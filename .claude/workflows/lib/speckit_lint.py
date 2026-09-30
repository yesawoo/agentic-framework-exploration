#!/usr/bin/env python3
"""Deterministic consistency checks for a Spec Kit feature directory. No model calls, read-only.

Usage: speckit_lint.py --feature specs/001-... [--out lint.json]
Prints a JSON document {stats, findings}. Findings use the same shape the analysis agents return
(id, severity, category, tasks, location, summary, evidence, recommendation) plus source="lint".
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from speckit_common import (  # noqa: E402
    FILE_EXT, PHASE_RE, TASK_RE, TICK_RE, is_concrete_path, parse_requirements, parse_tasks, read, sections,
)

# Names that are legitimately UPPER_SNAKE but not environment-contract variables.
NON_ENV_ALLOW = {
    # justfile / operator knobs that are documented in tasks and quickstart, not container env
    "KEEP_FINAL_SNAPSHOT", "FRESH", "MAX_UPTIME_HOURS", "AWS_PROFILE", "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_ENDPOINT_URL_BEDROCK_RUNTIME",
    "PYTHONPATH", "NODE_ENV", "PATH", "HOME",
}
# Stale terms that earlier passes removed on purpose; a reappearance is drift.
STALE_TERMS = [
    (r"\blangchain-anthropic\b", "Anthropic API client (Bedrock-only, FR-023)"),
    (r"\bANTHROPIC_API_KEY\b", "Anthropic API key (Bedrock-only, FR-023)"),
    (r"\bstub_anthropic\b", "renamed to stub_bedrock"),
    (r"SKIP_FINAL_SNAPSHOT", "replaced by KEEP_FINAL_SNAPSHOT (no snapshot by default)"),
    (r"migrations? (?:are |is )?(?:applied|run) (?:at|on) (?:start|startup)", "migrations run in the one-shot migrate task"),
    (r"one shared RDS Postgres", "database is Aurora Serverless v2"),
    (r"pydantic-ai`? 2\.x with the `anthropic`", "Pydantic AI uses the bedrock extra"),
]
NOT_METRICS = {
    "Converse", "ConverseStream", "InvokeModel", "InvokeModelWithResponseStream", "Authorization",
    "Marketplace", "Count", "Milliseconds", "Implementation", "Route", "Tool", "Dimensions",
}
SPLICE_STARTERS = (
    "Also|Takes|Take|Every|Region|Scenario|Environment|Alarm|Service-to-service|The|Tasks|Emit|Use|Names|"
    "Local|Attach|Set|Each|All|No|If|When|This|Resume|Region-agnostic|Every|Its|Add|Supports|Requires"
)
SPLICE_RE = re.compile(r"[a-z0-9`)\]](?: )(?:" + SPLICE_STARTERS + r") [a-z`]")


class Out:
    def __init__(self):
        self.items = []
        self.n = {}

    def add(self, check, severity, category, summary, evidence, recommendation, tasks=(), location=""):
        self.n[check] = self.n.get(check, 0) + 1
        self.items.append({
            "id": "L-%s-%02d" % (check, self.n[check]),
            "source": "lint",
            "severity": severity,
            "category": category,
            "tasks": list(tasks),
            "location": location,
            "summary": summary,
            "evidence": evidence[:400],
            "recommendation": recommendation,
        })


def env_names(feature_dir):
    text = read(Path(feature_dir) / "contracts" / "environment.md")
    names = set()
    for line in text.split("\n"):
        if line.startswith("|"):
            first = line.split("|")[1] if line.count("|") > 1 else ""
            for tok in TICK_RE.findall(first):
                if re.match(r"^[A-Z][A-Z0-9_]+$", tok):
                    names.add(tok)
    for tok in re.findall(r"`([A-Z][A-Z0-9_]{3,})`", text):
        names.add(tok)
    return names


def metric_names(feature_dir):
    text = read(Path(feature_dir) / "contracts" / "observability.md")
    return {t for t in TICK_RE.findall(text) if re.match(r"^[A-Z][A-Za-z0-9]+$", t)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    fd = Path(a.feature)
    o = Out()
    tasks, phases = parse_tasks(fd)
    tasks_txt = read(fd / "tasks.md")
    by_id = {t["id"]: t for t in tasks}

    # L1: task-ID integrity
    if not tasks:
        o.add("ID", "CRITICAL", "format", "tasks.md contains no parseable tasks", "no '- [ ] T### ' lines", "Regenerate tasks.md")
    seq = [t["id"] for t in tasks]
    for i, tid in enumerate(seq, 1):
        if tid != "T%03d" % i:
            o.add("ID", "HIGH", "format", "Task IDs are not sequential T001..TNNN at position %d" % i,
                  "expected T%03d, found %s" % (i, tid), "Renumber tasks sequentially and update references", [tid], "tasks.md:%d" % by_id[tid]["line"])
            break
    dups = {x for x in seq if seq.count(x) > 1}
    for d in sorted(dups):
        o.add("ID", "HIGH", "format", "Duplicate task ID %s" % d, "appears more than once", "Renumber", [d])
    for m in re.finditer(r"@@[\w-]+@@", tasks_txt):
        ln = tasks_txt[: m.start()].count("\n") + 1
        o.add("ID", "HIGH", "format", "Unresolved renumbering placeholder %s" % m.group(0), "tasks.md:%d" % ln, "Run the integrator/renumber step", [], "tasks.md:%d" % ln)

    # L2: dangling task references
    for line_no, line in enumerate(tasks_txt.split("\n"), 1):
        if TASK_RE.match(line):
            own = TASK_RE.match(line).group(1)
            body = TASK_RE.match(line).group(2)
        else:
            own, body = None, line
        for ref in set(re.findall(r"\bT\d{3}a?\b", body)):
            if ref not in by_id and ref != own:
                o.add("REF", "HIGH", "reference", "Reference to non-existent task %s" % ref, "tasks.md:%d" % line_no, "Point at the intended task or remove", [own] if own else [], "tasks.md:%d" % line_no)

    # L3: [P] conflicts within a phase (same concrete FILE, with an extension, in two [P] tasks)
    for ph in phases:
        seen = {}
        for tid in ph["tasks"]:
            t = by_id[tid]
            if not t["parallel"]:
                continue
            for p in set(x for x in t["paths"] if is_concrete_path(x) and x.startswith(("implementations/", "shared/", "infra/", "docs/", "specs/", ".github/", "scripts/")) and x.endswith(FILE_EXT)):
                if p in seen and seen[p] != tid:
                    doc_only = p.endswith(("CLAUDE.md", ".md"))
                    o.add("PAR", "LOW" if doc_only else "MEDIUM", "parallelism", "Two [P] tasks in Phase %d edit %s" % (ph["number"], p),
                          "%s and %s both list `%s`" % (seen[p], tid, p), "Drop [P] from one of them or split the file", [seen[p], tid])
                seen.setdefault(p, tid)

    # L4: story labels vs phase kind
    for ph in phases:
        for tid in ph["tasks"]:
            t = by_id[tid]
            if ph["story"] is not None and t["story"] != ph["story"]:
                o.add("LBL", "LOW", "format", "%s in the User Story %d phase has story label %s" % (tid, ph["story"], t["story"]),
                      t["text"][:120], "Use [US%d] on story-phase tasks" % ph["story"], [tid])
            if ph["story"] is None and t["story"] is not None:
                o.add("LBL", "LOW", "format", "%s has story label US%s outside a story phase" % (tid, t["story"]), t["text"][:120],
                      "Remove the story label from Setup/Foundational/Polish tasks", [tid])

    # L5: tasks without any file path (skip checkpoints and spikes, which legitimately have few)
    for t in tasks:
        if not t["paths"] and not re.search(r"Checkpoint|Confirm |Run |Independent clean-state|Tag the evaluated", t["text"]):
            o.add("PATH", "LOW", "format", "%s names no file path" % t["id"], t["text"][:140],
                  "Add the file path(s) the task creates or edits", [t["id"]])

    # L6: spliced sentences from appended clauses
    for t in tasks:
        for m in SPLICE_RE.finditer(t["text"]):
            ctx = t["text"][max(0, m.start() - 40): m.end() + 30]
            o.add("SPL", "LOW", "wording", "Appended clause is spliced without punctuation in %s" % t["id"], "...%s..." % ctx,
                  "Insert a period or semicolon before the clause", [t["id"]])
            break

    # L7: env-var names used in tasks/quickstart/plan that the environment contract does not define
    known = env_names(fd) | NON_ENV_ALLOW
    files = {"tasks.md": tasks_txt, "quickstart.md": read(fd / "quickstart.md"), "plan.md": read(fd / "plan.md")}
    unknown = {}
    for fname, txt in files.items():
        for ln, line in enumerate(txt.split("\n"), 1):
            for tok in TICK_RE.findall(line):
                if re.match(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$", tok) and tok not in known:
                    if re.match(r"^(FR|SC|SQS|HTTP|CI|MCP|SDK|API|IAM)_", tok):
                        continue
                    unknown.setdefault(tok, []).append("%s:%d" % (fname, ln))
    for tok, locs in sorted(unknown.items()):
        o.add("ENV", "MEDIUM", "consistency", "Name `%s` is used but not defined in contracts/environment.md" % tok,
              "seen at " + ", ".join(locs[:4]), "Add it to environment.md (or the framework-native table), or rename it to the contract name")

    # L8: metric names in metric/alarm tasks that observability.md does not define
    metrics = metric_names(fd)
    for t in tasks:
        if re.search(r"metric|EMF|alarm", t["text"], re.I):
            for tok in TICK_RE.findall(t["text"]):
                if re.match(r"^[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+$", tok) and tok not in metrics and tok not in NOT_METRICS:
                    o.add("MET", "MEDIUM", "consistency", "Metric-like name `%s` in %s is not in contracts/observability.md" % (tok, t["id"]),
                          t["text"][:140], "Use the contract metric name or add it to observability.md", [t["id"]])

    # L9: spike/decision references that research.md does not define
    research = read(fd / "research.md")
    spikes = set(re.findall(r"^\| (S\d+) \|", research, re.M))
    decisions = set(re.findall(r"^### (D\d+[a-z]?)\.", research, re.M))
    for t in tasks:
        for s in set(re.findall(r"\bS(\d{1,2})\b", t["text"])):
            if "S" + s not in spikes:
                o.add("SPK", "MEDIUM", "reference", "%s cites spike S%s, which research.md section 4 does not define" % (t["id"], s),
                      t["text"][:120], "Add the spike row to research.md or fix the reference", [t["id"]])
        for d in set(re.findall(r"\bD(\d{1,2}[a-z]?)\b", t["text"])):
            if "D" + d not in decisions and re.search(r"research", t["text"]):
                o.add("DEC", "LOW", "reference", "%s cites decision D%s, which research.md does not define" % (t["id"], d),
                      t["text"][:120], "Fix the reference", [t["id"]])

    # L10: contract files named in tasks that do not exist
    for t in tasks:
        for ref in set(re.findall(r"contracts/([\w\-]+\.(?:md|yaml|yml|json))", t["text"])):
            if not (fd / "contracts" / ref).exists():
                o.add("CON", "HIGH", "reference", "%s cites contracts/%s, which does not exist" % (t["id"], ref), t["text"][:120],
                      "Create the contract or fix the reference", [t["id"]])

    # L11: paths outside the plan's project structure
    plan = files["plan.md"]
    roots = {"implementations", "shared", "infra", "docs", "specs", ".github", "scripts"}
    for t in tasks:
        for p in t["paths"]:
            parts = p.split("/")
            if not is_concrete_path(p) or len(parts) < 2:
                continue
            if parts[0] in ("implementations", "specs", ".github", "docs", "scripts"):
                continue
            if parts[0] in ("shared", "infra"):
                seg = parts[1]
                if seg not in plan and seg + "/" not in plan:
                    o.add("STR", "MEDIUM", "consistency", "%s uses `%s`, whose directory is not in plan.md's project structure" % (t["id"], p),
                          t["text"][:120], "Add the directory to plan.md or fix the path", [t["id"]])
            elif parts[0] not in roots and parts[0] not in ("compose.yaml", "justfile"):
                pass

    # L12: stale terms
    for label, txt in files.items():
        for pat, why in STALE_TERMS:
            for m in re.finditer(pat, txt):
                ln = txt[: m.start()].count("\n") + 1
                o.add("STL", "MEDIUM", "drift", "Stale term %r in %s (%s)" % (m.group(0), label, why), "%s:%d" % (label, ln),
                      "Update to the current design", [], "%s:%d" % (label, ln))
    contracts_dir = fd / "contracts"
    for cf in sorted(contracts_dir.glob("*.md")) if contracts_dir.exists() else []:
        txt = read(cf)
        for pat, why in STALE_TERMS:
            for m in re.finditer(pat, txt):
                o.add("STL", "MEDIUM", "drift", "Stale term %r in %s (%s)" % (m.group(0), cf.name, why), cf.name, "Update", [], cf.name)

    # L13: unresolved placeholders in the core artifacts
    for fname in ("spec.md", "plan.md", "tasks.md", "research.md", "data-model.md", "quickstart.md"):
        txt = read(fd / fname)
        for m in re.finditer(r"TODO|TKTK|\?\?\?|\[NEEDS CLARIFICATION|<placeholder>", txt):
            ln = txt[: m.start()].count("\n") + 1
            o.add("PLC", "MEDIUM", "ambiguity", "Unresolved placeholder %r in %s" % (m.group(0), fname), "%s:%d" % (fname, ln),
                  "Resolve or remove", [], "%s:%d" % (fname, ln))

    # L14: requirement IDs never mentioned anywhere in tasks/plan/quickstart (hint only; coverage is judged by content)
    reqs = parse_requirements(fd)
    corpus = tasks_txt + files["plan.md"] + files["quickstart.md"]
    mentioned = {r for r in reqs if re.search(r"\b%s\b" % re.escape(r), corpus)}

    # L15: 200/202 webhook semantics stay consistent
    http = read(fd / "contracts" / "http-api.yaml")
    if re.search(r"'200':\s*\{description:\s*Duplicate", http):
        o.add("HTTP", "HIGH", "consistency", "http-api.yaml says a duplicate webhook delivery returns 200", "contracts/http-api.yaml /webhooks/github",
              "Duplicates get 202; the worker drops them (the handler never reads the database)")

    findings = o.items
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["id"]))
    doc = {
        "stats": {
            "tasks": len(tasks), "phases": len(phases), "requirements": len(reqs),
            "requirements_never_mentioned_by_id": len(set(reqs) - mentioned),
            "by_severity": {s: sum(1 for f in findings if f["severity"] == s) for s in order},
            "by_check": o.n,
        },
        "findings": findings,
    }
    text = json.dumps(doc, indent=1)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
