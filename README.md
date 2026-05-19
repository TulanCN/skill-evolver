# Skill Evolver

**Claude Code Skill 的自主进化引擎。**

基于外层优化循环，自动对 skill prompt 进行 A/B 测试、机械化评分和迭代改进。

## 设计理念

Skill 是 Claude Code 的指令增强包。一个 skill 的效果取决于它的 prompt 写得好不好。但 prompt 调优目前基本靠人工 —— 改了 → 试一下 → 感觉好点？→ 保留。

Skill Evolver 把这件事自动化：

```
Modify → Verify(with-skill vs without-skill) → Keep/Discard → Repeat
```

三个核心思想：
- **Autoresearch**：Goal + Metric + Loop = 持续改进
- **Meta-Harness**：文件系统记忆，proposer 看到完整历史和源码
- **Skill Creator**：双轨对比验证 + 机械化 grading

## 使用方式

在 skill-evolver 项目中启动 Claude Code：

```bash
cd skill-evolver
claude
```

加载 evolver skill，指定目标 skill 进行进化：

```
进化 <skill-name>
```

Claude 会自动：
1. 读取目标配置，定位要进化的 skill
2. 建立 baseline（跑所有 evals 的 with/without 对比）
3. 进入进化循环：分析 → 提出假设 → 改一处 → 验证 → 保留/回滚
4. 所有结果记录在 `experiments/` 下

### 配置新目标

创建 `targets/<your-target>.yaml`，参考 `targets/self.yaml` 的格式。为你的 skill 编写 evals（grade.py + evals.json），放在 skill 项目的 evals 目录下。
