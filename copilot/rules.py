"""Load a city's requirements and decide which ones apply to a job."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cities"

KINDS = ("prerequisite", "document", "notice", "timing", "field", "option")

JOB_DEFAULTS = {
    "method": "bore",            # bore | trench | aerial
    "new_facility": True,
    "pavement_cut": False,
    "lane_closure": False,
    "sidewalk_closure": False,
    "street_class": "collector",  # residential | collector | arterial | downtown
    "disturbed_acres": 0.0,
    "pavement_age_years": 10,
    "in_tree_dripline": False,
    "near_signal": False,
    "emergency": False,
}


def list_cities() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def load_city(slug: str) -> dict:
    path = DATA_DIR / f"{slug}.json"
    if not path.exists():
        raise ValueError(f"No rules for '{slug}'. Available: {', '.join(list_cities())}")
    return json.loads(path.read_text())


def _test(leaf: dict, job: dict) -> bool:
    actual = job.get(leaf["field"])
    op, want = leaf["op"], leaf["value"]
    if op == "eq":
        return actual == want
    if op == "in":
        return actual in want
    if op == "lt":
        return actual is not None and actual < want
    if op == "gte":
        return actual is not None and actual >= want
    raise ValueError(f"Unknown operator: {op}")


def applies(when: dict | None, job: dict) -> bool:
    """A requirement with no condition always applies."""
    if when is None:
        return True
    if "all" in when:
        return all(applies(c, job) for c in when["all"])
    if "any" in when:
        return any(applies(c, job) for c in when["any"])
    return _test(when, job)


def build_checklist(city: dict, job: dict) -> list[dict]:
    """Return the requirements that apply to this job, in the city's order."""
    full_job = {**JOB_DEFAULTS, **job}
    return [r for r in city["requirements"] if applies(r.get("when"), full_job)]


def business_days_between(start: date, end: date) -> int:
    """Whole business days from start up to end. Weekends skipped; holidays are not."""
    if end <= start:
        return 0
    days, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def lead_time_check(checklist: list[dict], submit_on: date, start_on: date) -> dict | None:
    """Compare the planned start against the longest lead time on the checklist."""
    needed = max((r.get("lead_business_days", 0) for r in checklist), default=0)
    if not needed:
        return None
    have = business_days_between(submit_on, start_on)
    return {"needed": needed, "have": have, "ok": have >= needed}
