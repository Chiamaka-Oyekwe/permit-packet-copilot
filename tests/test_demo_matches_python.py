"""The browser demo re-implements the rules in JavaScript. Make sure both agree."""
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from copilot.narrative import draft_cover_letter
from copilot.packet import check_packet
from copilot.rules import build_checklist, lead_time_check, list_cities, load_city

ROOT = Path(__file__).resolve().parent.parent
JOBS = [
    {"method": "bore", "lane_closure": True, "sidewalk_closure": True, "street_class": "downtown",
     "facility_owner": "Example Fiber LLC", "location": "Elm St", "length_ft": 640, "start_date": "2026-12-01",
     "description": "Two conduits.", "contact": "permits@example.com"},
    {"method": "aerial", "street_class": "residential", "lane_closure": True},
    {"method": "trench", "pavement_cut": True, "pavement_age_years": 1, "disturbed_acres": 1.5,
     "in_tree_dripline": True, "near_signal": True, "length_ft": 12500},
    {"method": "bore", "emergency": True, "new_facility": False},
]
FILES = ["ROW_Application.pdf", "Traffic_Control_Plan.pdf", "Plans-11x17.pdf", "bond.pdf", "photos.zip"]

NODE = """
const L = require(process.argv[1]);
const {cities, jobs, files} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = [];
for (const slug of Object.keys(cities)) for (const job of jobs) {
  const cl = L.buildChecklist(cities[slug], job);
  const packet = L.checkPacket(cl, files);
  out.push({ids: cl.map(r => r.id), packet,
            lead: L.leadTimeCheck(cl, '2026-11-11', '2026-11-20'),
            letter: L.draftCoverLetter(cities[slug], job, cl, packet)});
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_and_python_agree():
    cities = {s: load_city(s) for s in list_cities()}
    payload = json.dumps({"cities": cities, "jobs": JOBS, "files": FILES})
    run = subprocess.run(["node", "-e", NODE, str(ROOT / "demo" / "logic.js")],
                         input=payload, capture_output=True, text=True, check=True)
    js = json.loads(run.stdout)
    i = 0
    for slug in cities:
        for job in JOBS:
            cl = build_checklist(cities[slug], job)
            packet = check_packet(cl, FILES)
            assert js[i]["ids"] == [r["id"] for r in cl]
            assert js[i]["packet"] == packet
            assert js[i]["lead"] == lead_time_check(cl, date(2026, 11, 11), date(2026, 11, 20))
            assert js[i]["letter"] == draft_cover_letter(cities[slug], job, cl, packet)
            i += 1
