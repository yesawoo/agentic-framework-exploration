#!/usr/bin/env python3
"""Build small per-phase analysis packets so agents read one file instead of six large ones.

Usage: speckit_packets.py --feature specs/001-... --out DIR [--lint lint.json]
Writes DIR/phase-N.md for every phase in tasks.md, DIR/cross.md, and DIR/index.json.
Deterministic and read-only with respect to the feature directory.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from speckit_common import (  # noqa: E402
    BM25, parse_requirements, parse_stories, parse_tasks, read, sections,
)

TASK_SUMMARY_CHARS = 150
DEP_SUMMARY_CHARS = 200
DECISION_CAP = 1800
SECTION_CAP = 2600


def clip(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def task_line(t, full=False):
    body = t["text"] if full else clip(t["text"], TASK_SUMMARY_CHARS)
    return "- %s %s" % (t["id"], body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lint")
    a = ap.parse_args()
    fd = Path(a.feature)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tasks, phases = parse_tasks(fd)
    by_id = {t["id"]: t for t in tasks}
    reqs = parse_requirements(fd)
    stories = parse_stories(fd)
    constitution = read(fd.parent.parent / ".specify" / "memory" / "constitution.md")
    plan = read(fd / "plan.md")
    research = read(fd / "research.md")
    datamodel = read(fd / "data-model.md")
    contracts = {p.name: read(p) for p in sorted((fd / "contracts").glob("*")) if p.is_file()}
    lint = json.loads(read(a.lint)) if a.lint and Path(a.lint).exists() else {"findings": []}

    tree = re.search(r"```text\n(implementations/.*?)```", plan, re.S)
    structure = tree.group(1).strip() if tree else "(project structure block not found in plan.md)"
    decisions = sections(research, r"^### (D\d+[a-z]?)\. ")
    spike_rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| (S\d+) \|.*$", research, re.M)}
    tbl_sections = {}
    # data-model sections keyed by every backticked table name in the heading
    cur_names, buf = [], []
    for line in datamodel.split("\n"):
        if line.startswith("### ") or line.startswith("## "):
            for n in cur_names:
                tbl_sections[n] = "\n".join(buf).strip()
            cur_names = re.findall(r"`(\w+)`", line) if line.startswith("### ") else []
            buf = [line]
        else:
            buf.append(line)
    for n in cur_names:
        tbl_sections[n] = "\n".join(buf).strip()

    bm25 = BM25([t["text"] for t in tasks])
    cands = {}
    for rid, rtext in reqs.items():
        cands[rid] = [(tasks[i]["id"], s) for i, s in bm25.top(rid + " " + rtext, 3)]

    foundation = [t for t in tasks if t["phase"] in (1, 2)]
    idx = {"phases": [], "tasks": len(tasks), "requirements": len(reqs)}

    def relevant_lint(ids):
        keep = [f for f in lint["findings"] if set(f.get("tasks", [])) & set(ids)]
        if not keep:
            return "(none)"
        return "\n".join("- [%s] %s %s" % (f["severity"], f["id"], f["summary"]) for f in keep[:40])

    common_head = (
        "# Analysis packet\n\n"
        "This packet replaces reading the whole artifact set. It contains everything this scope needs, cut out of the "
        "feature files. Open a full artifact only to verify one specific suspected problem, and say so in the evidence. "
        "The deterministic linter already checks task-ID integrity, dangling task refs, [P] same-file conflicts, "
        "env-var and metric names against contracts/, stale terms, and spliced sentences; do not re-report those.\n"
    )

    for ph in phases:
        ids = ph["tasks"]
        ptasks = [by_id[i] for i in ids]
        text = "\n".join(t["text"] for t in ptasks)
        story_text = stories.get(ph["story"], "") if ph["story"] else ""
        cited = sorted(set(re.findall(r"\b(?:FR|SC)-\d{3}\b", story_text + "\n" + text)))
        # requirements the story serves: cited ones plus BM25 matches whose top task is in this phase
        mine = set(cited)
        for rid, cs in cands.items():
            if cs and cs[0][0] in ids:
                mine.add(rid)
        refs = sorted(set(re.findall(r"\bT\d{3}\b", text)) - set(ids))
        contract_names = sorted({c for c in contracts if c in text or ("contracts/" + c) in text})
        table_names = sorted({n for n in tbl_sections if re.search(r"`%s`|\b%s\b" % (n, n), text)})
        dec_names = sorted(set(re.findall(r"\bD\d+[a-z]?\b", text)) & set(decisions))
        spike_names = sorted(set(re.findall(r"\bS\d{1,2}\b", text)) & set(spike_rows))

        parts = [common_head]
        parts.append("## Scope\nPhase %d: %s\nTasks %s to %s (%d tasks). Feature: %s\n" % (ph["number"], ph["title"], ids[0] if ids else "-", ids[-1] if ids else "-", len(ids), fd.name))
        parts.append("## Tasks in this phase (full text)\n" + "\n".join(task_line(t, True) for t in ptasks) + "\n")
        if story_text:
            parts.append("## User story (spec.md)\n" + story_text + "\n")
        if mine:
            parts.append("## Requirements this phase serves (spec.md), with BM25 candidate tasks\n" + "\n".join(
                "- %s: %s\n    candidates: %s" % (r, clip(reqs.get(r, "(not found in spec.md)"), 320), ", ".join("%s(%s)" % c for c in cands.get(r, [])) or "none")
                for r in sorted(mine)) + "\n")
        dep = {i for i in refs if i in by_id}
        if ph["number"] > 2:
            dep |= {t["id"] for t in foundation}
        dep -= set(ids)
        if dep:
            parts.append("## Foundation and referenced tasks (one-line summaries, for dependency checks)\n" + "\n".join(
                task_line(by_id[i]) for i in sorted(dep)) + "\n")
        if contract_names:
            parts.append("## Contracts named by these tasks (full text)\n" + "\n\n".join("### contracts/%s\n%s" % (c, contracts[c]) for c in contract_names) + "\n")
        if table_names:
            parts.append("## data-model.md sections for tables these tasks mention\n" + "\n\n".join(clip_block(tbl_sections[n], SECTION_CAP) for n in table_names) + "\n")
        if dec_names or spike_names:
            parts.append("## research.md items cited\n" + "\n\n".join(
                [clip_block(decisions[d], DECISION_CAP) for d in dec_names] + [spike_rows[s] for s in spike_names]) + "\n")
        parts.append("## Project structure (plan.md)\n```text\n" + structure + "\n```\n")
        parts.append("## Constitution (authoritative)\n" + constitution + "\n")
        parts.append("## Linter findings already detected for these tasks (do not re-report)\n" + relevant_lint(ids) + "\n")
        (out / ("phase-%d.md" % ph["number"])).write_text("\n".join(p for p in parts if p), encoding="utf-8")
        idx["phases"].append({"number": ph["number"], "title": ph["title"], "story": ph["story"], "firstTask": ids[0] if ids else "", "lastTask": ids[-1] if ids else "", "taskCount": len(ids), "packet": str(out / ("phase-%d.md" % ph["number"]))})

    # Cross-cutting packet
    inv = "\n".join("- %s: %s | candidates: %s" % (r, clip(t, 200), ", ".join("%s(%s)" % c for c in cands[r]) or "none") for r, t in reqs.items())
    tindex = "\n".join("- %s (P%s%s) %s" % (t["id"], t["phase"], " [P]" if t["parallel"] else "", clip(t["text"], 110)) for t in tasks)
    cross = [common_head,
             "## Scope\nCross-cutting consistency for %s: %d tasks, %d requirements.\n" % (fd.name, len(tasks), len(reqs)),
             "## Task index (one line per task)\n" + tindex + "\n",
             "## Requirement inventory (FR/SC) with BM25 candidate tasks\n" + inv + "\n",
             "## Contracts (full text)\n" + "\n\n".join("### contracts/%s\n%s" % (c, contracts[c]) for c in contracts if c.endswith(".md") or c.endswith(".yaml")) + "\n",
             "## Project structure (plan.md)\n```text\n" + structure + "\n```\n",
             "## Constitution (authoritative)\n" + constitution + "\n",
             "## All linter findings (do not re-report)\n" + "\n".join("- [%s] %s %s" % (f["severity"], f["id"], f["summary"]) for f in lint["findings"][:80]) + "\n"]
    (out / "cross.md").write_text("\n".join(cross), encoding="utf-8")
    idx["cross"] = str(out / "cross.md")
    (out / "index.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")
    sizes = {p.name: p.stat().st_size for p in sorted(out.glob("*.md"))}
    print(json.dumps({"index": str(out / "index.json"), "packets": sizes, "approxTokens": {k: v // 4 for k, v in sizes.items()}}, indent=1))


def clip_block(text, n):
    return text if len(text) <= n else text[: n - 1] + "…"


if __name__ == "__main__":
    main()
