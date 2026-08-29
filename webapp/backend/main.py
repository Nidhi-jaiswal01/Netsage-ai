import os
import csv
import json
import uuid
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

cases = []

# webapp/backend/main.py -> go up two levels to reach the project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}


def load_csv(dir_path, filename):
    path = os.path.join(dir_path, filename)
    if not os.path.exists(path):
        print(f"  (not found: {path})")
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def seed_from_csv():
    """Loads cases.csv (from /data) + ai_diagnosis.csv + review_sheet.csv
    (from /results) and merges them into the live `cases` list, so
    existing graded work shows up immediately on startup."""
    case_rows = {r["case_id"]: r for r in load_csv(DATA_DIR, "cases.csv")}
    ai_rows = {r["case_id"]: r for r in load_csv(RESULTS_DIR, "ai_diagnosis.csv")}
    review_rows = {r["case_id"]: r for r in load_csv(RESULTS_DIR, "review_sheet.csv")}

    if not case_rows:
        print("No cases.csv found — starting with an empty dashboard.")
        return

    for case_id, c in sorted(case_rows.items()):
        ai = ai_rows.get(case_id, {})
        rv = review_rows.get(case_id, {})

        confidence_raw = (ai.get("ai_confidence") or "").strip().lower()
        confidence = CONFIDENCE_MAP.get(confidence_raw, 0.5)

        fix_steps_raw = ai.get("ai_fix_steps", "")
        fix_steps = [s.strip() for s in fix_steps_raw.split("|") if s.strip()]

        verdict = (rv.get("verdict") or "").strip() or "Pending"

        cases.append({
            "id": case_id,
            "symptom": c.get("symptom", ""),
            "packet_tracer_notes": c.get("topology_note", ""),
            "show_output": c.get("show_output", ""),
            "diagnosis": {
                "root_cause": ai.get("ai_root_cause", c.get("expected_fault", "")),
                "osi_layer": ai.get("ai_osi_layer", c.get("osi_layer", "")),
                "confidence": confidence,
                "evidence": ai.get("ai_evidence", ""),
                "next_command": ai.get("ai_next_command", ""),
                "fix_steps": fix_steps,
                "category": c.get("category", "Unknown"),
            },
            "verdict": verdict,
            "reviewer_note": rv.get("reviewer_notes", ""),
            "created_at": datetime.utcnow().isoformat(),
        })

    print(f"Seeded {len(cases)} case(s) from CSV data.")


seed_from_csv()


class DiagnoseRequest(BaseModel):
    symptom: str
    packet_tracer_notes: str = ""
    show_output: str = ""


class ReviewRequest(BaseModel):
    verdict: str
    note: str = ""
    edited_diagnosis: Optional[dict] = None


SYSTEM_PROMPT = """You are NetSage AI, a network troubleshooting assistant for Cisco-style lab networks (VLAN, DHCP, DNS, routing, ACL, NAT, wireless).

You will be given: a symptom description, Packet Tracer notes, and show-command output.

Respond ONLY with valid JSON in this exact shape, no markdown fences, no extra text:
{
  "root_cause": "short, specific description of the likely fault",
  "osi_layer": "one of: Physical, Data Link, Network, Transport, Session, Presentation, Application",
  "confidence": 0.0 to 1.0,
  "evidence": "specific evidence from the input that supports this diagnosis",
  "next_command": "a single show/debug command to confirm the fault",
  "fix_steps": ["step 1", "step 2", "step 3"],
  "category": "one of: VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless"
}"""


@app.post("/diagnose")
def diagnose(req: DiagnoseRequest):
    user_content = f"""SYMPTOM:
{req.symptom}

PACKET TRACER NOTES:
{req.packet_tracer_notes or "(none provided)"}

SHOW COMMAND OUTPUT:
{req.show_output or "(none provided)"}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        diagnosis = json.loads(raw)
    except json.JSONDecodeError:
        diagnosis = {
            "root_cause": "Could not parse AI response",
            "osi_layer": "Unknown",
            "confidence": 0.0,
            "evidence": raw,
            "next_command": "",
            "fix_steps": [],
            "category": "Unknown",
        }

    case = {
        "id": str(uuid.uuid4())[:8],
        "symptom": req.symptom,
        "packet_tracer_notes": req.packet_tracer_notes,
        "show_output": req.show_output,
        "diagnosis": diagnosis,
        "verdict": "Pending",
        "reviewer_note": "",
        "created_at": datetime.utcnow().isoformat(),
    }
    cases.append(case)
    return case


@app.get("/cases")
def get_cases():
    return list(reversed(cases))


@app.post("/cases/{case_id}/review")
def review_case(case_id: str, req: ReviewRequest):
    for c in cases:
        if c["id"] == case_id:
            c["verdict"] = req.verdict
            c["reviewer_note"] = req.note
            if req.edited_diagnosis:
                c["diagnosis"] = req.edited_diagnosis
            return c
    raise HTTPException(status_code=404, detail="Case not found")


@app.get("/summary")
def summary():
    total = len(cases)
    verdict_counts = {"Accepted": 0, "Edited": 0, "Rejected": 0, "Pending": 0}
    category_counts = {}
    for c in cases:
        verdict_counts[c["verdict"]] = verdict_counts.get(c["verdict"], 0) + 1
        cat = c["diagnosis"].get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
    return {
        "total": total,
        "verdict_counts": verdict_counts,
        "category_counts": category_counts,
    }