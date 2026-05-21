# Skill Evolver

**Claude Code Skill 的自主进化引擎。**

自动对 skill prompt 进行 A/B 测试、机械化评分和迭代改进 —— 你只管说"进化"，剩下的交给 agent。

## 使用方式

### 方式一：插件安装

```
/plugin marketplace add TulanCN/skill-evolver
/plugin install skill-evolver@skill-evolver
```

然后在任意项目中：

```
/skill-evolver 进化 <skill-name>
```

### 方式二：克隆 + 本地安装

```bash
git clone https://github.com/TulanCN/skill-evolver.git
cd skill-evolver
claude
```

在 Claude Code 中添加本地 marketplace 并安装：

```
/plugin marketplace add ../skill-evolver
/plugin install skill-evolver@skill-evolver
```

然后：

## License

MIT
