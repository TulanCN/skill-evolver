#!/usr/bin/env python3
"""Experiment history management.

Usage:
  python3 evolver/scripts/aggregate.py init <experiments_dir> <skill_name>
      Initialize experiment tracking for a skill.

  python3 evolver/scripts/aggregate.py log <experiments_dir> <iteration> <commit> <l1> <l2> <l3> <aggregate> <delta> <status> <hypothesis>
      Append an iteration result to experiments.tsv.

  python3 evolver/scripts/aggregate.py summary <experiments_dir>
      Print experiment summary.
"""

import sys
from pathlib import Path
from datetime import datetime

TSV_HEADER = "iteration\tcommit\tl1\tl2\tl3\taggregate\tdelta\tstatus\thypothesis\ttimestamp"


def cmd_init(exp_dir: str, skill_name: str):
    path = Path(exp_dir) / skill_name
    path.mkdir(parents=True, exist_ok=True)
    tsv = path / "experiments.tsv"
    if not tsv.exists():
        tsv.write_text(TSV_HEADER + "\n")
    (path / ".gitkeep").touch(exist_ok=True)
    print(f"Initialized experiments at {path}")
    print(f"  TSV: {tsv}")


def cmd_log(exp_dir: str, args: list):
    if len(args) < 9:
        print("ERROR: need iteration commit l1 l2 l3 aggregate delta status hypothesis")
        sys.exit(1)

    iteration, commit, l1, l2, l3, aggregate, delta, status = args[:8]
    hypothesis = " ".join(args[8:])
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    tsv = Path(exp_dir) / "experiments.tsv"
    with open(tsv, "a") as f:
        f.write(f"{iteration}\t{commit}\t{l1}\t{l2}\t{l3}\t{aggregate}\t{delta}\t{status}\t{hypothesis}\t{timestamp}\n")

    print(f"Logged iteration {iteration}: status={status} aggregate={aggregate} delta={delta}")


def cmd_summary(exp_dir: str):
    tsv = Path(exp_dir) / "experiments.tsv"
    if not tsv.exists():
        print("No experiments recorded.")
        return

    lines = [l.strip() for l in tsv.read_text().strip().split("\n") if l.strip()]
    if len(lines) < 2:
        print("No experiments recorded.")
        return

    header = lines[0].split("\t")
    records = [dict(zip(header, l.split("\t"))) for l in lines[1:]]

    kept = [r for r in records if r.get("status") == "keep"]
    discarded = [r for r in records if r.get("status") == "discard"]
    baseline = [r for r in records if r.get("status") == "baseline"]

    print(f"\nExperiment Summary ({len(records)} iterations)")
    print(f"  Kept:     {len(kept)}")
    print(f"  Discarded: {len(discarded)}")
    print(f"  Baseline:  {len(baseline)}")

    if baseline:
        b = baseline[0]
        print(f"\n  Baseline score: {b.get('aggregate', 'N/A')}")
    if kept:
        best = max(kept, key=lambda r: float(r.get("aggregate", 0)))
        print(f"  Best score:     {best.get('aggregate', 'N/A')} (iter {best.get('iteration', '?')})")
        print(f"  Best hypothesis: {best.get('hypothesis', 'N/A')}")

    # Show trajectory
    all_records = [r for r in records if r.get("status") != "discard"]
    if len(all_records) > 1:
        scores = " → ".join(r.get("aggregate", "?") for r in all_records)
        print(f"\n  Score trajectory: {scores}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    exp_dir = sys.argv[2]

    if cmd == "init":
        cmd_init(exp_dir, sys.argv[3] if len(sys.argv) > 3 else "default")
    elif cmd == "log":
        cmd_log(exp_dir, sys.argv[3:])
    elif cmd == "summary":
        cmd_summary(exp_dir)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
