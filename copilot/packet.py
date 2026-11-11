"""Compare the files in a packet against the documents a city asks for."""
from __future__ import annotations

from pathlib import Path


def _normalize(name: str) -> str:
    return name.lower().replace("_", " ").replace("-", " ")


def check_packet(checklist: list[dict], filenames: list[str]) -> dict:
    """Match file names to required documents by keyword.

    Matching on names is deliberately simple. It catches the missing exhibit,
    which is the common failure. It does not judge what is inside a file.
    """
    names = [(f, _normalize(Path(f).name)) for f in filenames]
    found, missing = [], []
    for req in checklist:
        if req["kind"] != "document" or req.get("closeout"):
            continue
        hits = [orig for orig, norm in names
                if any(_normalize(k) in norm for k in req.get("match", []))
                and not any(_normalize(x) in norm for x in req.get("exclude", []))]
        (found if hits else missing).append({"id": req["id"], "title": req["title"], "files": hits})
    used = {f for item in found for f in item["files"]}
    unmatched = [f for f, _ in names if f not in used]
    return {"found": found, "missing": missing, "unmatched": unmatched}
