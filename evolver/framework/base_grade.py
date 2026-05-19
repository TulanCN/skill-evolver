#!/usr/bin/env python3
"""Base grading framework for skill evals.

Each skill inherits BaseGrader and implements check_all().
"""

import json
from pathlib import Path
from typing import Optional


class Assertion:
    """A single testable assertion about a skill's output."""

    def __init__(self, text: str, level: int = 1):
        self.text = text
        self.level = level  # 1=结构, 2=模板, 3=内容
        self._passed: Optional[bool] = None
        self._evidence: str = ""

    def check(self, passed: bool, evidence: str = "") -> "Assertion":
        self._passed = passed
        self._evidence = evidence
        return self

    def pass_(self, evidence: str = "") -> "Assertion":
        return self.check(True, evidence)

    def fail(self, evidence: str = "") -> "Assertion":
        return self.check(False, evidence)

    @property
    def passed(self) -> bool:
        return self._passed is True

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "level": self.level,
            "passed": self._passed,
            "evidence": self._evidence,
        }


class GradingResult:
    """Aggregated grading result for one test run."""

    def __init__(self, label: str, project_root: Optional[Path] = None):
        self.label = label
        self.project_root = project_root
        self.assertions: list[Assertion] = []

    def add(self, assertion: Assertion) -> "GradingResult":
        self.assertions.append(assertion)
        return self

    @property
    def passed(self) -> int:
        return sum(1 for a in self.assertions if a.passed)

    @property
    def total(self) -> int:
        return len(self.assertions)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    def stats(self) -> dict:
        if not self.project_root or not self.project_root.exists():
            return {"total_dirs": 0, "total_files": 0}
        all_items = list(self.project_root.rglob("*"))
        dirs = sum(1 for f in all_items if f.is_dir())
        files = sum(1 for f in all_items if f.is_file() and ".snapshots" not in str(f))
        return {"total_dirs": dirs, "total_files": files}

    def by_level(self) -> dict:
        levels = {1: [], 2: [], 3: []}
        for a in self.assertions:
            if a._passed is not None:
                levels[a.level].append(a.passed)
        return {
            f"L{lv}": f"{sum(vals)}/{len(vals)}" if vals else "N/A"
            for lv, vals in levels.items()
        }

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "passed": self.passed,
            "total": self.total,
            "pass_rate": self.pass_rate,
            "by_level": self.by_level(),
            "stats": self.stats(),
            "expectations": [a.to_dict() for a in self.assertions],
        }

    def print(self):
        print(f"\n{'='*60}")
        print(f"Grading: {self.label}")
        if self.project_root:
            print(f"Project: {self.project_root}")
        print(f"Results: {self.passed}/{self.total} ({self.pass_rate:.1%})")
        print(f"By level: {self.by_level()}")
        print(f"{'='*60}")
        for a in self.assertions:
            status = "PASS" if a.passed else "FAIL"
            print(f"  [L{a.level}] [{status}] {a.text}")
            if not a.passed and a._evidence:
                print(f"         → {a._evidence}")


class BaseGrader:
    """Base class for skill-specific graders.

    Subclass and override check_all() to define assertions.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def check_all(self, result: GradingResult) -> None:
        """Override this to add all assertions for the skill."""
        raise NotImplementedError

    def grade(self, label: str) -> GradingResult:
        result = GradingResult(label, self.project_root)
        self.check_all(result)
        return result


def compare_results(with_skill: GradingResult, without_skill: GradingResult):
    """Print a comparison summary."""
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    for r in [with_skill, without_skill]:
        print(f"{r.label}: {r.passed}/{r.total} ({r.pass_rate:.1%}) "
              f"[{r.stats()['total_dirs']} dirs, {r.stats()['total_files']} files] "
              f"L1={r.by_level().get('L1','N/A')} L2={r.by_level().get('L2','N/A')} L3={r.by_level().get('L3','N/A')}")
    delta = with_skill.pass_rate - without_skill.pass_rate
    print(f"\nDelta (with - without): {delta:+.1%}")
