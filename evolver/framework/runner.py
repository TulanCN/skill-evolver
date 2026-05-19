#!/usr/bin/env python3
"""CLI runner for skill evals.

Usage:
  python3 evolver/framework/runner.py grade <evals_dir> <project_dir> <label>
      Run grading on a completed test run.

  python3 evolver/framework/runner.py report <experiments_dir>
      Aggregate all experiment results.

  python3 evolver/framework/runner.py score <grading.json>
      Compute weighted aggregate score from a grading result.
"""

import json
import sys
from pathlib import Path

# L1/L2/L3 weights for aggregate scoring
WEIGHTS = {"L1": 0.2, "L2": 0.3, "L3": 0.5}


def compute_score(grading_data: dict) -> dict:
    """Compute weighted aggregate score from grading result."""
    by_level = grading_data.get("by_level", {})
    scores = {}
    for level in ["L1", "L2", "L3"]:
        entry = by_level.get(level, "0/0")
        if "/" in entry:
            parts = entry.split("/")
            passed = float(parts[0])
            total = float(parts[1])
            scores[level] = passed / total if total > 0 else 0.0
        else:
            scores[level] = 0.0

    aggregate = sum(scores[lv] * WEIGHTS[lv] for lv in ["L1", "L2", "L3"])
    return {
        "L1": scores["L1"],
        "L2": scores["L2"],
        "L3": scores["L3"],
        "aggregate": round(aggregate, 4),
    }


def cmd_grade(evals_dir: str, project_dir: str, label: str):
    evals_path = Path(evals_dir)
    grader_path = evals_path / "grade.py"

    if not grader_path.exists():
        print(f"ERROR: No grade.py found at {grader_path}")
        sys.exit(1)

    sys.path.insert(0, str(evals_path))
    import importlib
    mod = importlib.import_module("grade")

    proj = Path(project_dir)
    if not proj.exists():
        print(f"ERROR: Project dir not found: {proj}")
        sys.exit(1)

    result = mod.grade(proj, label)

    # Save grading.json to project directory
    out_path = proj / "grading.json"
    with open(out_path, "w") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    print(f"Saved: {out_path}")

    return result


def cmd_score(grading_path: str):
    with open(grading_path) as f:
        data = json.load(f)

    scores = compute_score(data)
    print(f"Score for {grading_path}:")
    print(f"  L1={scores['L1']:.3f}  L2={scores['L2']:.3f}  L3={scores['L3']:.3f}")
    print(f"  Aggregate={scores['aggregate']:.4f}")
    return scores


def cmd_report(experiments_dir: str):
    exp_path = Path(experiments_dir)
    print(f"\n{'='*70}")
    print(f"EVOLUTION EXPERIMENT REPORT: {exp_path.name}")
    print(f"{'='*70}")

    tsv_path = exp_path / "experiments.tsv"
    if tsv_path.exists():
        with open(tsv_path) as f:
            lines = f.readlines()
        if lines:
            print(f"\n{lines[0].strip()}")
            for line in lines[1:]:
                print(line.strip())

    # Show latest iteration details
    iters = sorted(exp_path.glob("iter-*"))
    if iters:
        latest = iters[-1]
        print(f"\nLatest iteration: {latest.name}")
        for config in ["baseline", "modified"]:
            for track in ["with_skill", "without_skill"]:
                gpath = latest / config / track / "grading.json"
                if gpath.exists():
                    scores = cmd_score(str(gpath))
                    print(f"  {config}/{track}: aggregate={scores['aggregate']:.4f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "grade" and len(sys.argv) >= 5:
        cmd_grade(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "score" and len(sys.argv) >= 3:
        cmd_score(sys.argv[2])
    elif cmd == "report" and len(sys.argv) >= 3:
        cmd_report(sys.argv[2])
    else:
        print(f"Unknown command or insufficient arguments: {sys.argv[1:]}")
        print(__doc__)
        sys.exit(1)
