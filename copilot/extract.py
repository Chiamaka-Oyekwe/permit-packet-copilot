"""Turn ordinance or form text into a draft requirements file.

This is the step that adds a new city. Claude reads the source text and
proposes requirements in the same shape as data/cities/*.json. The output is
a draft: a person who knows permitting reads every line against the source
before it is used.
"""
from __future__ import annotations

import json

from .rules import KINDS

FIELDS = {
    "method": "bore | trench | aerial",
    "new_facility": "true when a new facility is installed (not a repair)",
    "pavement_cut": "true when pavement is cut or removed",
    "lane_closure": "true when a traffic lane is closed",
    "sidewalk_closure": "true when a sidewalk is blocked",
    "street_class": "residential | collector | arterial | downtown",
    "disturbed_acres": "number",
    "pavement_age_years": "number",
    "in_tree_dripline": "true when work falls inside a tree drip line",
    "near_signal": "true when within 500 ft of a signalized intersection",
    "emergency": "true for emergency work",
}
OPS = ("eq", "in", "lt", "gte")


def build_prompt(city: str, source_label: str, source_url: str, text: str) -> str:
    return f"""You are helping a telecom permitting engineer build a submittal checklist for {city}.

Read the source text and list every requirement a fiber contractor must meet to
get and keep a right-of-way permit. Use only what the text says. If the text does
not state something, leave it out.

Return JSON only: a list of objects with these keys.
- id: short code, uppercase, unique
- kind: one of {", ".join(KINDS)}
- title: under 12 words, in your own words
- detail: one or two sentences, in your own words
- when: null if it always applies, otherwise a condition
- match: for kind "document" only, lowercase keywords likely to appear in the file name
- lead_business_days: for kind "timing" only, when the text gives a submittal lead time
- source: {{"label": "{source_label}", "cite": "<section or page>", "url": "{source_url}"}}

Conditions are {{"field": ..., "op": ..., "value": ...}}, or {{"all": [...]}}, or {{"any": [...]}}.
Operators: {", ".join(OPS)}. Fields:
{json.dumps(FIELDS, indent=2)}

Source text:
<source>
{text}
</source>"""


def validate(requirements: list[dict]) -> list[str]:
    """Return a list of problems. Empty means the draft is well-formed."""
    problems, seen = [], set()

    def check_when(when, rid):
        if when is None:
            return
        if "all" in when or "any" in when:
            for c in when.get("all", when.get("any", [])):
                check_when(c, rid)
            return
        if when.get("field") not in FIELDS:
            problems.append(f"{rid}: unknown field {when.get('field')!r}")
        if when.get("op") not in OPS:
            problems.append(f"{rid}: unknown operator {when.get('op')!r}")

    for r in requirements:
        rid = r.get("id", "<no id>")
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)
        for key in ("id", "kind", "title", "detail", "source"):
            if not r.get(key):
                problems.append(f"{rid}: missing {key}")
        if r.get("kind") not in KINDS:
            problems.append(f"{rid}: unknown kind {r.get('kind')!r}")
        if r.get("kind") == "document" and not r.get("match"):
            problems.append(f"{rid}: document with no match keywords")
        if not (r.get("source") or {}).get("cite"):
            problems.append(f"{rid}: no citation")
        check_when(r.get("when"), rid)
    return problems


def extract(city: str, source_label: str, source_url: str, text: str,
            client=None, model: str | None = None) -> list[dict]:
    """Ask Claude for a draft. Raises if the draft is malformed."""
    import os
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model or os.environ.get("COPILOT_MODEL", "claude-sonnet-5-5"),
        max_tokens=4000,
        messages=[{"role": "user", "content": build_prompt(city, source_label, source_url, text)}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    requirements = json.loads(raw)
    problems = validate(requirements)
    if problems:
        raise ValueError("Draft failed validation:\n" + "\n".join(problems))
    return requirements
