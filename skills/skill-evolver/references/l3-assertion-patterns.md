# L3 Assertion Design Patterns

Good L3 assertions discriminate — with-skill passes while without-skill fails. Bad L3 assertions are just
disguised L1/L2 checks (pattern matching, word counting). This guide helps you write assertions
that resist mechanical gaming.

## The Discrimination Test

Before finalizing any L3 assertion, ask: "Would bare Claude (without my skill) pass this?"

If yes → it's not L3, it's L2 at best. Rewrite it.

If no → it discriminates. Keep it.

## Pattern 1: Specificity Check

**Bad**: "摘要 ≥3 句"
**Why**: Any 3 sentences pass. Content doesn't matter.

**Good**: "摘要提到至少一个具体的人名、组织名、数字或日期"
**Why**: Forces the output to include concrete anchoring details. Bare Claude often writes vague summaries.

**Good**: "摘要不会以'本文讨论了'或'这是一个关于'开头"
**Why**: Targets a specific Claude habit. Mechanical and objective.

## Pattern 2: Anti-Claude Check

Claude has well-known default behaviors. Good assertions target these.

**Bad**: "摘要无泛泛而谈的套话"（banned word list）
**Why**: Word lists are trivial to bypass and hard to maintain.

**Good**: "摘要中不包含下述任一句式：'在当今时代'、'随着...的发展'、'众所周知'、'越来越重要'"
**Why**: Targets structural Claude-isms, not individual words. Harder to game.

**Good**: "分析部分的第一句话是论点，而非背景陈述"
**Why**: Claude defaults to "X is an important topic in..." before stating a position.

## Pattern 3: Actionability Check

**Bad**: "建议包含执行动词"
**Why**: Dropping "修改" or "创建" anywhere satisfies this.

**Good**: "每条建议包含：做什么（动词+对象）、怎么做（工具/方法）、预期结果（可观测的变化）"
**Why**: Three-dimensional check. You can't fake all three with a keyword.

**Good**: "至少一条建议引用了分析部分的具体发现作为依据"
**Why**: Forces logical connection between sections. Bare Claude tends to give generic advice.

## Pattern 4: Structural Integrity Check

**Bad**: "分析包含 ≥2 个 bullet 点"
**Why**: Any two dashes pass.

**Good**: "每条分析 bullet 的结构是：`- **核心发现**：一句话 + 支撑证据`"
**Why**: Checks a specific template pattern, not just existence.

**Good**: "相邻的 bullet 点覆盖不同维度（不重复同一个观点）"
**Why**: Requires semantic judgment. Mechanical but meaningful.

## Pattern 5: Constraint Satisfaction

**Bad**: "建议有 2 条编号项"
**Why**: Number counting.

**Good**: "建议按优先级排序，且每条建议的操作对象是明确的（不是'团队'这种模糊主体）"
**Why**: Checks two qualities simultaneously.

**Good**: "文件中不包含 future tense marker（将会、计划、打算、后面会）"
**Why**: Domain-specific constraint that bare Claude routinely violates.

## Pattern 6: Differentiation Check

The best L3 assertions produce a clear with/without split.

**Setup**: Run the eval WITHOUT your skill first. Examine what bare Claude produces. Identify its weaknesses — what does it consistently miss or do wrong? Then write assertions that target those specific gaps.

**Example workflow**:
1. Run without-skill → bare Claude writes 8 H2 sections instead of 3
2. Write assertion: "H2 节数量恰好为 3，不多不少"
3. Run with-skill → passes (the skill constrains it)

| Pattern | Inspection Target |
|---------|-------------------|
| Anti-Claude | Claude's default writing habits |
| Specificity | Vagueness → concrete anchoring |
| Actionability | Generic advice → executable plan |
| Structural | Surface format → internal logic |
| Constraint | Single rule → multi-dimensional constraint |
| Differentiation | Weakness in bare output → assertion targeting that gap |

## When an Assertion Keeps Passing for Both Tracks

If with-skill AND without-skill both pass at 100% for an assertion:

1. **The assertion is too easy** → strengthen it (move up a pattern level)
2. **The assertion tests something Claude already does well** → drop it, it wastes grading time
3. **The skill isn't needed for this** → the eval itself may be non-discriminating

After establishing baseline, audit all assertions. Any assertion that passes 100% in BOTH tracks
should be flagged for replacement. See `evolver/SKILL.md` Step 1.4 for the auto-audit procedure.
