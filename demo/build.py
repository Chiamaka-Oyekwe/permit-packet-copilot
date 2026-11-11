"""Assemble demo/index.html from the template, the browser logic and the city files."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
cities = {p.stem: json.loads(p.read_text()) for p in sorted((HERE.parent / "data" / "cities").glob("*.json"))}
logic = (HERE / "logic.js").read_text().split("if (typeof module")[0]
html = (HERE / "template.html").read_text()
html = html.replace("/*__DATA__*/", json.dumps(cities).replace("</", "<\\/"))
html = html.replace("/*__LOGIC__*/", logic)
(HERE / "index.html").write_text(html)
print(f"wrote demo/index.html ({len(html):,} bytes, {len(cities)} cities)")
