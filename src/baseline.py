"""
Baseline: Single-prompt LLM repair (no multi-agent, no iteration).
Used for comparison against the multi-agent approach.

Usage:
    cd src
    python baseline.py
"""

import os
import sys
import io
import json
import csv
import time
import threading

from config import DATASET_DIR, RESULTS_DIR
from gemini_client import GeminiClient

EXEC_TIMEOUT = 5


def _run_with_timeout(func, args, timeout=EXEC_TIMEOUT):
    """Run a function with a timeout. Returns (result, error)."""
    result = [None]
    error = [None]

    def target():
        try:
            r = func(*args)
            if hasattr(r, '__next__'):
                r = list(r)
            result[0] = r
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=target)
    t.daemon = True
    t.start()
    t.join(timeout)

    if t.is_alive():
        return None, TimeoutError("Timed out")
    return result[0], error[0]


def load_programs():
    """Load all QuixBugs programs (same as run_experiment.py)."""
    programs = []
    json_dir = os.path.join(DATASET_DIR, "json_testcases")
    buggy_dir = os.path.join(DATASET_DIR, "python_programs")

    for json_file in sorted(os.listdir(json_dir)):
        if not json_file.endswith(".json"):
            continue

        program_name = json_file.replace(".json", "")
        buggy_file = os.path.join(buggy_dir, f"{program_name}.py")

        if not os.path.exists(buggy_file):
            continue

        with open(buggy_file, "r") as f:
            buggy_code = f.read()

        code_lines = []
        for line in buggy_code.split("\n"):
            if line.startswith('"""') or line.startswith("'''"):
                break
            code_lines.append(line)
        buggy_code_clean = "\n".join(code_lines).strip()

        with open(os.path.join(json_dir, json_file), "r") as f:
            content = f.read().strip()

        test_cases = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                tc = json.loads(line)
                if isinstance(tc, list) and len(tc) == 2:
                    inputs = tc[0] if isinstance(tc[0], list) else [tc[0]]
                    expected = tc[1]
                    test_cases.append([inputs, expected])
            except json.JSONDecodeError:
                continue

        if not test_cases:
            continue

        programs.append({
            "name": program_name,
            "buggy_code": buggy_code_clean,
            "test_cases": test_cases,
        })

    return programs


def validate(program_name: str, patched_code: str, test_cases: list) -> dict:
    """Run test cases against patched code."""
    results = {"all_passed": False, "passed": 0, "failed": 0, "total": len(test_cases)}

    try:
        namespace = {}
        exec(patched_code, namespace)
        func = None
        for name, obj in namespace.items():
            if callable(obj) and not name.startswith("_"):
                func = obj
                break
    except Exception:
        results["failed"] = results["total"]
        return results

    if func is None:
        results["failed"] = results["total"]
        return results

    for i, tc in enumerate(test_cases):
        inputs, expected = tc
        actual, exc = _run_with_timeout(func, inputs)
        if exc is not None:
            results["failed"] += 1
        elif actual == expected:
            results["passed"] += 1
        else:
            results["failed"] += 1

    results["all_passed"] = results["passed"] == results["total"]
    return results


def run_baseline():
    """Run single-prompt baseline on all programs."""
    print("=" * 60)
    print("BASELINE - Single-Prompt LLM Repair")
    print("=" * 60)

    programs = load_programs()
    print(f"\nLoaded {len(programs)} programs.\n")

    llm = GeminiClient()

    # Resume support
    os.makedirs(RESULTS_DIR, exist_ok=True)
    csv_path = os.path.join(RESULTS_DIR, "baseline_results.csv")
    fieldnames = ["program", "success", "attempts", "time_seconds", "passed", "total"]

    completed = set()
    results = []
    if os.path.exists(csv_path):
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed.add(row["program"])
                results.append(row)
        print(f"\nResuming: {len(completed)} programs already completed, skipping them.")

    total_success = sum(1 for r in results if str(r.get("success")) == "True")

    for i, prog in enumerate(programs):
        if prog["name"] in completed:
            print(f"\n[{i+1}/{len(programs)}] {prog['name']} — SKIPPED (already done)")
            continue

        start_time = time.time()
        print(f"\n[{i+1}/{len(programs)}] {prog['name']}")

        # Single prompt — no agents, no iteration
        prompt = f"""Fix the bug in this Python function. Return ONLY the corrected Python code, nothing else. No explanations, no markdown, no backticks.

Buggy code:
{prog['buggy_code']}

Example test case: {prog['name']}({', '.join(map(repr, prog['test_cases'][0][0]))}) should return {repr(prog['test_cases'][0][1])}"""

        patched = llm.generate(prompt)
        cleaned = patched.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Validate
        validation = validate(prog["name"], cleaned, prog["test_cases"])
        elapsed = round(time.time() - start_time, 2)

        success = validation["all_passed"]
        if success:
            total_success += 1

        row = {
            "program": prog["name"],
            "success": success,
            "attempts": 1,
            "time_seconds": elapsed,
            "passed": validation["passed"],
            "total": validation["total"],
        }
        results.append(row)

        # Save after EACH bug
        write_header = not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

        status = "FIXED" if success else "FAILED"
        print(f"  [{status}] {validation['passed']}/{validation['total']} tests passed ({elapsed}s)")
        print(f"  Running total: {total_success}/{i+1}")

    # Summary
    print("\n" + "=" * 60)
    print("BASELINE SUMMARY")
    print("=" * 60)
    print(f"Total programs: {len(results)}")
    print(f"Successfully fixed: {total_success}")
    print(f"Success rate: {total_success/len(results)*100:.1f}%")
    print(f"Total API calls: {llm.total_calls}")
    print(f"Results saved to: {csv_path}")


if __name__ == "__main__":
    run_baseline()
