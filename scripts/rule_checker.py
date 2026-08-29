"""
NetSage AI — Rule Checker
--------------------------
Deterministic, non-AI checks over network case evidence (show-command output).

This script looks for six common configuration mistakes:
  1. Duplicate IP addresses (ARP conflict evidence)
  2. Wrong / mismatched subnet mask
  3. Gateway mismatch (PC gateway vs actual SVI IP)
  4. Interface / SVI administratively down or down/down
  5. Missing VLAN (referenced VLAN not present in show vlan brief)
  6. Missing route (expected destination network not found in show ip route)

Each check is independent and returns a finding (or None) with a short reason.
This is intentionally rule-based and simple — no AI, no guessing — so its
output can be trusted as ground truth to compare against the AI's diagnosis.

Usage:
    python rule_checker.py --input ../data/cases.csv --output ../results/rule_checker_findings.csv
"""

import re
import csv
import argparse


# ---------------------------------------------------------------------------
# Individual checks
# Each check takes the raw show_output text (and sometimes topology_note)
# and returns a dict {check: str, triggered: bool, detail: str} or None.
# ---------------------------------------------------------------------------

def check_duplicate_ip(show_output: str):
    """Looks for the same IP address appearing twice with two different MAC
    addresses in an ARP table — the classic signature of a duplicate IP."""
    ip_mac_pairs = re.findall(
        r"Internet\s+(\d+\.\d+\.\d+\.\d+)\s+\d+\s+([0-9a-fA-F.]{14})",
        show_output
    )
    seen = {}
    for ip, mac in ip_mac_pairs:
        if ip in seen and seen[ip] != mac:
            return {
                "check": "duplicate_ip",
                "triggered": True,
                "detail": f"IP {ip} seen with two different MAC addresses ({seen[ip]} and {mac})"
            }
        seen[ip] = mac
    return None


def check_wrong_mask(show_output: str):
    """Looks for two differing subnet masks mentioned for what should be the
    same network context (heuristic: two distinct /prefix or mask patterns
    referring to a similar octet range)."""
    masks = re.findall(r"255\.255\.255\.\d+|/\d{1,2}\b", show_output)
    unique_masks = set(masks)
    if len(unique_masks) > 1:
        return {
            "check": "wrong_mask",
            "triggered": True,
            "detail": f"Multiple differing subnet masks found in evidence: {sorted(unique_masks)}"
        }
    return None


def check_gateway_mismatch(show_output: str, topology_note: str = ""):
    """Looks for a PC-configured 'Default Gateway' IP that does not match
    an SVI / interface IP mentioned elsewhere in the same evidence."""
    gw_match = re.search(r"Default Gateway:\s*(\d+\.\d+\.\d+\.\d+)", show_output)
    svi_ips = re.findall(r"(?:Vlan\d+|interface Vlan\d+)\D+(\d+\.\d+\.\d+\.\d+)", show_output + " " + topology_note)
    if gw_match and svi_ips:
        gw_ip = gw_match.group(1)
        if gw_ip not in svi_ips:
            return {
                "check": "gateway_mismatch",
                "triggered": True,
                "detail": f"PC default gateway {gw_ip} does not match any known SVI IP {svi_ips}"
            }
    return None


def check_interface_down(show_output: str):
    """Looks for 'administratively down' or 'down  down' status in
    show ip interface brief / show interfaces output."""
    if re.search(r"administratively down", show_output, re.IGNORECASE):
        return {
            "check": "interface_down",
            "triggered": True,
            "detail": "Interface or SVI is administratively down"
        }
    if re.search(r"\bdown\s+down\b", show_output, re.IGNORECASE):
        return {
            "check": "interface_down",
            "triggered": True,
            "detail": "Interface or SVI line protocol is down/down"
        }
    return None


def check_missing_vlan(show_output: str, expected_vlan: str = None):
    """If an expected VLAN number is provided, checks whether it's actually
    present in a 'show vlan brief' style output. Also flags explicit
    'not listed' phrasing used in simulated case text."""
    if "not listed" in show_output.lower():
        return {
            "check": "missing_vlan",
            "triggered": True,
            "detail": "Referenced VLAN explicitly noted as not listed on this switch"
        }
    if expected_vlan and re.search(r"VLAN\s*brief", show_output, re.IGNORECASE):
        if expected_vlan not in show_output:
            return {
                "check": "missing_vlan",
                "triggered": True,
                "detail": f"Expected VLAN {expected_vlan} not found in show vlan brief output"
            }
    return None


def check_missing_route(show_output: str):
    """Looks for explicit 'no route' phrasing or an empty show ip route
    result — both used in simulated evidence to represent a missing route."""
    if re.search(r"no route to|no static route|not listed\)|does not list a route|\(empty\)", show_output, re.IGNORECASE):
        return {
            "check": "missing_route",
            "triggered": True,
            "detail": "Expected route to destination network appears to be missing"
        }
    return None


CHECKS = [
    ("duplicate_ip", lambda row: check_duplicate_ip(row["show_output"])),
    ("wrong_mask", lambda row: check_wrong_mask(row["show_output"])),
    ("gateway_mismatch", lambda row: check_gateway_mismatch(row["show_output"], row.get("topology_note", ""))),
    ("interface_down", lambda row: check_interface_down(row["show_output"])),
    ("missing_vlan", lambda row: check_missing_vlan(row["show_output"])),
    ("missing_route", lambda row: check_missing_route(row["show_output"])),
]


def run_checks_on_case(row: dict):
    """Runs every check on a single case row. Returns a list of triggered
    findings (empty list if nothing was flagged)."""
    findings = []
    for name, fn in CHECKS:
        result = fn(row)
        if result:
            findings.append(result)
    return findings


def run_on_csv(input_path: str, output_path: str):
    with open(input_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    output_rows = []
    for row in rows:
        findings = run_checks_on_case(row)
        if findings:
            for finding in findings:
                output_rows.append({
                    "case_id": row["case_id"],
                    "category": row.get("category", ""),
                    "check_triggered": finding["check"],
                    "detail": finding["detail"]
                })
        else:
            output_rows.append({
                "case_id": row["case_id"],
                "category": row.get("category", ""),
                "check_triggered": "none",
                "detail": "No deterministic rule triggered for this case"
            })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "category", "check_triggered", "detail"])
        writer.writeheader()
        writer.writerows(output_rows)

    triggered_count = sum(1 for r in output_rows if r["check_triggered"] != "none")
    print(f"Processed {len(rows)} cases.")
    print(f"Rule checker triggered on {triggered_count} finding(s).")
    print(f"Results written to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NetSage AI deterministic rule checker")
    parser.add_argument("--input", default="../data/cases.csv", help="Path to cases.csv")
    parser.add_argument("--output", default="../results/rule_checker_findings.csv", help="Path to write findings CSV")
    args = parser.parse_args()

    run_on_csv(args.input, args.output)
