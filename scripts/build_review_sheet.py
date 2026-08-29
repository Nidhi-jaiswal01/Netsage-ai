"""
NetSage AI — Review Comparison Builder
-----------------------------------------
Merges cases.csv (the known-correct answers) with ai_diagnosis.csv (the AI's
output) into a single side-by-side CSV, ready for human review.

Adds an empty 'verdict' column (Accepted / Edited / Rejected) and a
'reviewer_notes' column for you to fill in manually — e.g. in Excel or
Google Sheets — rather than needing to cross-reference two separate files.

Usage:
    python build_review_sheet.py --cases ../data/cases.csv --ai ../results/ai_diagnosis.csv --output ../results/review_sheet.csv
"""

import csv
import argparse


def build_review_sheet(cases_path: str, ai_path: str, output_path: str):
    with open(cases_path, newline="", encoding="utf-8") as f:
        cases = {row["case_id"]: row for row in csv.DictReader(f)}

    with open(ai_path, newline="", encoding="utf-8") as f:
        ai_results = {row["case_id"]: row for row in csv.DictReader(f)}

    fieldnames = [
        "case_id",
        "category",
        "symptom",
        "expected_fault",
        "ai_root_cause",
        "ai_confidence",
        "ai_evidence",
        "match_looks_correct",  # a simple heuristic hint, not a final verdict
        "verdict",              # YOU fill this in: Accepted / Edited / Rejected
        "reviewer_notes",       # YOU fill this in, especially for Edited/Rejected
    ]

    output_rows = []
    missing_ai = []

    for case_id, case in cases.items():
        ai = ai_results.get(case_id)
        if not ai:
            missing_ai.append(case_id)
            continue

        # Simple heuristic: do any meaningful words overlap between the
        # expected fault and the AI's root cause? This is NOT the actual
        # judgment — it's just a hint to speed up your manual review.
        expected_words = set(case["expected_fault"].lower().split())
        ai_words = set(ai["ai_root_cause"].lower().split())
        overlap = expected_words & ai_words
        hint = "possible match" if len(overlap) >= 2 else "check closely"

        output_rows.append({
            "case_id": case_id,
            "category": case.get("category", ""),
            "symptom": case.get("symptom", ""),
            "expected_fault": case.get("expected_fault", ""),
            "ai_root_cause": ai.get("ai_root_cause", ""),
            "ai_confidence": ai.get("ai_confidence", ""),
            "ai_evidence": ai.get("ai_evidence", ""),
            "match_looks_correct": hint,
            "verdict": "",           # left blank for you to fill in
            "reviewer_notes": "",    # left blank for you to fill in
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Built review sheet with {len(output_rows)} cases.")
    if missing_ai:
        print(f"WARNING: {len(missing_ai)} case(s) had no AI diagnosis: {missing_ai}")
    print(f"Written to {output_path}")
    print("\nNext step: open this file, review each row, and fill in the 'verdict' column")
    print("with Accepted / Edited / Rejected, plus a short note for anything not Accepted.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a side-by-side AI vs expected review sheet")
    parser.add_argument("--cases", default="../data/cases.csv")
    parser.add_argument("--ai", default="../results/ai_diagnosis.csv")
    parser.add_argument("--output", default="../results/review_sheet.csv")
    args = parser.parse_args()

    build_review_sheet(args.cases, args.ai, args.output)
