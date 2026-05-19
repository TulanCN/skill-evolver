#!/usr/bin/env python3
"""Grading rules for skill-evolver itself.

Tests both the framework code and the skill prompt quality.
This is meta-grading: the evolver evaluating itself.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evolver" / "framework"))
from base_grade import Assertion, BaseGrader, GradingResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_SECTIONS = [
    "Step 0: Load Target Config",
    "Step 1: Establish Baseline",
    "Step 2: Evolution Loop",
    "Step 3: Termination",
    "Guard",
    "Crash Recovery",
    "Subagent Protocol",
    "Important Constraints",
]

REQUIRED_SUBSECTIONS = [
    "2.1 Analyze",
    "2.2 Propose",
    "2.3 Apply",
    "2.4 Verify",
    "2.5 Keep or Revert",
    "2.6 Log",
    "2.7 Periodic Summary",
]

REFERENCED_FILES = [
    "evolver/framework/runner.py",
    "evolver/framework/base_grade.py",
    "evolver/scripts/aggregate.py",
    "targets/",
]


class SkillEvolverGrader(BaseGrader):

    def check_all(self, r: GradingResult) -> None:
        self._check_framework_code(r)
        self._check_skill_prompt(r)
        self._check_tool_consistency(r)

    # ---- Framework code checks ----

    def _check_framework_code(self, r: GradingResult):
        self._check_runner_score(r)
        self._check_aggregate(r)
        self._check_base_grade(r)

    def _check_runner_score(self, r: GradingResult):
        """Verify runner.py score computation."""
        runner = PROJECT_ROOT / "evolver/framework/runner.py"
        r.add(Assertion("runner.py 存在", level=1).check(
            runner.is_file(), str(runner)))

        # Test score computation with mock data
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "by_level": {"L1": "10/10", "L2": "8/10", "L3": "6/10"},
            }, f)
            tmp_path = f.name

        try:
            result = subprocess.run(
                ["python3", str(runner), "score", tmp_path],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_ROOT),
            )
            r.add(Assertion("runner.py score 命令可执行", level=1).check(
                result.returncode == 0, f"exit={result.returncode}" if result.returncode != 0 else "ok"))

            if "Aggregate=0.7000" in result.stdout or "Aggregate=0.7" in result.stdout:
                r.add(Assertion("score 计算正确: L1=1.0 L2=0.8 L3=0.6 → 0.70", level=2).pass_("正确"))
            else:
                r.add(Assertion("score 计算正确: L1=1.0 L2=0.8 L3=0.6 → 0.70", level=2).fail(
                    f"stdout: {result.stdout.strip()[:100]}"))
        except Exception as e:
            r.add(Assertion("runner.py score 命令可执行", level=1).fail(str(e)))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _check_aggregate(self, r: GradingResult):
        """Verify aggregate.py commands work."""
        agg = PROJECT_ROOT / "evolver/scripts/aggregate.py"
        r.add(Assertion("aggregate.py 存在", level=1).check(
            agg.is_file(), str(agg)))

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            exp_dir = Path(tmpdir) / "experiments"
            exp_dir.mkdir()

            # Test init
            result = subprocess.run(
                ["python3", str(agg), "init", str(exp_dir), "test-skill"],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_ROOT),
            )
            r.add(Assertion("aggregate.py init 可执行", level=1).check(
                result.returncode == 0, f"exit={result.returncode}" if result.returncode != 0 else "ok"))

            tsv = exp_dir / "test-skill" / "experiments.tsv"
            r.add(Assertion("init 创建 experiments.tsv", level=2).check(
                tsv.is_file(), str(tsv) if tsv.is_file() else "缺失"))

            # Test log
            result = subprocess.run(
                ["python3", str(agg), "log", str(exp_dir / "test-skill"),
                 "0", "abc123", "1.0", "0.85", "0.60", "0.78", "0.0", "baseline", "initial"],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_ROOT),
            )
            r.add(Assertion("aggregate.py log 可执行", level=1).check(
                result.returncode == 0, f"exit={result.returncode}" if result.returncode != 0 else "ok"))

            if tsv.is_file():
                lines = tsv.read_text().strip().split("\n")
                r.add(Assertion("TSV 包含 header + 1 条记录", level=2).check(
                    len(lines) == 2, f"{len(lines)} 行" if len(lines) == 2 else f"{len(lines)} 行，应为 2"))

            # Test summary
            result = subprocess.run(
                ["python3", str(agg), "summary", str(exp_dir / "test-skill")],
                capture_output=True, text=True, timeout=10,
                cwd=str(PROJECT_ROOT),
            )
            r.add(Assertion("aggregate.py summary 可执行", level=1).check(
                result.returncode == 0, f"exit={result.returncode}" if result.returncode != 0 else "ok"))

    def _check_base_grade(self, r: GradingResult):
        """Verify base_grade.py classes work."""
        bg = PROJECT_ROOT / "evolver/framework/base_grade.py"
        r.add(Assertion("base_grade.py 存在", level=1).check(
            bg.is_file(), str(bg)))

        # Import and test
        sys.path.insert(0, str(bg.parent))
        try:
            import base_grade as bg_mod
            r.add(Assertion("base_grade.py 可导入", level=1).pass_("ok"))
        except Exception as e:
            r.add(Assertion("base_grade.py 可导入", level=1).fail(str(e)))
            return

        # Test Assertion
        a = bg_mod.Assertion("测试断言", level=3)
        a.pass_("证据")
        r.add(Assertion("Assertion.pass_() 正常", level=2).check(
            a.passed and a.to_dict()["evidence"] == "证据", "ok" if a.passed else "fail"))

        a2 = bg_mod.Assertion("测试失败", level=1)
        a2.fail("失败原因")
        r.add(Assertion("Assertion.fail() 正常", level=2).check(
            not a2.passed and a2.to_dict()["evidence"] == "失败原因", "ok" if not a2.passed else "fail"))

        # Test GradingResult
        gr = bg_mod.GradingResult("test", Path("/tmp"))
        gr.add(a).add(a2)
        r.add(Assertion("GradingResult.pass_rate 计算正确", level=2).check(
            gr.pass_rate == 0.5, f"{gr.pass_rate}" if gr.pass_rate == 0.5 else f"{gr.pass_rate}，应为 0.5"))
        r.add(Assertion("GradingResult.by_level() 正确", level=2).check(
            gr.by_level().get("L1") == "0/1", f"L1={gr.by_level().get('L1')}"))

        # Test BaseGrader
        class TestGrader(bg_mod.BaseGrader):
            def check_all(self, result: GradingResult) -> None:
                result.add(Assertion("always pass", level=1).pass_("ok"))

        tg = TestGrader(Path("/tmp"))
        result = tg.grade("test")
        r.add(Assertion("BaseGrader.grade() 返回 GradingResult", level=2).check(
            isinstance(result, bg_mod.GradingResult) and result.pass_rate == 1.0,
            f"pass_rate={result.pass_rate}" if result.pass_rate == 1.0 else "fail"))

    # ---- Skill prompt quality checks ----

    def _check_skill_prompt(self, r: GradingResult):
        skill_md = PROJECT_ROOT / "skills" / "skill-evolver" / "SKILL.md"
        if not skill_md.is_file():
            r.add(Assertion("SKILL.md 存在", level=1).fail("文件不存在"))
            return
        content = skill_md.read_text()
        r.add(Assertion("SKILL.md 可读", level=1).pass_(f"{len(content)} 字符"))

        self._check_yaml_frontmatter(r, content)
        self._check_required_sections(r, content)
        self._check_workflow_steps(r, content)
        self._check_score_formula(r, content)
        self._check_atomic_change_rule(r, content)

    def _check_yaml_frontmatter(self, r: GradingResult, content: str):
        has_frontmatter = content.startswith("---")
        r.add(Assertion("SKILL.md 有 YAML frontmatter", level=1).check(
            has_frontmatter, "有" if has_frontmatter else "缺失"))

        if has_frontmatter:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = parts[1]
                has_name = "name:" in fm
                has_desc = "description:" in fm
                r.add(Assertion("frontmatter 包含 name", level=2).check(
                    has_name, "有" if has_name else "缺失"))
                r.add(Assertion("frontmatter 包含 description", level=2).check(
                    has_desc, "有" if has_desc else "缺失"))

    def _check_required_sections(self, r: GradingResult, content: str):
        for section in REQUIRED_SECTIONS:
            r.add(Assertion(f"SKILL.md 包含章节: {section}", level=2).check(
                section in content, "找到" if section in content else "缺失"))

        for subsection in REQUIRED_SUBSECTIONS:
            r.add(Assertion(f"SKILL.md 包含子章节: {subsection}", level=2).check(
                subsection in content, "找到" if subsection in content else "缺失"))

    def _check_workflow_steps(self, r: GradingResult, content: str):
        all_steps = ["ANALYZE", "READ", "PROPOSE", "APPLY", "RUN all evals",
                     "GRADE", "KEEP", "LOG"]
        found = sum(1 for s in all_steps if s in content)
        r.add(Assertion("Workflow 包含所有核心步骤", level=2).check(
            found >= 6, f"{found}/{len(all_steps)} 步" if found >= 6 else f"仅 {found}/{len(all_steps)} 步"))

    def _check_score_formula(self, r: GradingResult, content: str):
        has_l1 = "0.2" in content and "L1" in content
        has_l2 = "0.3" in content and "L2" in content
        has_l3 = "0.5" in content and "L3" in content
        r.add(Assertion("评分公式: L1*0.2 + L2*0.3 + L3*0.5", level=3).check(
            has_l1 and has_l2 and has_l3,
            "公式存在" if (has_l1 and has_l2 and has_l3) else "公式不完整"))

        has_mean = "mean" in content.lower() or "average" in content.lower()
        r.add(Assertion("多 eval 聚合: mean(eval_scores)", level=3).check(
            has_mean, "有聚合说明" if has_mean else "缺少多 eval 聚合说明"))

    def _check_atomic_change_rule(self, r: GradingResult, content: str):
        has_atomic = "ONE change" in content or "one change" in content.lower() or "atomic" in content.lower()
        r.add(Assertion("包含原子变更规则", level=3).check(
            has_atomic, "有" if has_atomic else "缺失"))

    # ---- Tool consistency checks ----

    def _check_tool_consistency(self, r: GradingResult):
        """Verify all files referenced in SKILL.md exist."""
        for f in REFERENCED_FILES:
            path = PROJECT_ROOT / f
            exists = path.exists()
            r.add(Assertion(f"引用路径存在: {f}", level=1).check(
                exists, str(path) if exists else "不存在"))

        # Check that SKILL.md references runner.py and aggregate.py
        skill_md = PROJECT_ROOT / "skills" / "skill-evolver" / "SKILL.md"
        if skill_md.is_file():
            content = skill_md.read_text()
            r.add(Assertion("SKILL.md 引用了 runner.py", level=1).check(
                "runner.py" in content, "引用" if "runner.py" in content else "未引用"))
            r.add(Assertion("SKILL.md 引用了 aggregate.py", level=1).check(
                "aggregate.py" in content, "引用" if "aggregate.py" in content else "未引用"))
            r.add(Assertion("SKILL.md 引用了 Agent 工具", level=2).check(
                "Agent" in content, "引用" if "Agent" in content else "未引用"))


def grade(project_root: Path, label: str) -> GradingResult:
    grader = SkillEvolverGrader(project_root)
    result = grader.grade(label)
    result.print()
    return result


if __name__ == "__main__":
    grade(PROJECT_ROOT, "skill-evolver-self-test")
