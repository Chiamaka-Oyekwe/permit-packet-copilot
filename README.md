# Permit Packet Copilot

I've had right-of-way permits come back from a city because one exhibit was missing. The fix takes ten minutes. The resubmittal costs a week, sometimes two, and a crew sits idle while it does.

This tool checks the packet before the city does. You describe the job, point it at the folder of files, and it tells you:

- which requirements apply to this job in this city
- which required documents are not in the packet yet
- whether you are submitting early enough
- a cover letter draft that lists what is enclosed and flags what is not

Every requirement carries the ordinance section or form page it came from, so a reviewer can check it instead of trusting it.

**Cities so far:** Dallas, Fort Worth, Richardson.

**Live demo:** https://chiamaka-oyekwe.github.io/permit-packet-copilot/ (opens for anyone, no account needed)

The same page [on Claude](https://claude.ai/artifact/5kxrhPYoBvTFStFXJmTrqV) adds two AI features for signed-in viewers: tightening the cover letter and answering questions about a city's rules.

## Try it

```
python -m copilot.cli check examples/job_dallas_bore.json --packet examples/packet_dallas
```

```
Dallas: Right-of-Way Permit  (12 requirements apply)
...
Packet check: 5 found, 2 missing
  MISSING  Underground facility statement
  MISSING  Performance bond, letter of credit or cash deposit
  not matched to a requirement: Site_Photos.zip

Lead time: need 3 business days, have 4  [OK]
```

The checker has no dependencies beyond Python 3.10. There is also a browser version in `demo/`.

## Where the AI is, and where it isn't

I kept the model out of the part that has to be right every time.

| Step | Who does it | Why |
|---|---|---|
| Read an ordinance or form and draft the requirements | Claude (`copilot/extract.py`) | Reading forty pages of municipal code for the six lines that matter is slow work a model does well. |
| Check every drafted requirement against its source | A person | A wrong requirement is worse than a missing one. The draft is rejected automatically if any line lacks a citation. |
| Decide which requirements apply to a job | Plain rules (`copilot/rules.py`) | Same input, same answer, every time. Testable. |
| Compare the packet to the checklist | Plain rules (`copilot/packet.py`) | Same reason. |
| Tighten the cover letter | Claude, optional (`--ai`) | Told to keep every fact and add nothing. The plain draft works without it. |

To add a city:

```
export ANTHROPIC_API_KEY=...
python -m copilot.cli extract "Plano" plano_row_ordinance.txt \
    --label "Plano ROW ordinance" --url https://... > data/cities/plano.draft.json
```

Then read each line against the source, fix what is wrong, and save it as `data/cities/plano.json`.

## What it does not do

- It matches on file names. It will catch a missing traffic control plan. It will not tell you the plan is drawn at the wrong scale.
- Business-day counts skip weekends and ignore city holidays.
- The rules are a snapshot. Each city file has a `reviewed` date. Cities change forms and ordinances, so confirm with the city before relying on any of it.
- It covers the first submittal. Closeout items such as as-builts are listed and marked, not checked.
- This is not legal advice.

## How a requirement is written

```json
{
  "id": "DAL-BOND",
  "kind": "document",
  "title": "Performance bond, letter of credit or cash deposit",
  "detail": "Required before the permit issues for pavement excavation or boring that installs a new facility...",
  "when": {"all": [
    {"field": "new_facility", "op": "eq", "value": true},
    {"any": [
      {"field": "method", "op": "in", "value": ["bore", "trench"]},
      {"field": "pavement_cut", "op": "eq", "value": true}
    ]}
  ]},
  "match": ["bond", "letter of credit", "surety"],
  "source": {"label": "Dallas City Code Sec. 43-140.1", "cite": "Performance bond", "url": "https://..."}
}
```

`when` is the condition under which it applies. `match` is what to look for in file names.

## Tests

```
pip install pytest
python -m pytest
```

Sixteen tests. One of them runs the browser logic in Node and checks it gives the same checklist, packet result and letter as the Python for every city, so the demo cannot drift from the tool.

## Layout

```
copilot/        rules, packet check, cover letter, extraction, CLI
data/cities/    one JSON file per city
demo/           browser version (build with: python demo/build.py)
docs/           the built page, served by GitHub Pages
examples/       a sample job and packet folder
tests/
```

## Sources

- Dallas City Code, Chapter 43, Article VIII (right-of-way permits and performance bond)
- City of Dallas Public Works, Right-of-Way Management
- City of Fort Worth Utility Construction Policy, Resolution 5082-05-2019
- City of Fort Worth, Franchise Utility Permitting Guidelines and Requirements
- City of Richardson, Application for Right-of-Way Construction Permit (rev. 02/07/22)

Links to each are in the city files.
