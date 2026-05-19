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
LOAD target config → READ skill + evals → ESTABLISH baseline →
LOOP:
  1. ANALYZE grading results — which assertions fail? what's the weakest dimension?
  2. READ current SKILL.md + references (full source)
  3. READ experiments.tsv — what's been tried? what worked? what failed?
  4. PROPOSE one focused hypothesis ("changing X will improve Y because Z")
  5. APPLY the change (edit one section of SKILL.md or a reference)
  6. RUN all evals (spawn with-skill and without-skill agents in parallel)
  7. WAIT for all agents to complete
  8. GRADE results → compute new aggregate score
  9. IF score improved → KEEP, log to experiments.tsv
  10. IF score didn't improve → REVERT (git checkout), log failure
  11. IF score decreased significantly → ANALYZE why, log learning
  12. PRINT progress summary every iteration
```

## Step 0: Load Target Config

Read `targets/<target>.yaml`. Target YAML schema:

```yaml
project_root: /absolute/path/to/project   # project containing skills
skills:
  - name: skill-name                       # skill identifier
    path: plugins/.../skills/skill-name    # relative to project_root
    evals_dir: evals/skill-name            # relative to project_root, contains grade.py
settings:
  max_iterations: 20     # stop after N iterations (omit for unbounded)
  min_delta: 0.01        # minimum aggregate improvement to keep change
  atomic_changes: true   # always true — one change per iteration
  auto_revert: true      # revert if score doesn't improve
  guard: null            # optional: evals_dir of another skill to protect
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
    "skill-name": {
      "skill_path": "plugins/.../skills/skill-name",
      "evals": [
        {
          "id": "unique-eval-id",
          "name": "人类可读名称",
          "iteration": 1,
          "prompt": "给 agent 的执行指令...",
          "project_dirs": {
            "with_skill": "/tmp/skill-test-with-skill",
            "without_skill": "/tmp/skill-test-without-skill"
          }
        }
      ]
    }
  }
}
```

Key fields:
- `prompt`: the exact text given to the eval agent (injected into the subagent prompt template)
- `project_dirs.with_skill` / `project_dirs.without_skill`: isolated working directories for each track
- `iteration`: fixture version — increment when eval prompts or grading rules change

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

### 2.3 Apply

Edit the skill file. ONE section, ONE concept. Commit with message:
```
experiment: <skill-name> — <brief hypothesis>
```

### 2.4 Verify

Re-run all evals using the same process as Step 1 (prepare dirs → spawn agents → grade with `runner.py` → compute score).

### 2.5 Keep or Revert

Compute scores from grading.json:
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py score experiments/{skill}/iter-{N}/modified/with_skill/grading.json
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py score experiments/{skill}/iter-{N}/modified/without_skill/grading.json
```

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

Spawn a subagent with this prompt template:

```
You are a blind quality judge. You will see two outputs labeled A and B.
You do NOT know which skill or configuration produced them.
Judge purely on output quality and task completion.

Output A: {path to with-skill or without-skill output, randomly assigned}
Output B: {path to the other output}
Task: {eval.prompt}

Step 1: Read both outputs carefully.
Step 2: Understand what the task requires.
Step 3: Score each output on two dimensions (1-5 each):
  - Content: correctness, completeness, accuracy
  - Structure: organization, formatting, usability
Step 4: Determine the winner (A, B, or TIE).

Save your judgment to {output_path}/comparison.json:
{
  "winner": "A"|"B"|"TIE",
  "reasoning": "specific explanation",
  "rubric": {
    "A": {"content": {"correctness": 4, "completeness": 5, "accuracy": 4}, "content_score": 4.3, "structure": {...}, "structure_score": 4.0, "overall_score": 8.3},
    "B": {...}
  }
}

CRITICAL: Do NOT try to infer which output came from the skill. Judge outputs as-is.
```

**Randomization**: Randomly assign which output is A and which is B. Record the mapping so you can unblind after.

### Interpreting Results

After the comparator finishes, read `comparison.json`:

- **Winner = with-skill output AND mechanical delta > 0**: Strong confirmation. Keep.
- **Winner = with-skill output BUT mechanical delta ≤ 0**: Mechanical assertions are too strict or miss what matters. Consider revising assertions.
- **Winner = without-skill output (mechanical score said keep)**: The mechanical improvement was spurious. REVERT.
- **Winner = without-skill output (mechanical score said revert)**: Confirmed regression. Keep the revert.
- **TIE**: Mechanical score decides (fall back to normal keep/revert logic).

### Post-hoc Analysis (on revert)

When a change is reverted, optionally spawn an analyzer agent to understand WHY:

```
Read the blind comparison result at {comparison.json}.
The winning skill is at {winner_skill_path}, the losing skill at {loser_skill_path}.

Analyze:
1. What specific difference in the skill instructions caused the outcome?
2. Quote from both skills where they diverge.
3. What concrete change would likely flip the result?

Save to {output_path}/analysis.json:
{
  "winner_strengths": ["specific strength 1", ...],
  "loser_weaknesses": ["specific weakness 1", ...],
  "improvement_suggestions": [
    {"priority": "high"|"medium"|"low", "category": "instructions"|"tools"|"examples"|"error_handling", "suggestion": "...", "expected_impact": "..."}
  ]
}
```

The analysis feeds into the next iteration's Propose step — the proposer reads `analysis.json` alongside grading failures to form a better hypothesis.

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

Each eval runs two agents in parallel. Use the `Agent` tool with `run_in_background: true`.

### Agent Prompt Template

For each eval definition (from `evals.json`), construct the agent prompt as follows.
Use `{skill_path}` = the absolute path from target config (`project_root + path`).

**with-skill agent:**
```
Your task is to execute the following request using the {skill_name} skill.

First, read the skill file at {skill_path}/SKILL.md and any referenced files
in {skill_path}/references/. Follow the skill's instructions exactly.

Then, execute this task:
{eval.prompt}

IMPORTANT: You must work in the directory: {eval.project_dirs.with_skill}
Create all output files under that directory. When done, save a brief summary
of what you did to {eval.project_dirs.with_skill}/outputs/summary.md
```

Note: The agent reads the skill file directly rather than using the `Skill` tool,
because test/development skills are not registered in Claude Code's skill registry.
The `Skill` tool only works for installed skills. Reading the file directly is
always reliable.

**without-skill agent:**
```
Your task is to execute the following request WITHOUT using any skill.
Do NOT read any SKILL.md file. Do NOT load any skill. Work from your own knowledge.

Execute this task:
{eval.prompt}

IMPORTANT: You must work in the directory: {eval.project_dirs.without_skill}
Create all output files under that directory. When done, save a brief summary
of what you did to {eval.project_dirs.without_skill}/outputs/summary.md
```

### Before Spawning

1. Read the eval definition from the target's `evals.json`
2. Ensure the project directories exist: `mkdir -p {project_dir}/outputs`
3. If the eval has fixture files (in `iteration-N/`), copy them to the project dir first
4. Spawn both agents simultaneously with `run_in_background: true`
5. Wait for both to complete before proceeding to grading

### After Agents Complete

Run grading for each track:
```
python3 ${CLAUDE_PLUGIN_ROOT}/evolver/framework/runner.py grade {evals_dir} {project_dir} {label}
```

Save results:
```
mkdir -p experiments/{skill}/iter-{N}/{config}/{track}/
cp {project_dir}/grading.json experiments/{skill}/iter-{N}/{config}/{track}/
```

### Parallelism

- All evals for a skill run in parallel (each spawns its own with/without pair)
- Within each eval, the with-skill and without-skill agents run in parallel
- Total concurrent agents = N_evals × 2
- If token/resource limits are a concern, batch evals in groups of 2-3

## Important Constraints

- **Simplicity wins**: equal scores → prefer fewer words, fewer constraints, fewer steps. A shorter skill that scores the same is strictly better.
- **L3 matters most**: content quality assertions are harder to pass — that's the point. Work on them first.
- **If stuck, think harder**: re-read failure evidence, combine ideas from near-misses. Don't add random changes hoping something sticks.
- **Don't overfit**: a change that improves scores but degrades actual quality (detectable via L3 assertions) must be reverted.
