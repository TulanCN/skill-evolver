# CLAUDE.md

## 项目定位

Skill Evolver 是一个**通用的 Claude Code Skill 自主进化引擎**。它通过外层优化循环，自动对 skill prompt 进行 A/B 测试、评分和改进。

**灵感来源（三个项目的交集）：**

| 项目 | 核心贡献 |
|------|---------|
| Karpathy Autoresearch (uditgoenka/autoresearch) | Goal + Metric + Loop = 持续改进；一次改一处，原子变更，自动回滚 |
| Meta-Harness (arxiv 2603.28052) | Agentic proposer + 文件系统记忆；proposer 能看到完整源码、评分和 trace，不压缩反馈 |
| Anthropic Skill Creator | with-skill vs without-skill A/B 对比 + 机械化 grading 断言 |

**核心洞察**：这三个项目的交集是 —— 一个能自己读历史、自己改 prompt、自己跑测试验证、自己决定保留还是回滚的进化循环。文件系统作为记忆（Meta-Harness 精髓），机械指标驱动决策（Autoresearch），双轨对比验证（Skill Creator）。

## 架构

```
skill-evolver/
├── CLAUDE.md                     # 本项目设计文档
├── .claude-plugin/
│   ├── plugin.json               # 插件清单
│   └── marketplace.json          # Marketplace 定义
├── skills/
│   └── skill-evolver/
│       └── SKILL.md              # 进化循环 skill（加载入口）
├── evolver/                      # 框架代码
│   ├── framework/
│   │   ├── base_grade.py         # Assertion / GradingResult / BaseGrader
│   │   └── runner.py             # CLI: grade / score / report
│   └── scripts/
│       └── aggregate.py          # 结果聚合 + TSV 记录
├── evals/                        # skill-evolver 自身的 evals
│   └── skill-evolver/
│       ├── evals.json
│       └── grade.py
├── targets/                      # 测试目标配置
│   ├── self.yaml                 # 自进化目标
│   └── <your-target>.yaml        # 任意 skill 的进化配置
├── tests/                        # 测试 fixtures
│   └── fixtures/dummy/           # 最小化测试靶场
├── experiments/                  # 进化实验历史
│   └── <skill-name>/
│       ├── experiments.tsv       # 迭代记录
│       └── iter-<N>/             # 每次迭代的完整 grading 结果
└── .gitignore
```

## 核心设计决策

### 1. 评估三层体系 (L1/L2/L3)

| 层级 | 检查什么 | 权重 | 例子 |
|------|---------|------|------|
| L1 | 结构：目录/文件是否存在 | 0.2 | 输出文件在指定路径下 |
| L2 | 模板：格式是否按 spec | 0.3 | 必需章节全部存在、章节顺序正确 |
| L3 | 内容：设计质量、语义正确性 | 0.5 | 摘要具体不泛泛、分析有实质洞见、建议可执行 |

**L3 权重最高**的原因：对抗 Goodhart 定律。如果 L1+L2 权重过高，优化器会进化出"完美通过所有结构断言但内容毫无灵魂"的 skill。

### 2. 原子变更规则

每次迭代只改一处 —— 一个 section、一段指令、一个约束。原因：
- 如果评分上升，知道是哪个改动导致的
- 如果评分下降，回滚不损失其他改动
- 实验记录有因果可解释性

### 3. 文件系统作为记忆

不把历史压缩成摘要。Proposer 每次决策前读取：
- `experiments.tsv`：所有历史迭代的分数和假设
- `iter-N/baseline/grading.json`：具体的断言通过/失败证据
- 当前 `SKILL.md` 和所有 `references/*.md`：完整源码
- `git log`：所有实验性提交

### 4. 双轨对比验证

每次验证 spawn 两个独立子代理：
- with-skill：加载目标 skill，执行 eval prompt
- without-skill：不加载任何 skill，裸跑同一 prompt

delta = with_score - without_score。如果裸跑也能得高分，说明 eval 断言不够有区分力（需要增加 L3 断言）。

### 5. 机械指标驱动

不使用主观判断决定保留/回滚。`aggregate_score = L1*0.2 + L2*0.3 + L3*0.5`。只有机械指标上升超过 min_delta 才保留改动。

### 6. Goodhart 防御

- L3 权重 > L1+L2 权重
- 禁止纯格式优化（如把"## 步骤"改成"## REQUIRED_STEP_1"）
- Proposer 必须读 failure evidence，不能只看数字
- 定期人工审查进化方向

## 进化循环流程（详见 skills/skill-evolver/SKILL.md）

完整复现 Autoresearch 核心能力：

**8 条规则全部覆盖**：Loop until done、Read before write、One change per iteration、Mechanical verification only、Automatic rollback、Simplicity wins、Git is memory、When stuck think harder。

**自增能力**：
- Guard 机制 — 优化一个 skill 时自动检测其他 skill 是否回归
- Crash Recovery — 6 种失败策略（timeout/grad error/git conflict/infinite loop/resource/external dependency）
- Setup 确认 — baseline 跑完先展示计划，用户确认后才进循环
- 每 10 轮进度摘要

```
LOAD target config → ESTABLISH baseline →
LOOP:
  1. ANALYZE grading results
  2. READ current source + experiments history
  3. PROPOSE one focused hypothesis
  4. APPLY atomic change
  5. RUN all evals (spawn agents in parallel)
  6. GRADE results
  7. KEEP or REVERT based on score delta
  8. LOG to experiments.tsv
```

## 关键文件

- `skills/skill-evolver/SKILL.md`：进化循环的完整指令，被 Claude Code 加载执行
- `targets/<target>.yaml`：指向目标 skill 的配置（项目内置 `self.yaml` 用于自进化）
- `evolver/framework/base_grade.py`：Assertion / GradingResult / BaseGrader 基类
- `evolver/framework/runner.py`：eval 运行和报告 CLI
- `evolver/scripts/aggregate.py`：实验记录管理 CLI
- `tests/fixtures/dummy/`：最小化测试靶场，供框架验证使用
- `experiments/`：所有进化实验的持久化记录

## 设计哲学

1. **第一性原理优先**：不从模板出发，从"为什么需要这个循环"出发
2. **文件系统是唯一的持久化层**：不需要数据库，git + TSV + JSON 足够
3. **简单胜于复杂**：Python 标准库 + Claude Code 原生能力，不引入新依赖
4. **透明度**：每个决策都有可追溯的实验记录
5. **对抗过度优化**：L3 权重 + 人工审查门，防止机械指标被游戏化
