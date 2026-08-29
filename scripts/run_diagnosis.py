"""
NetSage AI — AI Diagnosis Runner
----------------------------------
Sends each case from cases.csv to a Groq-hosted LLM, using diagnose_prompt.md
as the system prompt, and saves the structured JSON response.

This script does NOT do any human review — it only collects the AI's raw
diagnosis for every case so that a human reviewer (you) can compare it
against the known-correct answer afterward.

Setup:
    1. Get a free API key from https://console.groq.com
    2. Create a file named .env in your project root (same level as data/, scripts/)
       containing one line:
         GROQ_API_KEY=your-key-here
       Make sure .env is listed in .gitignore so it never gets pushed to GitHub.
    3. Install dependencies:
         pip install groq python-dotenv

Usage:
    python run_diagnosis.py --cases ../data/cases.csv --prompt ../prompts/diagnose_prompt.md --output ../results/ai_diagnosis.csv
"""

import os
import csv
import json
import argparse
import time
from groq import Groq
from dotenv import load_dotenv

load_dotenv()  # reads GROQ_API_KEY from a local .env file, if present


MODEL = "openai/gpt-oss-20b"  # confirmed available via check_models.py


def load_prompt(prompt_path: str) -> str:
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def build_user_message(row: dict) -> str:
    """Formats a single case's evidence into the message sent to the AI,
    exactly as a human engineer would present it — no hints, no answers."""
    return (
        f"Symptom: {row['symptom']}\n"
        f"Topology note: {row['topology_note']}\n"
        f"Show-command output:\n{row['show_output']}"
    )


def call_ai(client: Groq, system_prompt: str, user_message: str, retries: int = 3):
    """Calls the Groq API and returns the raw text response. Retries on
    transient failures (rate limits, timeouts)."""
    last_error = None
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,  # low temperature: we want consistent, non-creative diagnosis
                max_tokens=600,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            wait = 2 ** attempt
            print(f"  Attempt {attempt + 1} failed ({e}), retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Failed after {retries} attempts: {last_error}")


def parse_ai_json(raw_text: str):
    """Tries to parse the AI's response as JSON. Strips markdown code fences
    if the model added them despite instructions not to."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, str(e)


def run(cases_path: str, prompt_path: str, output_path: str):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable not set. "
            "Get a free key at https://console.groq.com and set it before running this script."
        )

    client = Groq(api_key=api_key)
    system_prompt = load_prompt(prompt_path)

    with open(cases_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output_rows = []
    for i, row in enumerate(rows, start=1):
        case_id = row["case_id"]
        print(f"[{i}/{len(rows)}] Diagnosing {case_id}...")

        user_message = build_user_message(row)
        raw_response = call_ai(client, system_prompt, user_message)
        parsed, parse_error = parse_ai_json(raw_response)

        if parsed:
            output_rows.append({
                "case_id": case_id,
                "category": row.get("category", ""),
                "ai_root_cause": parsed.get("root_cause", ""),
                "ai_osi_layer": parsed.get("osi_layer", ""),
                "ai_confidence": parsed.get("confidence", ""),
                "ai_evidence": parsed.get("evidence", ""),
                "ai_next_command": parsed.get("next_command", ""),
                "ai_fix_steps": " | ".join(parsed.get("fix_steps", [])),
                "parse_status": "ok",
                "raw_response": raw_response,
            })
        else:
            output_rows.append({
                "case_id": case_id,
                "category": row.get("category", ""),
                "ai_root_cause": "",
                "ai_osi_layer": "",
                "ai_confidence": "",
                "ai_evidence": "",
                "ai_next_command": "",
                "ai_fix_steps": "",
                "parse_status": f"PARSE_FAILED: {parse_error}",
                "raw_response": raw_response,
            })
            print(f"  WARNING: could not parse JSON for {case_id}")

        time.sleep(1)  # small delay to stay comfortably within free-tier rate limits

    fieldnames = [
        "case_id", "category", "ai_root_cause", "ai_osi_layer", "ai_confidence",
        "ai_evidence", "ai_next_command", "ai_fix_steps", "parse_status", "raw_response"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    ok_count = sum(1 for r in output_rows if r["parse_status"] == "ok")
    print(f"\nDone. {ok_count}/{len(output_rows)} cases parsed successfully.")
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NetSage AI diagnosis runner (Groq)")
    parser.add_argument("--cases", default="../data/cases.csv", help="Path to cases.csv")
    parser.add_argument("--prompt", default="../prompts/diagnose_prompt.md", help="Path to diagnose_prompt.md")
    parser.add_argument("--output", default="../results/ai_diagnosis.csv", help="Path to write AI diagnosis results")
    args = parser.parse_args()

    run(args.cases, args.prompt, args.output)