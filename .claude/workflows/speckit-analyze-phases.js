export const meta = {
  name: 'speckit-analyze-phases',
  description: 'Lint the Spec Kit artifacts deterministically, analyze each tasks.md phase from a small packet (Sonnet), verify HIGH/CRITICAL findings, then have Sonnet agents fix the artifacts and re-check, up to 4 fix cycles',
  whenToUse: 'After tasks.md exists for a Spec Kit feature and whole-feature analysis keeps looping. Args: {feature?: "001-agent-framework-comparison", phases?: [1,2,3], crossCutting?: true, fix?: true, maxIterations?: 4, fixLow?: false, fixLintLow?: true, model?: "sonnet", crossModel?: "opus", fixModel?: "sonnet", deferred?: ["..."], snapshotLabel?: "pre-fix"}. Set fix:false for a single read-only pass.',
  phases: [
    { title: 'Prepare', detail: 'run the deterministic linter and build per-phase packets (cheap model)' },
    { title: 'Snapshot', detail: 'copy the feature dir before any edit' },
    { title: 'Lint fix', detail: 'Sonnet fixes mechanical lint findings before any analysis tokens are spent' },
    { title: 'Analyze', detail: 'one read-only agent per phase reading its packet, plus a cross-cutting pass' },
    { title: 'Verify', detail: 'one skeptic per CRITICAL/HIGH finding' },
    { title: 'Fix', detail: 'Sonnet agents apply findings to the artifacts, one scope at a time' },
    { title: 'Integrate', detail: 'add any needed new tasks and renumber once per cycle' },
  ],
}

const cfg = args || {}
const FEATURE = cfg.feature || '001-agent-framework-comparison'
const MODEL = cfg.model || 'sonnet'
const CROSS_MODEL = cfg.crossModel || 'opus'
const FIX_MODEL = cfg.fixModel || 'sonnet'
const FIX = cfg.fix === undefined ? true : !!cfg.fix
const MAX_FIX_CYCLES = Math.max(1, Math.min(4, Number(cfg.maxIterations) || 4))
const FIX_LOW = !!cfg.fixLow
const FIX_LINT_LOW = cfg.fixLintLow === undefined ? true : !!cfg.fixLintLow
const ONLY = Array.isArray(cfg.phases) ? cfg.phases.map(Number) : null
const WITH_CROSS = cfg.crossCutting !== undefined ? !!cfg.crossCutting : !ONLY
const ROOT = '/Users/jamesthigpen/Development/agentic-framework-exploration'
const DIR = ROOT + '/specs/' + FEATURE
const LIB = ROOT + '/.claude/workflows/lib'
const SNAP_LABEL = cfg.snapshotLabel || 'pre-fix'

const DEFAULT_DEFERRED = [
  'smoke POST /internal/schedule side effects without an approval gate',
  'SNS alert topic has no email subscription',
  'digest scenario cannot seed PRs dated yesterday (GitHub cannot backdate)',
  'SC-001 and SC-002 trial counts and thresholds are not run by a task',
  'quickstart section 5 scenarios (safety, context-memory, mcp-server, tools, sandbox) have no tasks',
  'quickstart PAT scopes lack webhooks write and contents write',
  'FR-042 long-thread follow-up has no test',
  'S10/S11 spike ordering differs from plan.md phasing',
  'judge Bedrock client is not named',
  'scripts/ has no CI or CLAUDE.md',
  'scaffold CI pytest exits 5 with no tests',
  'work-item subject_key normalization for scheduled digests and null delivery_id (Phase 5)',
  'assorted LOW wording and sentence-splice issues in appended task clauses',
]
const BASE_DEFERRED = cfg.deferred || DEFAULT_DEFERRED

const FINDINGS = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['ready', 'ready_with_fixes', 'blocked'] },
    summary: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          severity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
          category: { type: 'string' },
          tasks: { type: 'array', items: { type: 'string' } },
          location: { type: 'string' },
          summary: { type: 'string' },
          evidence: { type: 'string' },
          recommendation: { type: 'string' },
        },
        required: ['id', 'severity', 'category', 'summary', 'evidence', 'recommendation'],
      },
    },
    coverage: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          requirement: { type: 'string' },
          covered: { type: 'string', enum: ['yes', 'partial', 'no'] },
          tasks: { type: 'array', items: { type: 'string' } },
          note: { type: 'string' },
        },
        required: ['requirement', 'covered'],
      },
    },
  },
  required: ['verdict', 'summary', 'findings'],
}

const VERDICT = {
  type: 'object',
  properties: {
    real: { type: 'boolean' },
    evidence: { type: 'string' },
    adjustedSeverity: { type: 'string', enum: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
  },
  required: ['real', 'evidence'],
}

const PREPARED = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    outDir: { type: 'string' },
    lintPath: { type: 'string' },
    lintCounts: {
      type: 'object',
      properties: {
        CRITICAL: { type: 'number' },
        HIGH: { type: 'number' },
        MEDIUM: { type: 'number' },
        LOW: { type: 'number' },
      },
      required: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
    },
    phases: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          number: { type: 'number' },
          title: { type: 'string' },
          story: { type: 'number' },
          firstTask: { type: 'string' },
          lastTask: { type: 'string' },
          taskCount: { type: 'number' },
          packet: { type: 'string' },
        },
        required: ['number', 'title', 'taskCount', 'packet'],
      },
    },
    crossPacket: { type: 'string' },
    error: { type: 'string' },
  },
  required: ['ok', 'outDir', 'lintPath', 'lintCounts', 'phases', 'crossPacket'],
}

const FIXED = {
  type: 'object',
  properties: {
    applied: {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } },
        required: ['id', 'note'],
      },
    },
    skipped: {
      type: 'array',
      items: { type: 'object', properties: { id: { type: 'string' }, reason: { type: 'string' } }, required: ['id', 'reason'] },
    },
    needsDecision: {
      type: 'array',
      items: { type: 'object', properties: { id: { type: 'string' }, question: { type: 'string' }, options: { type: 'string' } }, required: ['id', 'question'] },
    },
    newTasksNeeded: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          placeholder: { type: 'string' },
          insertAfter: { type: 'string' },
          text: { type: 'string' },
          forFinding: { type: 'string' },
        },
        required: ['placeholder', 'insertAfter', 'text'],
      },
    },
  },
  required: ['applied', 'skipped', 'needsDecision', 'newTasksNeeded'],
}

const INTEGRATED = {
  type: 'object',
  properties: {
    added: { type: 'array', items: { type: 'string' } },
    renumbered: { type: 'boolean' },
    totalTasks: { type: 'number' },
    sequentialOk: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['added', 'renumbered', 'totalTasks', 'sequentialOk'],
}

const SNAPSHOT = {
  type: 'object',
  properties: { path: { type: 'string' }, ok: { type: 'boolean' } },
  required: ['path', 'ok'],
}

function preamble(deferred, iteration, packet) {
  return [
    'You are running the speckit-analyze workflow, STRICTLY READ-ONLY: modify no files.',
    'Feature dir: ' + DIR + '. Repo root: ' + ROOT + '.',
    'Read ONLY your packet first: ' + packet + '. It contains everything your scope needs, already cut out of the feature files (tasks, story, requirements with candidate tasks, contracts, data-model and research excerpts, project structure, the constitution, and the deterministic linter findings). Do not read the full artifacts up front. Open a full file only to verify one specific suspected problem, and name the file in your evidence.',
    'Constitution (non-negotiable, violations of a MUST are CRITICAL) is inside the packet.',
    'This is analysis pass ' + iteration + '. The artifacts may have changed since earlier passes; the packet was regenerated for this pass.',
    'Severity: CRITICAL = constitution MUST violation, missing core artifact, or zero-coverage requirement that blocks baseline function; HIGH = conflicting/duplicate requirement, ambiguous security or performance attribute, untestable criterion, or a task that cannot be executed as written; MEDIUM = terminology drift, missing non-functional coverage, underspecified edge case; LOW = wording/style.',
    'Report only real, verified findings. Cite exact task IDs (T###) and quote the text as evidence. Do not hallucinate missing sections. Cap at 25 findings; summarize any overflow in the summary field.',
    'The linter already covers: task-ID integrity, dangling task references, [P] same-file conflicts, env-var and metric names vs contracts, stale terms, spliced sentences, placeholders. Do not report those.',
    'Known deferred items and items awaiting an owner decision; do NOT report them again: ' + deferred.map(function (d) { return '(' + d + ')' }).join('; ') + '.',
  ].join('\n')
}

function phasePrompt(p, deferred, iteration) {
  return [
    preamble(deferred, iteration, p.packet),
    '',
    'SCOPE: analyze ONLY Phase ' + p.number + ' ("' + p.title + '"), ' + p.taskCount + ' tasks' + (p.firstTask ? ' (' + p.firstTask + ' to ' + p.lastTask + ')' : '') + '. Do not report findings that belong to other phases.',
    '',
    'Check, for this phase only:',
    '1. Coverage: for the user story and FR/SC items this phase serves, is every requirement and acceptance scenario backed by a task with real content (not just an ID mention)? The packet gives BM25 candidate tasks per requirement as hints only. Fill the coverage array.',
    '2. Executability: can an LLM implement each task from its text alone? File paths present and consistent with the project structure; HTTP behavior matches contracts/http-api.yaml; queue messages match contracts/work-queue.md; tables and constraints match data-model.md.',
    '3. Dependencies: does the phase rely on anything not delivered by an earlier phase (forward references, missing prerequisites, tasks referencing files or components defined nowhere)? The packet lists one-line summaries of foundation and referenced tasks.',
    '4. Constitution principles that apply here (I test discipline, II scripted deploy, III repo conventions/CLAUDE.md, IV IaC, V secrets, VI observability, VII maintained clients, VIII clean-state verification, IX CI for new components).',
    '5. Tests: does the phase have contract-tier tests before or with implementation, and a checkpoint that verifies from a clean state?',
    '',
    'Set verdict to ready (no HIGH/CRITICAL), ready_with_fixes (only HIGH that are small text fixes), or blocked (CRITICAL or unresolvable HIGH). Lead the summary with the verdict reason.',
  ].join('\n')
}

function crossPrompt(packet, deferred, iteration) {
  return [
    preamble(deferred, iteration, packet),
    '',
    'SCOPE: cross-cutting consistency that no single phase owns. Do NOT analyze individual phase task contents in depth (other agents do that). The linter already checks ID sequence, dangling references, env-var and metric names, and stale terms mechanically.',
    '1. Semantic cross-references: for at least 12 T### references written in task text and in the Dependencies/Implementation Strategy sections of tasks.md, confirm they point at the intended task by content (read those sections of tasks.md directly; the task index in the packet gives one line per task).',
    '2. Artifact drift: plan.md, research.md, data-model.md, quickstart.md, and contracts/* against each other and against tasks.md (region us-east-1 default, Bedrock-only model access, migrate-task design, 202/200 webhook semantics, capability status values). Read the specific parts of those files you need to compare.',
    '3. Constitution: every principle I-IX against the plan and task set as a whole (every new component has CI and CLAUDE.md; teardown removes everything a deploy created; no secrets on disk; quickstart is an executable clean-state contract).',
    '4. Requirement coverage overall: every FR-### and SC-### maps to at least one task by content (the packet gives BM25 candidates); list any with zero coverage.',
    'Set verdict to ready, ready_with_fixes, or blocked.',
  ].join('\n')
}

async function prepare(iteration) {
  const p = await agent(
    [
      'Run two read-only commands and report their results. Do not edit any file.',
      'First determine an output directory: OUT="${CLAUDE_JOB_DIR:-$TMPDIR}/tmp/speckit-' + SNAP_LABEL + '-p' + iteration + '" (never /tmp), and mkdir -p it. Print its absolute path.',
      '1. python3 ' + LIB + '/speckit_lint.py --feature ' + DIR + ' --out "$OUT/lint.json" > /dev/null',
      '2. python3 ' + LIB + '/speckit_packets.py --feature ' + DIR + ' --out "$OUT" --lint "$OUT/lint.json"',
      'Then read "$OUT/index.json" and "$OUT/lint.json" (its stats.by_severity object holds the counts). Return: outDir (absolute), lintPath (absolute path of lint.json), lintCounts (CRITICAL/HIGH/MEDIUM/LOW), phases (copy each entry of index.json phases: number, title, story if not null, firstTask, lastTask, taskCount, packet), and crossPacket (index.json cross). If either command fails, return ok=false with the error text.',
    ].join('\n'),
    { label: 'prepare-p' + iteration, phase: 'Prepare', schema: PREPARED, model: 'haiku', effort: 'low' }
  )
  return p
}

async function analyze(items, deferred, iteration) {
  const results = await pipeline(
    items,
    function (it) {
      const label = (it.kind === 'phase' ? 'analyze-phase-' + it.p.number : 'analyze-cross-cutting') + '-i' + iteration
      const prompt = it.kind === 'phase' ? phasePrompt(it.p, deferred, iteration) : crossPrompt(it.packet, deferred, iteration)
      return agent(prompt, { label: label, phase: 'Analyze', model: it.kind === 'phase' ? MODEL : CROSS_MODEL, schema: FINDINGS })
    },
    function (analysis, it) {
      if (!analysis) return null
      const key = it.kind === 'phase' ? 'Phase ' + it.p.number : 'Cross-cutting'
      const serious = analysis.findings.filter(function (f) { return f.severity === 'CRITICAL' || f.severity === 'HIGH' })
      return parallel(serious.map(function (f) {
        return function () {
          return agent(
            [
              'You are an adversarial verifier. READ-ONLY: modify no files.',
              'Try to REFUTE this finding about ' + DIR + ' (' + key + '). Read the cited tasks in tasks.md and any artifact section needed, and decide whether the problem is real as stated. Default to real=false if you cannot confirm it from the files.',
              'Finding ' + f.id + ' [' + f.severity + ', ' + f.category + ']: ' + f.summary,
              'Cited tasks: ' + (f.tasks || []).join(', '),
              'Claimed evidence: ' + f.evidence,
              'Proposed fix: ' + f.recommendation,
              'Also set adjustedSeverity if the real severity differs.',
            ].join('\n'),
            { label: 'verify-' + key.replace(/\s+/g, '-') + '-' + f.id + '-i' + iteration, phase: 'Verify', schema: VERDICT }
          ).then(function (v) { return { id: f.id, verdict: v } })
        }
      })).then(function (vs) {
        return { analysis: analysis, key: key, kind: it.kind, verdicts: vs.filter(Boolean) }
      })
    }
  )

  return results.filter(Boolean).map(function (r) {
    const vmap = {}
    r.verdicts.forEach(function (v) { vmap[v.id] = v.verdict })
    const kept = []
    const dropped = []
    r.analysis.findings.forEach(function (f) {
      const v = vmap[f.id]
      if (v && v.real === false) {
        dropped.push({ id: f.id, summary: f.summary, why: v.evidence })
      } else {
        kept.push(Object.assign({}, f, v && v.adjustedSeverity ? { severity: v.adjustedSeverity, verified: true } : { verified: !!v }))
      }
    })
    const count = function (sev) { return kept.filter(function (f) { return f.severity === sev }).length }
    const blockers = count('CRITICAL') + count('HIGH')
    return {
      scope: r.key,
      kind: r.kind,
      verdict: blockers === 0 && r.analysis.verdict === 'blocked' ? 'ready_with_fixes' : (blockers === 0 ? 'ready' : r.analysis.verdict),
      summary: r.analysis.summary,
      counts: { CRITICAL: count('CRITICAL'), HIGH: count('HIGH'), MEDIUM: count('MEDIUM'), LOW: count('LOW') },
      findings: kept,
      droppedByVerification: dropped,
      coverage: r.analysis.coverage || [],
    }
  })
}

function fixable(f) {
  if (f.severity === 'CRITICAL' || f.severity === 'HIGH' || f.severity === 'MEDIUM') return true
  return FIX_LOW && f.severity === 'LOW'
}

function lintFixableCount(c) {
  return (c.CRITICAL || 0) + (c.HIGH || 0) + (c.MEDIUM || 0) + (FIX_LINT_LOW ? (c.LOW || 0) : 0)
}

const FIX_RULES = function (iteration) {
  return [
    'RULES (violating any of these is a failure):',
    '1. Edit ONLY files inside ' + DIR + ' (spec.md, plan.md, tasks.md, research.md, data-model.md, quickstart.md, contracts/*, checklists/*). Never touch .specify/, .claude/, the constitution, or any file outside that directory. Do not run git commands that change state, tofu, docker, or anything that deploys or spends money.',
    '2. Use the Edit tool for small precise edits and re-read the surrounding text first. Other agents edit these same files one after another, so ALWAYS re-read the current text before editing; if a finding is already resolved, list it under skipped with reason "already resolved".',
    '3. tasks.md format: every task stays "- [ ] T### [P?] [US#?] description with file paths". Do NOT delete, reorder, split, or renumber existing tasks, and do NOT add task lines yourself. Fold changes into existing task text (keep each edit a complete sentence with proper punctuation; no run-on splices). If a genuinely new task is required, report it under newTasksNeeded with a unique placeholder like @@fix-' + iteration + '-a@@, the existing task ID it should follow (insertAfter), and the full task text (the integrator will insert and renumber).',
    '4. Keep artifacts consistent: when a change alters a name, status code, env var, metric, table, or contract, update every artifact that states it (tasks.md, plan.md, research.md, data-model.md, quickstart.md, contracts/*) in the same pass.',
    '5. Do not guess owner decisions. If a finding needs a product, cost, or design choice that the artifacts and constitution do not settle, do not edit for it; report it under needsDecision with a concise question and your recommended option.',
    '6. Do not introduce work beyond what a finding requires (YAGNI). Do not fix findings outside your list.',
  ].join('\n')
}

function fixPrompt(scope, findings, iteration) {
  return [
    'You are fixing Spec Kit artifacts for the feature in ' + DIR + '. Repo root: ' + ROOT + '. This is fix cycle ' + iteration + ' of at most ' + MAX_FIX_CYCLES + '.',
    'Scope of the findings below: ' + scope + '. Read the constitution at ' + ROOT + '/.specify/memory/constitution.md before editing; it is authoritative and you must never edit it.',
    '',
    FIX_RULES(iteration),
    '',
    'FINDINGS TO FIX (apply each recommendation, adapting it to the current text):',
    JSON.stringify(findings.map(function (f) {
      return { id: f.id, severity: f.severity, tasks: f.tasks, summary: f.summary, evidence: f.evidence, recommendation: f.recommendation }
    }), null, 1),
    '',
    'Return applied (with the files you edited), skipped (with reasons), needsDecision, and newTasksNeeded.',
  ].join('\n')
}

function lintFixPrompt(lintPath, iteration) {
  return [
    'You are fixing mechanical consistency problems in the Spec Kit artifacts for ' + DIR + '. Repo root: ' + ROOT + '. Fix cycle ' + iteration + ' of at most ' + MAX_FIX_CYCLES + '.',
    'A deterministic linter wrote its findings to ' + lintPath + ' (JSON, key "findings"). Fix every finding with severity CRITICAL, HIGH or MEDIUM' + (FIX_LINT_LOW ? ', and LOW' : '') + '. After editing, you may re-run: python3 ' + LIB + '/speckit_lint.py --feature ' + DIR + ' and confirm the findings you fixed are gone (that command only reads files).',
    'Typical fixes: L-SPL (spliced sentence: put a period, or a semicolon where the clause continues, before the appended clause and capitalize correctly, without changing meaning); L-PAR ([P] on two tasks that edit the same file: remove [P] from the later task); L-ENV/L-MET (rename to the contract name, or add the name to contracts/environment.md or observability.md when the name is legitimately new); L-STL (update the stale term to the current design); L-SPK/L-CON (fix the reference or add the missing row/file); L-ID/L-REF (repair IDs and references; do not renumber unless required).',
    '',
    FIX_RULES(iteration),
    '',
    'Return applied (one entry per finding id or group), skipped (with reasons), needsDecision, and newTasksNeeded.',
  ].join('\n')
}

function integratePrompt(newTasks, iteration) {
  return [
    'You are the integrator for Spec Kit task changes in ' + DIR + '/tasks.md. Fix cycle ' + iteration + '. Edit only that file (and T### references in other artifacts of the feature dir). Do not run git commands that change state.',
    'Insert each new task below immediately after the task named in insertAfter (a T### ID as it currently exists), as a single line "- [ ] <placeholder> <text>" keeping the checkbox format (the text already contains any [P]/[US#] labels).',
    'Then renumber ALL tasks sequentially T001..TNNN in file order and rewrite every T### cross-reference in the whole file (task bodies, Dependencies, Implementation Strategy, Scope notes) via a mapping. Proven algorithm (use a python script, not manual edits): ids = every line matching ^- \\[ \\] (T\\d{3}a?|@@[\\w-]+@@)(?=\\s) in file order; assert unique; mapping old-or-placeholder -> "T%03d" by position; then re.sub(r"\\bT\\d{3}a?\\b|@@[\\w-]+@@", lambda m: mapping.get(m.group(0), m.group(0)), text). Placeholders may also appear inside other tasks as references and are replaced by the same mapping.',
    'Finally verify: no "@@" remains, IDs are sequential with no gaps or duplicates, and the task count equals the previous count plus the number added. Also grep the other artifacts in the feature dir (plan.md, research.md, quickstart.md, contracts/*, data-model.md) for T### references and update them with the same mapping. You may run ' + LIB + '/speckit_lint.py --feature ' + DIR + ' (read-only) to confirm there are no ID or reference findings.',
    'New tasks to insert:',
    JSON.stringify(newTasks, null, 1),
  ].join('\n')
}

phase('Prepare')
let prep = await prepare(1)
if (!prep || !prep.ok) {
  log('Prepare failed (' + (prep && prep.error ? prep.error : 'no result') + '); aborting.')
  return { error: 'prepare failed', detail: prep }
}
log('Lint: ' + JSON.stringify(prep.lintCounts) + ' (deterministic, no model spent)')

let allPhases = prep.phases
if (ONLY) allPhases = allPhases.filter(function (p) { return ONLY.indexOf(p.number) >= 0 })

let snapshotPath = null
if (FIX) {
  phase('Snapshot')
  const snap = await agent(
    [
      'Make a backup copy of the feature directory before it is edited. Read-only with respect to the repo.',
      'Source: ' + DIR + '. Destination: a NEW directory named snapshot-' + SNAP_LABEL + ' under $CLAUDE_JOB_DIR/tmp if that variable is set, otherwise under $TMPDIR (never /tmp). If the destination already exists, append -2, -3, and so on. Use cp -R. Verify the copy has the same file count as the source and return its absolute path.',
    ].join('\n'),
    { label: 'snapshot', phase: 'Snapshot', schema: SNAPSHOT, model: 'haiku', effort: 'low' }
  )
  if (!snap || !snap.ok) {
    log('Snapshot failed; refusing to edit artifacts without a backup. Rerun, or pass fix:false for analysis only.')
    return { error: 'snapshot failed', snapshot: snap }
  }
  snapshotPath = snap.path
  log('Snapshot saved at ' + snapshotPath)
}

const history = []
const ownerDecisions = []
const newTaskLog = []
const lintLog = []
let deferred = BASE_DEFERRED.slice()
let scopes = { phases: allPhases.map(function (p) { return p.number }), cross: WITH_CROSS }
let converged = false
let stalled = false
let prevFixable = null
let nonImproving = 0
let lastReport = []

log('Scopes: ' + scopes.phases.join(', ') + (WITH_CROSS ? ' + cross-cutting' : '') + '; fix=' + FIX + '; at most ' + MAX_FIX_CYCLES + ' fix cycle(s); phase analyzers on ' + MODEL + ', cross-cutting on ' + CROSS_MODEL)

for (let i = 1; i <= MAX_FIX_CYCLES + 1; i++) {
  const isFinalCheck = i === MAX_FIX_CYCLES + 1

  if (i > 1) {
    phase('Prepare')
    prep = await prepare(i)
    if (!prep || !prep.ok) { log('Prepare failed on pass ' + i + '; stopping.'); break }
  }

  // Mechanical lint findings are fixed first so analysis agents never spend tokens on them.
  if (FIX && !isFinalCheck && lintFixableCount(prep.lintCounts) > 0) {
    phase('Lint fix')
    const before = prep.lintCounts
    const lf = await agent(lintFixPrompt(prep.lintPath, i), { label: 'lint-fix-c' + i, phase: 'Lint fix', model: FIX_MODEL, schema: FIXED })
    if (lf) {
      lf.needsDecision.forEach(function (d) { ownerDecisions.push(Object.assign({ scope: 'Lint', pass: i }, d)) })
      const again = await prepare(i)
      if (again && again.ok) prep = again
      lintLog.push({ pass: i, before: before, after: prep.lintCounts, applied: lf.applied.length, skipped: lf.skipped.length })
      log('Lint fix: ' + lf.applied.length + ' applied, ' + lf.skipped.length + ' skipped; lint now ' + JSON.stringify(prep.lintCounts))
    }
  }

  const items = []
  prep.phases.filter(function (p) { return scopes.phases.indexOf(p.number) >= 0 }).forEach(function (p) { items.push({ kind: 'phase', p: p }) })
  if (scopes.cross) items.push({ kind: 'cross', packet: prep.crossPacket })
  if (items.length === 0) { converged = true; break }

  log((isFinalCheck ? 'Final confirmation pass' : 'Pass ' + i) + ': analyzing ' + items.length + ' scope(s)')
  phase('Analyze')
  const report = await analyze(items, deferred, i)
  lastReport = lastReport.filter(function (old) { return !report.some(function (r) { return r.scope === old.scope }) }).concat(report)

  const analysisFixable = report.reduce(function (n, r) { return n + r.findings.filter(fixable).length }, 0)
  const lintFixable = lintFixableCount(prep.lintCounts)
  const totalFixable = analysisFixable + lintFixable
  history.push({
    pass: i,
    lint: prep.lintCounts,
    scopes: report.map(function (r) { return { scope: r.scope, verdict: r.verdict, counts: r.counts } }),
    fixable: totalFixable,
  })

  if (!FIX) break
  if (totalFixable === 0) { converged = true; log('No fixable findings remain; converged.'); break }
  if (isFinalCheck) { log('Fix-cycle limit reached with ' + totalFixable + ' fixable finding(s) still open.'); break }

  if (prevFixable !== null && totalFixable >= prevFixable) nonImproving++
  else nonImproving = 0
  prevFixable = totalFixable
  if (nonImproving >= 2) {
    stalled = true
    log('Fixable findings did not decrease for two passes in a row (' + totalFixable + '); stopping to avoid churn.')
    break
  }

  phase('Fix')
  const touched = []
  const newTasks = []
  const passRecord = { pass: i, applied: 0, skipped: 0 }
  const withWork = report.filter(function (r) { return r.findings.filter(fixable).length > 0 })
  // Sequential on purpose: agents edit the same artifact files, and concurrent edits can clobber each other.
  for (let k = 0; k < withWork.length; k++) {
    const r = withWork[k]
    const todo = r.findings.filter(fixable)
    const out = await agent(fixPrompt(r.scope, todo, i), { label: 'fix-' + r.scope.replace(/\s+/g, '-') + '-c' + i, phase: 'Fix', model: FIX_MODEL, schema: FIXED })
    if (!out) { log('Fixer for ' + r.scope + ' returned nothing; its findings stay open.'); continue }
    touched.push(r.scope)
    passRecord.applied += out.applied.length
    passRecord.skipped += out.skipped.length
    out.needsDecision.forEach(function (d) {
      ownerDecisions.push(Object.assign({ scope: r.scope, pass: i }, d))
      const f = todo.find(function (x) { return x.id === d.id })
      deferred.push('awaiting owner decision: ' + (f ? f.summary : d.id))
    })
    out.newTasksNeeded.forEach(function (n) { newTasks.push(n) })
    log(r.scope + ': applied ' + out.applied.length + ', skipped ' + out.skipped.length + ', needs decision ' + out.needsDecision.length + ', new tasks ' + out.newTasksNeeded.length)
  }
  history[history.length - 1].fix = passRecord

  if (newTasks.length > 0) {
    phase('Integrate')
    const integ = await agent(integratePrompt(newTasks, i), { label: 'integrate-c' + i, phase: 'Integrate', model: FIX_MODEL, schema: INTEGRATED })
    newTaskLog.push({ pass: i, requested: newTasks.length, result: integ })
    if (!integ || !integ.sequentialOk) log('Integrator did not confirm sequential task IDs; the next pass lint will flag any damage.')
    else log('Integrator added ' + integ.added.length + ' task(s); tasks.md now has ' + integ.totalTasks + ' tasks.')
  }

  // Next pass: re-analyze only the scopes that were edited, plus cross-cutting. Packets are rebuilt at the top of the loop.
  const wanted = touched.filter(function (s) { return s.indexOf('Phase ') === 0 }).map(function (s) { return Number(s.replace('Phase ', '')) })
  scopes = { phases: wanted, cross: WITH_CROSS || touched.length > 0 }
  if (wanted.length === 0 && !scopes.cross) { converged = true; break }
}

const final = lastReport.map(function (r) {
  return { scope: r.scope, verdict: r.verdict, counts: r.counts, findings: r.findings, droppedByVerification: r.droppedByVerification }
})

return {
  feature: FEATURE,
  mode: FIX ? 'analyze-and-fix' : 'analyze-only',
  converged: converged,
  stalled: stalled,
  snapshot: snapshotPath,
  finalLint: prep && prep.lintCounts,
  lintPath: prep && prep.lintPath,
  history: history,
  lintFixes: lintLog,
  ownerDecisionsNeeded: ownerDecisions,
  newTaskIntegration: newTaskLog,
  remaining: final,
  note: FIX
    ? 'Edits were applied to the Spec Kit artifacts by ' + FIX_MODEL + ' agents. The pre-edit copy is at the snapshot path. Review the diff against it, answer ownerDecisionsNeeded, then rerun (optionally with args.phases) to recheck.'
    : 'Read-only. Fix findings, then rerun to recheck.',
}
