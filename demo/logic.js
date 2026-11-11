// Same rules as copilot/rules.py, packet.py and narrative.py, for the browser demo.
const JOB_DEFAULTS = {
  method: "bore", new_facility: true, pavement_cut: false, lane_closure: false,
  sidewalk_closure: false, street_class: "collector", disturbed_acres: 0,
  pavement_age_years: 10, in_tree_dripline: false, near_signal: false, emergency: false,
};

function applies(when, job) {
  if (when === null || when === undefined) return true;
  if (when.all) return when.all.every((c) => applies(c, job));
  if (when.any) return when.any.some((c) => applies(c, job));
  const actual = job[when.field];
  switch (when.op) {
    case "eq": return actual === when.value;
    case "in": return when.value.includes(actual);
    case "lt": return actual !== null && actual !== undefined && actual < when.value;
    case "gte": return actual !== null && actual !== undefined && actual >= when.value;
    default: throw new Error("Unknown operator: " + when.op);
  }
}

function buildChecklist(city, job) {
  const full = Object.assign({}, JOB_DEFAULTS, job);
  return city.requirements.filter((r) => applies(r.when, full));
}

function parseDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function businessDaysBetween(startIso, endIso) {
  const start = parseDate(startIso), end = parseDate(endIso);
  let days = 0;
  const d = new Date(start);
  while (d < end) {
    d.setUTCDate(d.getUTCDate() + 1);
    const wd = d.getUTCDay();
    if (wd !== 0 && wd !== 6) days += 1;
  }
  return days;
}

function leadTimeCheck(checklist, submitIso, startIso) {
  const needed = Math.max(0, ...checklist.map((r) => r.lead_business_days || 0));
  if (!needed || !submitIso || !startIso) return null;
  const have = businessDaysBetween(submitIso, startIso);
  return { needed, have, ok: have >= needed };
}

const normalize = (s) => s.toLowerCase().replace(/[_-]/g, " ");

function checkPacket(checklist, filenames) {
  const names = filenames.map((f) => [f, normalize(f.split(/[\\/]/).pop())]);
  const found = [], missing = [];
  for (const req of checklist) {
    if (req.kind !== "document" || req.closeout) continue;
    const hits = names
      .filter(([, n]) => (req.match || []).some((k) => n.includes(normalize(k)))
        && !(req.exclude || []).some((x) => n.includes(normalize(x))))
      .map(([f]) => f);
    (hits.length ? found : missing).push({ id: req.id, title: req.title, files: hits });
  }
  const used = new Set(found.flatMap((i) => i.files));
  return { found, missing, unmatched: names.map(([f]) => f).filter((f) => !used.has(f)) };
}

const METHOD_TEXT = { bore: "directional bore", trench: "open trench", aerial: "aerial placement on existing poles" };

function draftCoverLetter(city, job, checklist, packet) {
  const loc = job.location || "the location shown on the plans";
  const len = job.length_ft ? `approximately ${Number(job.length_ft).toLocaleString("en-US")} feet of ` : "";
  const lines = [
    `Re: ${city.permit_name} application, ${job.location || "location per plans"}`,
    "",
    `${job.facility_owner || "The applicant"} proposes to place ${len}fiber optic cable by ${METHOD_TEXT[job.method] || job.method} at ${loc}.`,
  ];
  if (job.description && job.description.trim()) lines.push(job.description.trim());
  const traffic = [];
  if (job.lane_closure) traffic.push("a lane closure");
  if (job.sidewalk_closure) traffic.push("a sidewalk closure");
  lines.push(traffic.length
    ? `The work requires ${traffic.join(" and ")}. A traffic control plan is enclosed.`
    : "No lane or sidewalk closure is planned.");
  if (job.start_date) lines.push(`Requested start date: ${job.start_date}.`);
  const docs = checklist.filter((r) => r.kind === "document" && !r.closeout);
  if (docs.length) {
    const miss = new Set(((packet && packet.missing) || []).map((m) => m.id));
    lines.push("", "Enclosed:");
    for (const r of docs) lines.push(`  - ${r.title}${miss.has(r.id) ? "  [NOT YET IN PACKET]" : ""}`);
  }
  const notices = checklist.filter((r) => r.kind === "notice");
  if (notices.length) {
    lines.push("", "Notices we will complete before work begins:");
    for (const r of notices) lines.push(`  - ${r.title}`);
  }
  lines.push("", job.contact ? `Questions on this submittal can go to ${job.contact}.`
    : "Please contact us with any questions on this submittal.");
  return lines.join("\n");
}

if (typeof module !== "undefined") {
  module.exports = { applies, buildChecklist, businessDaysBetween, leadTimeCheck, checkPacket, draftCoverLetter };
}
