import os
import re
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
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

cases = []

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

CONFIDENCE_MAP = {"high": 0.9, "medium": 0.6, "low": 0.3}

CASES_FIELDNAMES = [
    "case_id", "category", "symptom", "topology_note", "show_output",
    "expected_fault", "osi_layer", "concept_tag", "severity", "source",
]
AI_FIELDNAMES = [
    "case_id", "category", "ai_root_cause", "ai_osi_layer", "ai_confidence",
    "ai_evidence", "ai_next_command", "ai_fix_steps", "parse_status", "raw_response",
]
REVIEW_FIELDNAMES = [
    "case_id", "category", "symptom", "expected_fault", "ai_root_cause",
    "ai_confidence", "ai_evidence", "match_looks_correct", "verdict", "reviewer_notes",
]


def confidence_to_text(c):
    try:
        c = float(c)
    except (TypeError, ValueError):
        return "medium"
    if c >= 0.75:
        return "high"
    if c >= 0.45:
        return "medium"
    return "low"


def load_csv(dir_path, filename):
    path = os.path.join(dir_path, filename)
    if not os.path.exists(path):
        print(f"  (not found: {path})")
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def seed_from_csv():
    """Loads cases.csv (from /data) + ai_diagnosis.csv + review_sheet.csv
    (from /results) into the live `cases` list on startup."""
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
            "expected_fault": c.get("expected_fault", ""),
            "concept_tag": c.get("concept_tag", ""),
            "severity": c.get("severity", ""),
            "source": c.get("source", "seed"),
            "match_looks_correct": rv.get("match_looks_correct", ""),
            "parse_status": ai.get("parse_status", "ok"),
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


def save_all_to_csv():
    """Rewrites cases.csv, ai_diagnosis.csv, and review_sheet.csv completely
    from the current in-memory `cases` list. Called after any create,
    review, or delete so the files on disk always match the live app."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(os.path.join(DATA_DIR, "cases.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CASES_FIELDNAMES)
        writer.writeheader()
        for c in cases:
            d = c["diagnosis"]
            writer.writerow({
                "case_id": c["id"],
                "category": d.get("category", ""),
                "symptom": c.get("symptom", ""),
                "topology_note": c.get("packet_tracer_notes", ""),
                "show_output": c.get("show_output", ""),
                "expected_fault": c.get("expected_fault", ""),
                "osi_layer": d.get("osi_layer", ""),
                "concept_tag": c.get("concept_tag", ""),
                "severity": c.get("severity", ""),
                "source": c.get("source", "live"),
            })

    with open(os.path.join(RESULTS_DIR, "ai_diagnosis.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AI_FIELDNAMES)
        writer.writeheader()
        for c in cases:
            d = c["diagnosis"]
            writer.writerow({
                "case_id": c["id"],
                "category": d.get("category", ""),
                "ai_root_cause": d.get("root_cause", ""),
                "ai_osi_layer": d.get("osi_layer", ""),
                "ai_confidence": confidence_to_text(d.get("confidence", 0.5)),
                "ai_evidence": d.get("evidence", ""),
                "ai_next_command": d.get("next_command", ""),
                "ai_fix_steps": " | ".join(d.get("fix_steps", [])),
                "parse_status": c.get("parse_status", "ok"),
                "raw_response": json.dumps(d),
            })

    with open(os.path.join(RESULTS_DIR, "review_sheet.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDNAMES)
        writer.writeheader()
        for c in cases:
            d = c["diagnosis"]
            writer.writerow({
                "case_id": c["id"],
                "category": d.get("category", ""),
                "symptom": c.get("symptom", ""),
                "expected_fault": c.get("expected_fault", ""),
                "ai_root_cause": d.get("root_cause", ""),
                "ai_confidence": confidence_to_text(d.get("confidence", 0.5)),
                "ai_evidence": d.get("evidence", ""),
                "match_looks_correct": c.get("match_looks_correct", ""),
                "verdict": c.get("verdict", "Pending"),
                "reviewer_notes": c.get("reviewer_note", ""),
            })


def generate_next_case_id():
    """Scans existing case IDs matching the C0XX pattern and returns the
    next number in sequence, e.g. C032 -> C033. Falls back to C001 if
    none exist yet."""
    max_num = 0
    for c in cases:
        match = re.match(r"^C(\d+)$", c["id"])
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"C{max_num + 1:03d}"


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
  "osi_layer": "one of: Layer 1, Layer 2, Layer 3, Layer 4, Layer 7",
  "confidence": 0.0 to 1.0,
  "evidence": "specific evidence from the input that supports this diagnosis",
  "next_command": "a single show/debug command to confirm the fault",
  "fix_steps": ["step 1", "step 2", "step 3"],
  "category": "one of: VLAN, Gateway, DHCP, DNS, Routing, ACL, NAT, Wireless",
  "concept_tag": "a short kebab-case tag summarizing the fault type, e.g. vlan-misassignment, missing-static-route, acl-deny-before-permit",
  "severity": "one of: Low, Medium, High"
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
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        diagnosis = json.loads(raw)
        parse_status = "ok"
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
        parse_status = "PARSE_FAILED"

    case = {
        "id": generate_next_case_id(),
        "symptom": req.symptom,
        "packet_tracer_notes": req.packet_tracer_notes,
        "show_output": req.show_output,
        "expected_fault": "",
        "concept_tag": diagnosis.get("concept_tag", ""),
        "severity": diagnosis.get("severity", ""),
        "source": "live",
        "match_looks_correct": "",
        "parse_status": parse_status,
        "diagnosis": diagnosis,
        "verdict": "Pending",
        "reviewer_note": "",
        "created_at": datetime.utcnow().isoformat(),
    }
    cases.append(case)
    save_all_to_csv()
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
            save_all_to_csv()
            return c
    raise HTTPException(status_code=404, detail="Case not found")


@app.delete("/cases/{case_id}")
def delete_case(case_id: str):
    global cases
    original_len = len(cases)
    cases = [c for c in cases if c["id"] != case_id]
    if len(cases) == original_len:
        raise HTTPException(status_code=404, detail="Case not found")
    save_all_to_csv()
    return {"deleted": case_id}


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