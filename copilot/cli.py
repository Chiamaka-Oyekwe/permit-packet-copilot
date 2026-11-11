"""Command line entry point.

    python -m copilot.cli check examples/job_dallas_bore.json --packet examples/packet_dallas
    python -m copilot.cli cities
    python -m copilot.cli extract "Plano" ordinance.txt --label "Plano ROW ordinance" --url https://...
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import extract as extract_mod
from .narrative import draft_cover_letter, polish_with_claude
from .packet import check_packet
from .rules import build_checklist, lead_time_check, list_cities, load_city

LABELS = {
    "prerequisite": "Before you apply",
    "document": "In the packet",
    "notice": "Notices",
    "timing": "Timing",
    "field": "In the field",
    "option": "Worth knowing",
}


def cmd_check(args) -> int:
    job = json.loads(Path(args.job).read_text())
    city = load_city(job["city"])
    checklist = build_checklist(city, job)

    print(f"{city['city']}: {city['permit_name']}  ({len(checklist)} requirements apply)\n")
    for kind, label in LABELS.items():
        rows = [r for r in checklist if r["kind"] == kind]
        if not rows:
            continue
        print(label)
        for r in rows:
            print(f"  [{r['id']}] {r['title']}")
            print(f"      {r['source']['label']}, {r['source']['cite']}")
        print()

    packet = None
    if args.packet:
        files = [p.name for p in sorted(Path(args.packet).iterdir()) if p.is_file()]
        packet = check_packet(checklist, files)
        print(f"Packet check: {len(packet['found'])} found, {len(packet['missing'])} missing")
        for m in packet["missing"]:
            print(f"  MISSING  {m['title']}")
        for f in packet["unmatched"]:
            print(f"  not matched to a requirement: {f}")
        print()

    if job.get("start_date"):
        submit = date.fromisoformat(args.submit) if args.submit else date.today()
        lead = lead_time_check(checklist, submit, date.fromisoformat(job["start_date"]))
        if lead:
            verdict = "OK" if lead["ok"] else "TOO LATE"
            print(f"Lead time: need {lead['needed']} business days, have {lead['have']}  [{verdict}]\n")

    letter = draft_cover_letter(city, job, checklist, packet)
    if args.ai:
        letter = polish_with_claude(letter)
    print("Cover letter draft\n" + "-" * 18)
    print(letter)
    return 1 if packet and packet["missing"] else 0


def cmd_cities(_args) -> int:
    for slug in list_cities():
        c = load_city(slug)
        print(f"{slug:12} {c['city']}: {len(c['requirements'])} requirements, reviewed {c['reviewed']}")
    return 0


def cmd_extract(args) -> int:
    text = Path(args.source).read_text()
    reqs = extract_mod.extract(args.city, args.label, args.url, text)
    json.dump(reqs, sys.stdout, indent=2)
    print(f"\n\n{len(reqs)} draft requirements. Read each one against the source before using it.",
          file=sys.stderr)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="copilot", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="build the checklist and check a packet")
    c.add_argument("job")
    c.add_argument("--packet", help="folder holding the packet files")
    c.add_argument("--submit", help="planned submittal date, YYYY-MM-DD (default: today)")
    c.add_argument("--ai", action="store_true", help="have Claude tighten the cover letter")
    c.set_defaults(func=cmd_check)

    sub.add_parser("cities", help="list cities with rules").set_defaults(func=cmd_cities)

    e = sub.add_parser("extract", help="draft rules for a new city from source text")
    e.add_argument("city")
    e.add_argument("source")
    e.add_argument("--label", required=True)
    e.add_argument("--url", required=True)
    e.set_defaults(func=cmd_extract)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
