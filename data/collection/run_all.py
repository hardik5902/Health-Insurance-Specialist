"""
Master runner for the full Week 1 data collection pipeline.
Run with: python run_all.py
Or selectively: python run_all.py --steps datasets government
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = {
    "datasets": "01_download_datasets.py",
    "government": "02_scrape_government_sites.py",
    "insurers": "03_scrape_insurance_companies.py",
    "advocacy": "05_scrape_advocacy_orgs.py",
    "states": "06_collect_state_resources.py",
}

STEP_ARGS = {
    "datasets": ["--all"],
    "government": ["--all"],
    "insurers": ["--companies", "all"],
    "advocacy": ["--sources", "all"],
    "states": ["--states", "all"],
}


def run_step(name: str) -> bool:
    script = Path(__file__).parent / SCRIPTS[name]
    cmd = [sys.executable, str(script)] + STEP_ARGS[name]
    print(f"\n{'='*60}")
    print(f"STEP: {name.upper()} — {SCRIPTS[name]}")
    print(f"{'='*60}")
    result = subprocess.run(cmd)
    return result.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full data collection pipeline")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=list(SCRIPTS) + ["all"],
        default=["all"],
        help="Which collection steps to run (default: all)",
    )
    args = parser.parse_args()

    steps = list(SCRIPTS) if "all" in args.steps else args.steps
    failed = []

    for step in steps:
        ok = run_step(step)
        if not ok:
            failed.append(step)
            print(f"  WARNING: Step '{step}' failed — continuing with remaining steps.")

    print(f"\n{'='*60}")
    print("DATA COLLECTION SUMMARY")
    print(f"{'='*60}")
    for step in steps:
        status = "FAILED" if step in failed else "OK"
        print(f"  {step:<20} {status}")

    if failed:
        sys.exit(1)
