---
name: skill-evolver
description: |
  Autonomous skill evolution engine. Use when the user wants to improve, optimize,
  or evolve a Claude Code skill through iterative A/B testing. Trigger on phrases like
  "进化这个skill", "优化skill", "自动改进", "跑进化", "evolve skill", "improve skill automatically".
  Also use when user wants to run an outer optimization loop over skill prompts.
---

# Skill Evolver

Autonomous outer-loop optimization for Claude Code skills.

Framework tools are at `${CLAUDE_PLUGIN_ROOT}/evolver/` — use this prefix for all framework commands.
User project paths (`targets/`, `experiments/`, evals) are relative to the user's project root.

Three principles:
- **Atomic changes**: Modify one thing → Verify → Keep or Discard. If score goes up, you know why.
- **Filesystem as memory**: Proposer reads full source, scores, and traces — never compresses history.
- **A/B comparison**: with-skill vs without-skill, mechanical grading only. No subjective judgment.

## Workflow

```
BASELINE → LOOP { ANALYZE → PROPOSE → APPLY → VERIFY → KEEP/REVERT → LOG }
```
Core cycle: read evidence, propose one atomic change, verify mechanically, keep or revert. Full details in Step 2 below.
Steps: ANALYZE → READ → PROPOSE → APPLY → RUN all evals → GRADE → KEEP or REVERT → LOG

## Step 0: Load Target Config

Read `targets/<target>.yaml`:

```yaml
project_root: /path/to/project
skills:
  - name: <id>           # skill identifier
    path: skills/<id>    # relative to project_root
    evals_dir: evals/<id>  # must contain grade.py + evals.json
settings:
  max_iterations: 20     # omit for unbounded
  min_delta: 0.01        # minimum score delta to keep
  auto_revert: true      # revert on no improvement
  guard: null            # optional regression test command
```

The evals directory must contain:
- `grade.py` — module with `grade(project_root: Path, label: str) -> GradingResult`
- `evals.json` — eval definitions (see schema below)
- `iteration-N/` — optional fixture directories

For L3 assertion design guidance, see `references/l3-assertion-patterns.md` in this skill.
Good L3 assertions discriminate — with-skill passes, without-skill fails. If both pass at 100%,
the assertion is dead weight.

### evals.json Schema

```json
{
  "skills": {
    "<id>": {
      "skill_path": "skills/<id>",
      "evals": [{
        "id": "eval-id", "name": "描述", "iteration": 1,
        "prompt": "给 agent 的执行指令...",
        "project_dirs": {
          "with_skill": "/tmp/test-with",
          "without_skill": "/tmp/test-without"
        }
      }]
    }
  }
}
```
- `prompt`: injected into subagent prompt template
- `project_dirs.*`: isolated working directories for each track
- `iteration`: fixture version, increment when prompts/grading change

## Step 1: Establish Baseline

Before any changes, run all evals for the target skill and record baseline scores.

### 1.1 Prepare

For each eval in evals.json:
1. Create project directories: `mkdir -p {project_dir}/outputs`
2. If fixtures exist (`iteration-{N}/`), copy them to the project dir

### 1.2 Execute

Spawn agents per the Subagent Protocol (see below). Run all evals in parallel.

### 1.3 Grade

After all agents complete, run grading for each track:
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py grade {evals_dir} {project_dir} {label}
```
Or directly: `python3 {evals_dir}/grade.py` if it supports CLI invocation.

### 1.4 Compute Score

For each eval, compute per-level pass rates from `grading.json`:
```
L1 = passed_L1 / total_L1
L2 = passed_L2 / total_L2
L3 = passed_L3 / total_L3
eval_score = L1 * 0.2 + L2 * 0.3 + L3 * 0.5
```

**Multi-eval aggregation**: average the per-eval aggregate scores:
```
overall_score = mean(eval_scores)
delta = overall_with_score - overall_without_score
```

If `delta < 0.05`, the eval assertions lack discriminative power — bare Claude can almost match the skill. Consider adding more L3 assertions before evolving.

L3 (content quality) gets higher weight to combat Goodhart — we don't want the optimizer to sacrifice quality for structural compliance.

### 1.5 Audit Assertion Discrimination

Before entering the evolution loop, audit every assertion for discriminatory power.
An assertion that passes 100% in BOTH tracks (with AND without skill) is dead weight — it costs grading time but provides zero signal.

**Audit procedure**:

For each assertion in the baseline grading results:
1. Compare pass rate in with_skill vs without_skill
2. Classify:
   - **Strong discriminator**: passes with-skill, fails without-skill → keep, valuable
   - **Weak discriminator**: passes both, but with-skill passes more consistently (>20% gap) → keep but monitor
   - **Non-discriminator**: passes 100% in BOTH tracks → flag for replacement
   - **Anti-discriminator**: fails with-skill, passes without-skill → the skill may be hurting

**Output an audit summary**:

```
Assertion Audit (<N> total):
  Strong:   <K> — clearly differentiate skill value
  Weak:     <W> — marginal, monitor
  Dead:     <D> — pass 100% both tracks, need replacement
  Reversed: <R> — skill makes it worse (investigate)
```

**Action on dead assertions**:
- If dead assertions are L1 or L2: the skill's structural output is solid. Accept and move on.
- If dead assertions are L3: red flag. The L3 assertions aren't measuring content quality. Read `references/l3-assertion-patterns.md` for better design patterns, then propose replacement assertions BEFORE starting evolution.
- If >30% of all assertions are dead: the eval suite lacks teeth. Pause evolution and fix the evals first.
- If delta (with - without) < 0.05 AND >30% assertions are dead: the evals cannot meaningfully guide improvement. Fix evals before proceeding.

**Dead L3 example**: "摘要 >3 句" — both with and without pass 100%. Replace with: "摘要提到至少一个具体的人名、数字或日期" — bare Claude often writes vague summaries without concrete anchoring.

### Confirm and Go

After baseline is established, present a summary to the user before starting the loop:

```
Baseline established for <skill-name>:
  Evals: <N> test cases
  Aggregate score: <score>
  L1: <score>  L2: <score>  L3: <score>
  Weakest area: <dimension with lowest score>

Settings:
  Max iterations: <N or "unlimited">
  Min delta: <value>
  Guard: <command or "none">

Proceed with evolution loop? (Ctrl+C to abort)
```

Do NOT start the loop until the user acknowledges. This prevents wasted iterations on misconfigured evals.

## Step 2: Evolution Loop

### 2.1 Analyze

Before proposing any change, read:
- `experiments/<skill>/experiments.tsv` — full history of what's been tried
- Latest grading.json for each eval — which specific assertions fail?
- The current SKILL.md and all its references — full source code
- Evidence strings from failed assertions — what exactly went wrong?

Categorize failures:
- **Systematic**: same assertion fails across multiple evals → pattern problem
- **Isolated**: one assertion fails in one eval → specific edge case
- **False negative**: grading script issue, not skill issue → fix the grading, not the skill

### 2.2 Propose

Form a hypothesis: "Changing X in SKILL.md will improve Y metric because Z."

Rules for proposals:
- ONE change per iteration (atomic)
- Must cite specific evidence from grading failures
- Must explain WHY the change should help
- Prefer explanation over MUSTs — explain the reasoning, don't just add constraints
- If experiments.tsv shows similar changes already failed, try a different approach
- Look for what worked in past iterations and build on it
- **Explicitly declare** that your proposal follows the atomic change principle («仅一处修改»), and explain why single-variable changes enable causal attribution

**Common proposal mistakes to avoid:**

- **Bad** — 笼统假设: 「完善错误处理」→ 无法验证是否真的改善。**Good**: 「Crash Recovery 中 timeout 类型的动作从 'log warning' 改为 'kill subagents + revert'」
- **Bad** — 重试已失败方案: experiments.tsv 显示类似改动被丢弃，仍然尝试同样的方向。必须先分析上一次失败的原因再尝试不同方案。
- **Bad** — 一次改多个概念: 同时修改 scoring formula + subagent protocol + crash recovery。违反原子变更规则，分数变化无法归因到具体改动。

### 2.3 Apply

Edit the skill file. ONE section, ONE concept. Commit with message:
```
experiment: <skill-name> — <brief hypothesis>
```

### 2.4 Verify

Re-run all evals using the same process as Step 1 (prepare dirs → spawn agents → grade with `runner.py` → compute score).

### 2.5 Keep or Revert

Compute scores from grading.json (same `runner.py score` as Step 1.4):
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py score experiments/{skill}/iter-{N}/modified/{track}/grading.json
```
(where `{track}` is `with_skill` and `without_skill` respectively)

Compare new aggregate score to previous best:
- `new_score > prev_best + min_delta` → tentative KEEP, proceed to blind quality check
- `new_score <= prev_best + min_delta` → REVERT (`git checkout -- <skill-path>`)
- If reverted: log the failed hypothesis, optionally run post-hoc analysis (see Blind Quality Check)

**Blind quality gate**: see "## Blind Quality Check" for full protocol. Key rule:
- **Primary Gate mode** (assertions weak): blind comparison runs every iteration, its winner determines keep/revert
- **Periodic mode** (assertions healthy): blind comparison runs on triggers (every 5th iteration, L3 jump >0.15, structural hypothesis). If winner disagrees with mechanical score, revert even if metrics improved.

### 2.6 Log

**Initialize** (first iteration only):
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/scripts/aggregate.py init experiments {skill_name}
```

**Log each iteration** using aggregate.py:
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/scripts/aggregate.py log experiments/{skill} \
  {iteration} {commit} {l1} {l2} {l3} {aggregate} {delta} {status} "{hypothesis}"
```

This appends to `experiments/<skill>/experiments.tsv`:
```
iteration  commit   l1   l2   l3   aggregate  delta   status   hypothesis
0          a1b2c3d  1.0  0.85 0.60 0.78      0.0     baseline  initial
1          b2c3d4e  1.0  0.87 0.62 0.80     +0.02   keep      added memory point examples
2          -        1.0  0.83 0.58 0.77     -0.01   discard   mandatory checklists
```

**Print summary** anytime:
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/scripts/aggregate.py summary experiments/{skill}
```

Also save full grading.json for each iteration:
```
experiments/<skill>/iter-<N>/
├── baseline/
│   ├── with_skill/grading.json
│   └── without_skill/grading.json
├── modified/
│   ├── with_skill/grading.json
│   └── without_skill/grading.json
└── summary.json  # {iteration, hypothesis, score_delta, kept}
```

### 2.7 Periodic Summary

Every 10 iterations, print a progress summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Progress after <N> iterations for <skill-name>
  Baseline:   <baseline_score>
  Current:    <current_score>  (Δ <delta>)
  Best:       <best_score>     (iter <N>)
  Kept:       <K> changes
  Discarded:  <D> changes
  Top improvement: <brief description of best change>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Bounded loops (max_iterations set) also print a final summary with baseline → current best trajectory.

## Step 3: Termination

Stop when:
- User interrupts (Ctrl+C)
- `max_iterations` reached
- Score hasn't improved for 5 consecutive iterations (convergence)
- All assertions pass at 100% across all evals (perfection)

Print final summary:
- Iterations run, changes kept, changes discarded
- Score trajectory: baseline → best
- Best change and what made it work
- Remaining failure patterns (if any)

## Guard — Prevent Regressions

Guard is an optional safety net. While Verify checks "did the metric improve?", Guard checks "did anything else break?"

Configure in `targets/<target>.yaml`:
```yaml
settings:
  guard: "python3 evals/another-skill/grade.py /tmp/another-skill-test --quick"
```

Guard rules:
- Guard runs **after** the target skill's evals, on a **different skill's** test
- If aggregate score improves but guard fails → rework the change (max 2 attempts)
- If rework also fails → discard the change
- Guard skill files are never modified by the evolution loop
- This ensures optimizing one skill doesn't silently break another

Example: when evolving skill A, guard with skill B's evals to ensure changes to A don't break B's output format expectations.

## Blind Quality Check

Mechanical assertions (L1/L2/L3) can be gamed — the optimizer learns to pass assertions without actually improving output quality. Blind comparison is an independent quality signal: a fresh agent compares with-skill and without-skill outputs without knowing which is which.

### Operating Mode

Blind check runs in one of two modes, determined by the baseline assertion audit (Step 1.5):

| Mode | Condition | Behavior |
|------|-----------|----------|
| **Periodic** (default) | Assertions have healthy discrimination (delta > 0.05, <30% dead) | Blind check every 5 iterations as sanity check |
| **Primary Gate** | Assertions lack discrimination (delta < 0.05, or >30% dead L3 assertions) | Blind check runs on EVERY iteration as the main keep/revert gate |

In Primary Gate mode, the mechanical score still runs, but the blind comparison's winner determines keep/revert. The mechanical score is recorded for tracking but doesn't decide. This prevents the optimizer from gaming weak assertions — even if it learns to pass every dead L3 check, the blind judge catches quality regressions.

**Mode transition**: Start in Periodic. If the baseline audit triggers Primary Gate, stay in it until assertions are improved (dead L3% < 30% AND delta > 0.05 after re-running baseline with new assertions). The evolver should proactively suggest assertion improvements when stuck in Primary Gate mode.

### When to Trigger (Periodic Mode)

| Trigger | Rationale |
|---------|-----------|
| Every 5 iterations | Periodic sanity check |
| L3 score jumps >0.15 in one iteration | Suspiciously fast improvement |
| Hypothesis is purely structural | Adding keywords, reordering sections — easy to game |
| Manual request | Proposer wants a second opinion |

Skip blind check in Periodic mode if all L3 assertions pass at 100% AND delta > 0.05 (skill is genuinely converged). Never skip in Primary Gate mode — the high dead-assertion rate means L3 passing doesn't guarantee quality.

### Blind Comparator Agent

Spawn a subagent with this prompt:

```
You are a blind quality judge. Output A and B come from unknown sources.
Task: {eval.prompt}

Output A: {path_a}
Output B: {path_b}

1. Read both outputs.
2. Score each on Content (correctness/completeness/accuracy, 1-5) and Structure (organization/formatting/usability, 1-5).
3. Pick winner: A, B, or TIE.

Save to {output_path}/comparison.json:
{"winner": "A"|"B"|"TIE", "reasoning": "...", "rubric": {"A": {...}, "B": {...}}}
CRITICAL: Do NOT try to infer which output came from the skill.
```

**Randomization**: Randomly assign which output is A and which is B. Record the mapping so you can unblind after.

### Interpreting Results

After the comparator finishes, read `comparison.json`:

| Blind Winner | Mechanical Delta | Verdict | Action |
|-------------|-----------------|---------|--------|
| with-skill | delta > 0 | Strong confirmation | KEEP |
| with-skill | delta ≤ 0 | Assertions too strict or miss what matters | Consider revising assertions; tentative KEEP |
| without-skill | delta > 0 | Mechanical improvement was spurious | REVERT |
| without-skill | delta ≤ 0 | Confirmed regression | Keep the revert |
| TIE | any | Mechanical score decides | Fall back to normal keep/revert |

### Post-hoc Analysis (on revert)

Spawn an analyzer to understand WHY a change was reverted:

```
Read {comparison.json}. Winner: {winner_path}, Loser: {loser_path}.
1. What specific instruction difference caused the outcome? Quote both.
2. What concrete change would flip the result?

Save to {output_path}/analysis.json:
{"winner_strengths": [...], "loser_weaknesses": [...], "improvement_suggestions": [{"priority": "high"|"medium"|"low", "suggestion": "..."}]}
```

The analysis feeds into the next Propose step — proposer reads `analysis.json` alongside grading failures.

## Crash Recovery

| Failure | Response |
|---------|----------|
| Eval agent timeout / crash | Mark that eval as inconclusive, continue with remaining evals. If >50% of evals fail, abort iteration and revert. |
| Grading script error | Attempt fix (max 3 tries: syntax fix, import fix, assertion fix). If still broken, skip this eval for this iteration, log warning. |
| Git conflict on revert | Abort iteration, reset to HEAD~1, log the anomalous state for manual review. |
| Infinite loop / hang | Each iteration has a 10-minute timeout. If exceeded, kill subagents, revert, log timeout. |
| Resource exhaustion (disk/token) | Revert, log warning, suggest reducing eval scope or increasing limits. |
| External dependency missing | Skip evaluation that depends on it, log, continue with other evals. |
| All evals fail | Abort iteration, revert, log critical error. Do NOT count this as a kept change. |

Every crash is logged to `experiments/<skill>/crashes.tsv`:
```
timestamp           iteration  type        detail              action
2026-05-19T14:30:00 3          timeout     eval agent >600s    reverted
2026-05-19T14:45:00 5          grad_error  grade.py syntax     fixed (attempt 1)
```

## Subagent Protocol

Each eval spawns two agents in parallel (`Agent` tool, `run_in_background: true`).

### Agent Prompt Template

For each eval definition from `evals.json`. `{skill_path}` = `project_root + path`.

**with-skill agent:**
```
Execute this task using the {skill_name} skill.
First, read {skill_path}/SKILL.md and {skill_path}/references/. Follow the skill's instructions exactly.
Then: {eval.prompt}

Work in the directory: {eval.project_dirs.with_skill}. Save summary to {eval.project_dirs.with_skill}/outputs/summary.md
```

Note: Read the skill file directly — the `Skill` tool only works for installed skills, not development skills.

**without-skill agent:**
```
Execute this task WITHOUT any skill. Do NOT read any SKILL.md. Work from your own knowledge.
Task: {eval.prompt}

Work in {eval.project_dirs.without_skill}. Save summary to {eval.project_dirs.without_skill}/outputs/summary.md
```

### Lifecycle

1. **Before**: `mkdir -p {project_dir}/outputs`, copy fixtures if present
2. **Execute**: spawn both agents simultaneously, wait for completion
3. **After**: `python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py grade {evals_dir} {project_dir} {label}`; save results to `experiments/{skill}/iter-{N}/{config}/{track}/`

Parallelism: all evals run in parallel, N_evals × 2 concurrent agents. Batch in groups of 2-3 if resource-constrained.

## Important Constraints

- **Simplicity wins**: equal scores → prefer fewer words, fewer constraints, fewer steps. A shorter skill that scores the same is strictly better.
- **L3 matters most**: content quality assertions are harder to pass — that's the point. Work on them first.
- **If stuck, think harder**: re-read failure evidence, combine ideas from near-misses. Don't add random changes hoping something sticks.
- **Don't overfit**: a change that improves scores but degrades actual quality (detectable via L3 assertions) must be reverted.
