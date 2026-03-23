"""
Main experiment runner.
Runs the multi-agent recovery system on all QuixBugs programs with JSON test cases.

Usage:
    cd src
    python run_experiment.py
"""

import os
import sys
import json
import csv
import time

from config import DATASET_DIR, RESULTS_DIR
from gemini_client import GeminiClient
from coordinator import RecoveryCoordinator


def load_programs():
    """Load all QuixBugs programs that have JSON test cases."""
    programs = []

    json_dir = os.path.join(DATASET_DIR, "json_testcases")
    buggy_dir = os.path.join(DATASET_DIR, "python_programs")

    for json_file in sorted(os.listdir(json_dir)):
        if not json_file.endswith(".json"):
            continue

        program_name = json_file.replace(".json", "")
        buggy_file = os.path.join(buggy_dir, f"{program_name}.py")

        if not os.path.exists(buggy_file):
            print(f"[Skip] {program_name}: no buggy file found")
            continue

        # Load buggy code
        with open(buggy_file, "r") as f:
            buggy_code = f.read()

        # Extract just the function (before the docstring/comments)
        code_lines = []
        for line in buggy_code.split("\n"):
            if line.startswith('"""') or line.startswith("'''"):
                break
            code_lines.append(line)
        buggy_code_clean = "\n".join(code_lines).strip()

        # Load test cases
        with open(os.path.join(json_dir, json_file), "r") as f:
            content = f.read().strip()

        # Each line in the JSON file is a test case: [[inputs], expected_output]
        test_cases = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                tc = json.loads(line)
                # tc is [[input1, input2, ...], expected_output]
                if isinstance(tc, list) and len(tc) == 2:
                    inputs = tc[0] if isinstance(tc[0], list) else [tc[0]]
                    expected = tc[1]
                    test_cases.append([inputs, expected])
            except json.JSONDecodeError:
                continue

        if not test_cases:
            print(f"[Skip] {program_name}: no valid test cases")
            continue

        programs.append({
            "name": program_name,
            "buggy_code": buggy_code_clean,
            "test_cases": test_cases,
        })

    return programs


def run_experiment():
    """Run the multi-agent recovery system on all programs."""
    print("=" * 60)
    print("FAILURE RECOVERY SYSTEM - Multi-Agent Experiment")
    print("=" * 60)

    # Load programs
    programs = load_programs()
    print(f"\nLoaded {len(programs)} programs with test cases.\n")

    # Initialize
    llm = GeminiClient()
    coordinator = RecoveryCoordinator(llm)

    # Results storage — load any previous partial results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    csv_path = os.path.join(RESULTS_DIR, "results.csv")
    json_path = os.path.join(RESULTS_DIR, "results_detailed.json")
    fieldnames = ["program", "success", "attempts", "time_seconds", "error_type"]

    # Check which programs were already completed (resume support)
    completed = set()
    results = []
    if os.path.exists(csv_path):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["program"])
                results.append(row)
        print(f"\nResuming: {len(completed)} programs already completed, skipping them.")

    total_success = sum(1 for r in results if r.get("success") == "True" or r.get("success") is True)

    # Run on each program
    for i, prog in enumerate(programs):
        # Skip already completed programs (resume support)
        if prog["name"] in completed:
            print(f"\n[{i+1}/{len(programs)}] {prog['name']} — SKIPPED (already done)")
            continue

        print(f"\n[{i+1}/{len(programs)}] {prog['name']}")
        result = coordinator.recover(
            program_name=prog["name"],
            buggy_code=prog["buggy_code"],
            test_cases=prog["test_cases"],
        )

        if result["success"]:
            total_success += 1

        print(f"  Running total: {total_success}/{i+1} fixed")

        # Save after EACH bug (never lose progress)
        row = {
            "program": result["program"],
            "success": result["success"],
            "attempts": result["attempts"],
            "time_seconds": result["time_seconds"],
            "error_type": result["error_type"],
        }
        results.append(row)

        # Append to CSV
        write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

        # Save full detailed JSON (overwrite each time)
        # Load existing detailed results
        detailed = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    detailed = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                detailed = []
        detailed.append(result)
        with open(json_path, "w") as f:
            json.dump(detailed, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 60)
    print("EXPERIMENT SUMMARY")
    print("=" * 60)
    print(f"Total programs: {len(results)}")
    print(f"Successfully fixed: {total_success}")
    print(f"Success rate: {total_success/len(results)*100:.1f}%")

    pass_at_1 = sum(1 for r in results if str(r["success"]) == "True" and str(r["attempts"]) == "1")
    print(f"Pass@1: {pass_at_1}/{len(results)} ({pass_at_1/len(results)*100:.1f}%)")

    fixed = [r for r in results if str(r["success"]) == "True"]
    if fixed:
        avg_time = sum(float(r["time_seconds"]) for r in fixed) / len(fixed)
        avg_attempts = sum(int(r["attempts"]) for r in fixed) / len(fixed)
        print(f"Avg time (fixed bugs): {avg_time:.1f}s")
        print(f"Avg attempts (fixed bugs): {avg_attempts:.1f}")

    print(f"\nTotal API calls: {llm.total_calls}")
    print(f"Results saved to: {csv_path}")
    print(f"Detailed log saved to: {json_path}")


if __name__ == "__main__":
    run_experiment()
