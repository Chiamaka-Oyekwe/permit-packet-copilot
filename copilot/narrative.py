"""Draft the cover letter that goes on top of the packet."""
from __future__ import annotations

METHOD_TEXT = {
    "bore": "directional bore",
    "trench": "open trench",
    "aerial": "aerial placement on existing poles",
}


def scope_sentence(job: dict) -> str:
    method = METHOD_TEXT.get(job.get("method", ""), job.get("method", "construction"))
    length = job.get("length_ft")
    length_text = f"approximately {length:,} feet of " if length else ""
    return (f"{job.get('facility_owner', 'The applicant')} proposes to place "
            f"{length_text}fiber optic cable by {method} at {job.get('location', 'the location shown on the plans')}.")


def draft_cover_letter(city: dict, job: dict, checklist: list[dict], packet: dict | None = None) -> str:
    """Plain cover letter built from the job and the checklist. No model call."""
    lines = [
        f"Re: {city['permit_name']} application, {job.get('location', 'location per plans')}",
        "",
        scope_sentence(job),
    ]
    if job.get("description"):
        lines.append(job["description"].strip())
    traffic = []
    if job.get("lane_closure"):
        traffic.append("a lane closure")
    if job.get("sidewalk_closure"):
        traffic.append("a sidewalk closure")
    if traffic:
        lines.append(f"The work requires {' and '.join(traffic)}. A traffic control plan is enclosed.")
    else:
        lines.append("No lane or sidewalk closure is planned.")
    if job.get("start_date"):
        lines.append(f"Requested start date: {job['start_date']}.")

    docs = [r for r in checklist if r["kind"] == "document" and not r.get("closeout")]
    if docs:
        lines += ["", "Enclosed:"]
        missing_ids = {m["id"] for m in (packet or {}).get("missing", [])}
        for r in docs:
            flag = "  [NOT YET IN PACKET]" if r["id"] in missing_ids else ""
            lines.append(f"  - {r['title']}{flag}")

    notices = [r for r in checklist if r["kind"] == "notice"]
    if notices:
        lines += ["", "Notices we will complete before work begins:"]
        lines += [f"  - {r['title']}" for r in notices]

    contact = job.get("contact")
    lines += ["", f"Questions on this submittal can go to {contact}." if contact
              else "Please contact us with any questions on this submittal."]
    return "\n".join(lines)


def polish_with_claude(letter: str, model: str | None = None) -> str:
    """Optional: ask Claude to tighten the letter without changing any fact.

    Needs the `anthropic` package and ANTHROPIC_API_KEY.
    """
    import os
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model or os.environ.get("COPILOT_MODEL", "claude-sonnet-5-5"),
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": (
                "Rewrite this permit cover letter so a city reviewer can read it in thirty seconds. "
                "Keep every fact, date, quantity and enclosure exactly as written. Add nothing. "
                "Plain business English, no sales language.\n\n" + letter
            ),
        }],
    )
    return msg.content[0].text
