---
name: "speckit-pause"
description: "Produce a paste-ready handoff prompt that names the Spec Kit feature, worktree, branch, progress, decisions, and next step so a fresh session can resume exactly where this one stopped."
argument-hint: "Optional note about what to emphasize in the handoff"
compatibility: "Requires spec-kit project structure with .specify/ directory"
metadata:
  author: "local"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

Consider the user input above (an optional emphasis for the handoff) before proceeding.

## Goal

Write one self-contained prompt the user can paste into a new session to continue this work. It must state which spec and which worktree and branch the work lives in, what has been done, what is decided, what is open, and the exact next step. This skill is read-only: do not edit files, commit, switch branches, or run anything that deploys.

## Steps

1. **Gather the facts deterministically.** Run `python3 .claude/skills/speckit-pause/gather.py` from the repo root. It reports the worktree path, whether it is a linked worktree or the main checkout, the branch and upstream, HEAD, all worktrees, untracked and modified files, the active feature directory (from `.specify/feature.json`), which artifacts exist, task progress per phase, the deterministic lint counts, the constitution version, saved workflows, and any pre-fix snapshots. Treat its warnings (branch does not match the feature name, feature directory untracked) as things the next session must know.

2. **Add what only this conversation knows.** From the conversation so far, capture, in a few plain lines each:
   - **Goal**: what the user is trying to accomplish with this feature right now.
   - **Done**: what was completed this session (edits applied, workflows run, findings fixed), with the file paths and task IDs or finding IDs where they matter.
   - **Decisions made**: choices the user confirmed (for example region, model tiering, design choices), each with the reason if it was given, so the next session does not reopen them.
   - **Open decisions**: questions still waiting on the user, with a recommended option if one was offered.
   - **Deferred on purpose**: items intentionally not being fixed, so they are not re-reported.
   - **In flight**: anything running or half-done (a background workflow, an unapplied edit, a snapshot to review). Say plainly if nothing is running.
   - **Next step**: the single most useful next action, and the command to run it if there is one.
   Do not invent state. If you are unsure whether something finished, say it is unverified.

3. **Write the handoff prompt** in one fenced block the user can copy, using this shape and keeping it under about 70 lines:

   ```text
   Resume work on the Spec Kit feature <feature-name>.

   WHERE
   - Worktree: <absolute path> (<main checkout | linked worktree>)
   - Branch: <branch> (<upstream or none>); HEAD <sha subject>
   - Feature dir: <specs/...>; artifacts: <list>
   - Git caveats: <untracked/branch-name warnings, or "none">

   STATE
   - Tasks: <N> total, <M> checked; next unchecked phase: <phase>
   - Lint: <counts>; last analysis: <what was run and the result>
   - Constitution: v<version> at .specify/memory/constitution.md (authoritative)

   DONE THIS SESSION
   - ...

   DECISIONS (do not reopen)
   - ...

   OPEN QUESTIONS
   - ...

   DEFERRED ON PURPOSE
   - ...

   IN FLIGHT
   - ...

   FIRST ACTIONS
   1. Run `git rev-parse --show-toplevel && git branch --show-current` and confirm they match WHERE; if not, stop and tell me.
   2. Run `python3 .claude/skills/speckit-pause/gather.py` to refresh the facts above.
   3. <the next step, with its command>

   RULES
   - The constitution wins over any other guidance.
   - Do not deploy, spend money, or write to GitHub without my approval.
   - Edit only files under <feature dir> unless I say otherwise.
   ```

4. **Say what is not captured.** After the block, add one or two lines listing anything the handoff cannot carry (for example unsaved conversation-only context, or work that exists only in this untracked working tree) and, if the feature directory is untracked, suggest committing it on the feature branch or copying it before the worktree changes. Offer, do not perform, that action.

## Rules

- Read-only: the only command you run is the gather script (and read-only git or file reads if a fact is missing).
- Use the user's own words for decisions where possible, and never attribute a decision the user did not make.
- Refer to the user with they/them if a pronoun is needed. Do not include secrets, tokens, or credential values; name the variable or secret instead.
- Keep it short: the next session will re-read the artifacts itself, so point at files instead of pasting their contents.
