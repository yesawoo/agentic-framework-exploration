#!/usr/bin/env python3
"""Collect the facts a paused Spec Kit session needs to resume. Read-only; prints markdown.

Run from anywhere inside the repo: python3 .claude/skills/speckit-pause/gather.py
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def sh(*cmd, cwd=None):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def main():
    here = Path.cwd()
    root = sh("git", "rev-parse", "--show-toplevel", cwd=here)
    if not root:
        print("Not inside a git repository; cannot describe the worktree.")
        return
    root = Path(root)
    git_dir = sh("git", "rev-parse", "--absolute-git-dir", cwd=root)
    common = sh("git", "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=root)
    linked = bool(git_dir and common and Path(git_dir).resolve() != Path(common).resolve())
    branch = sh("git", "branch", "--show-current", cwd=root) or "(detached HEAD)"
    head = sh("git", "log", "-1", "--format=%h %s", cwd=root)
    upstream = sh("git", "rev-parse", "--abbrev-ref", "@{upstream}", cwd=root)
    status = sh("git", "status", "--short", cwd=root).split("\n") if sh("git", "status", "--short", cwd=root) else []
    untracked = [s[3:] for s in status if s.startswith("??")]
    changed = [s for s in status if not s.startswith("??")]
    worktrees = sh("git", "worktree", "list", cwd=root).split("\n")

    feat_file = root / ".specify" / "feature.json"
    feature_dir = None
    if feat_file.exists():
        try:
            feature_dir = json.loads(feat_file.read_text()).get("feature_directory")
        except Exception:
            pass
    fdir = root / feature_dir if feature_dir else None
    feature_name = Path(feature_dir).name if feature_dir else None

    out = []
    out.append("## Git")
    out.append("- Repo root / worktree path: `%s`" % root)
    out.append("- Worktree kind: %s" % ("linked worktree (git dir `%s`)" % git_dir if linked else "main checkout (not a linked worktree)"))
    out.append("- Branch: `%s`%s" % (branch, " (tracking `%s`)" % upstream if upstream else " (no upstream)"))
    out.append("- HEAD: %s" % head)
    out.append("- Worktrees: " + "; ".join("`%s`" % w.split()[0] + " " + " ".join(w.split()[1:]) for w in worktrees if w))
    out.append("- Modified/staged: %d file(s); untracked: %s" % (len(changed), ", ".join("`%s`" % u for u in untracked[:8]) or "none"))
    if feature_name and branch != feature_name:
        out.append("- WARNING: the constitution wants feature work on a branch named `%s`; the current branch is `%s`." % (feature_name, branch))
    if fdir and any(str(u).startswith(feature_dir.split("/")[0] + "/") for u in untracked):
        out.append("- WARNING: the feature directory is untracked, so it exists only in this working tree. Commit it or keep a copy before switching worktrees.")

    out.append("\n## Feature")
    if not fdir or not fdir.exists():
        out.append("- No active feature found (`.specify/feature.json` missing or points nowhere).")
    else:
        out.append("- Active feature directory: `%s`" % feature_dir)
        arts = []
        for name in ["spec.md", "plan.md", "tasks.md", "research.md", "data-model.md", "quickstart.md"]:
            p = fdir / name
            if p.exists():
                arts.append("%s (%d KB)" % (name, max(1, p.stat().st_size // 1024)))
        contracts = sorted(c.name for c in (fdir / "contracts").glob("*")) if (fdir / "contracts").exists() else []
        out.append("- Artifacts: " + ", ".join(arts))
        if contracts:
            out.append("- Contracts: " + ", ".join(contracts))
        tasks = fdir / "tasks.md"
        if tasks.exists():
            lines = tasks.read_text().split("\n")
            phase, per = None, {}
            for line in lines:
                m = re.match(r"^## (Phase \d+): (.*)$", line)
                if m:
                    phase = m.group(1) + ": " + m.group(2)[:60]
                    per[phase] = [0, 0]
                m = re.match(r"^- \[([ xX])\] (T\d{3}a?|@@[\w-]+@@)", line)
                if m and phase:
                    per[phase][1] += 1
                    if m.group(1) in "xX":
                        per[phase][0] += 1
            total = sum(v[1] for v in per.values())
            done = sum(v[0] for v in per.values())
            out.append("- Tasks: %d total, %d checked off, %d remaining across %d phases" % (total, done, total - done, len(per)))
            nxt = next((k for k, v in per.items() if v[0] < v[1]), None)
            if nxt:
                out.append("- First phase with unchecked tasks: %s (%d/%d done)" % (nxt, per[nxt][0], per[nxt][1]))
        lint = root / ".claude" / "workflows" / "lib" / "speckit_lint.py"
        if lint.exists():
            try:
                res = subprocess.run([sys.executable, str(lint), "--feature", str(fdir)], capture_output=True, text=True, timeout=60)
                st = json.loads(res.stdout)["stats"]
                out.append("- Deterministic lint now: %s" % json.dumps(st["by_severity"]))
            except Exception:
                out.append("- Deterministic lint: could not run")
        cons = root / ".specify" / "memory" / "constitution.md"
        if cons.exists():
            m = re.search(r"\*\*Version\*\*: ([\d.]+)", cons.read_text())
            if m:
                out.append("- Constitution version: %s" % m.group(1))

    out.append("\n## Tooling and state")
    wf = root / ".claude" / "workflows"
    if wf.exists():
        out.append("- Saved workflows: " + ", ".join(sorted(p.name for p in wf.glob("*.js"))))
    job = os.environ.get("CLAUDE_JOB_DIR")
    snaps = sorted(Path(job, "tmp").glob("snapshot-*")) if job and Path(job, "tmp").exists() else []
    if snaps:
        out.append("- Pre-fix snapshots: " + ", ".join("`%s`" % s for s in snaps[-3:]))
    print("\n".join(out))


if __name__ == "__main__":
    main()
