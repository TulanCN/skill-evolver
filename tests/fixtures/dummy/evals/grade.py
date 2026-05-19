#!/usr/bin/env python3
"""Grading rules for dummy-writer skill.

Tests the evolution framework itself — minimal assertions, fast to execute.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "evolver" / "framework"))
from base_grade import Assertion, BaseGrader, GradingResult

REQUIRED_SECTIONS = ["摘要", "分析", "建议"]
BANNED_GENERIC = ["这是一个很重要的", "众所周知", "众所周知的是"]


class DummyGrader(BaseGrader):

    def check_all(self, r: GradingResult) -> None:
        report = self._find_report()
        if not report:
            for section in REQUIRED_SECTIONS:
                r.add(Assertion(f"报告包含节: {section}", level=1).fail("报告文件不存在"))
            return
        content = report.read_text()

        # L1: structure — sections exist
        h2_sections = re.findall(r"^## (.+)$", content, re.MULTILINE)
        for section in REQUIRED_SECTIONS:
            r.add(Assertion(f"报告包含节: {section}", level=1).check(
                section in content, "找到" if section in content else "缺失"))

        # L2: template — correct order, correct count
        r.add(Assertion("H2 节数量为 3", level=2).check(
            len(h2_sections) == 3, f"找到 {len(h2_sections)} 个" if len(h2_sections) == 3 else f"找到 {len(h2_sections)} 个，应为 3"))

        r.add(Assertion("节顺序: 摘要 → 分析 → 建议", level=2).check(
            h2_sections == REQUIRED_SECTIONS,
            "顺序正确" if h2_sections == REQUIRED_SECTIONS else f"实际: {' → '.join(h2_sections)}"))

        # L2: format — bullet points in 分析
        analysis = self._extract_section(content, "分析")
        if analysis:
            bullet_count = len(re.findall(r"^- ", analysis, re.MULTILINE))
            r.add(Assertion("分析包含 ≥2 个 bullet 点", level=2).check(
                bullet_count >= 2, f"找到 {bullet_count} 个"))

        # L2: format — numbered items in 建议
        advice = self._extract_section(content, "建议")
        if advice:
            num_count = len(re.findall(r"^\d+\. ", advice, re.MULTILINE))
            r.add(Assertion("建议包含 ≥2 个编号项", level=2).check(
                num_count >= 2, f"找到 {num_count} 个"))

        # L3: content — 摘要 specificity
        summary = self._extract_section(content, "摘要")
        if summary:
            sentences = [s.strip() for s in re.split(r"[。.!！?？\n]", summary) if s.strip()]
            r.add(Assertion("摘要 ≥3 句", level=3).check(
                len(sentences) >= 3, f"{len(sentences)} 句" if len(sentences) >= 3 else f"仅 {len(sentences)} 句"))
            r.add(Assertion("摘要 ≤5 句", level=3).check(
                len(sentences) <= 5, f"{len(sentences)} 句" if len(sentences) <= 5 else f"{len(sentences)} 句，过多"))

            has_generic = any(phrase in summary for phrase in BANNED_GENERIC)
            r.add(Assertion("摘要无泛泛而谈的套话", level=3).check(
                not has_generic, "通过" if not has_generic else "包含套话"))

        # L3: content — 分析 has bold key insights
        if analysis:
            bold_bullets = re.findall(r"^- \*\*.+\*\*", analysis, re.MULTILINE)
            r.add(Assertion("分析 bullet 包含加粗关键词", level=3).check(
                len(bold_bullets) >= 1, f"找到 {len(bold_bullets)} 个" if len(bold_bullets) >= 1 else "未找到"))

        # L3: content — 建议 is actionable
        if advice:
            has_action_verb = bool(re.search(r"(修改|添加|删除|配置|运行|执行|检查|创建)", advice))
            r.add(Assertion("建议包含可执行动词", level=3).check(
                has_action_verb, "找到" if has_action_verb else "未找到"))

    def _find_report(self) -> Path | None:
        for name in ["report.md", "output.md", "summary.md"]:
            p = self.project_root / name
            if p.is_file():
                return p
        # Also search one level deep
        for p in self.project_root.rglob("*.md"):
            if "output" in str(p) or "report" in str(p):
                return p
        return None

    def _extract_section(self, content: str, name: str) -> str | None:
        pattern = rf"## {re.escape(name)}\s*\n(.*?)(?=\n## |\Z)"
        m = re.search(pattern, content, re.DOTALL)
        return m.group(1).strip() if m else None


def grade(project_root: Path, label: str) -> GradingResult:
    grader = DummyGrader(project_root)
    result = grader.grade(label)
    result.print()
    return result


if __name__ == "__main__":
    import json
    base = Path(__file__).resolve().parent / "iteration-1"
    for track in ["with_skill", "without_skill"]:
        proj = Path(f"/tmp/dummy-test-{track.replace('_', '-')}")
        if proj.exists():
            r = grade(proj, track)
            out_dir = base / track
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / "grading.json", "w") as f:
                json.dump(r.to_dict(), f, ensure_ascii=False, indent=2)
