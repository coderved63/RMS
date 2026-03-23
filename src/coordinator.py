import time
from gemini_client import GeminiClient
from agents import (
    FailureDetectionAgent,
    CodeLocalizationAgent,
    DebuggingAgent,
    PatchGenerationAgent,
    PatchApplicationAgent,
    ValidationAgent,
)
from config import MAX_RETRY_ATTEMPTS


class RecoveryCoordinator:
    """Orchestrates the 6-agent failure recovery loop.

    Agent flow per attempt:
      1. FailureDetectionAgent    (LLM)    — classify the failure
      2. CodeLocalizationAgent    (LLM)    — find the faulty line
      3. DebuggingAgent           (LLM)    — root cause + fix strategy
      4. PatchGenerationAgent     (LLM)    — generate corrected code
      5. PatchApplicationAgent    (Python)  — apply and compile-check
      6. ValidationAgent          (Python)  — run tests

    4 LLM calls per attempt. Max 3 attempts = max 12 LLM calls per bug.
    """

    def __init__(self, llm: GeminiClient):
        self.llm = llm
        self.failure_detector = FailureDetectionAgent(llm)
        self.code_localizer = CodeLocalizationAgent(llm)
        self.debugger = DebuggingAgent(llm)
        self.patch_generator = PatchGenerationAgent(llm)
        self.patch_applier = PatchApplicationAgent()
        self.validator = ValidationAgent()
        print("[Coordinator] Initialized with 6 agents:")
        print("[Coordinator]   1. FailureDetectionAgent   (LLM)")
        print("[Coordinator]   2. CodeLocalizationAgent   (LLM)")
        print("[Coordinator]   3. DebuggingAgent          (LLM)")
        print("[Coordinator]   4. PatchGenerationAgent    (LLM)")
        print("[Coordinator]   5. PatchApplicationAgent   (Python)")
        print("[Coordinator]   6. ValidationAgent         (Python)")
        print(f"[Coordinator] Max retry attempts: {MAX_RETRY_ATTEMPTS}")

    def recover(self, program_name: str, buggy_code: str, test_cases: list) -> dict:
        """Run the full 6-agent recovery loop for a single buggy program."""
        start_time = time.time()
        result = {
            "program": program_name,
            "success": False,
            "attempts": 0,
            "time_seconds": 0,
            "error_type": "",
            "llm_calls": 0,
            "patch": "",
            "agent_log": [],
        }

        print(f"\n{'='*70}")
        print(f"[Coordinator] ========== PROCESSING: {program_name} ==========")
        print(f"{'='*70}")
        print(f"\n[Coordinator] Buggy code:")
        for i, line in enumerate(buggy_code.strip().split('\n'), 1):
            print(f"[Coordinator]   {i:3d} | {line}")
        print(f"\n[Coordinator] Test cases: {len(test_cases)}")
        for i, tc in enumerate(test_cases[:3]):
            print(f"[Coordinator]   Test {i+1}: input={tc[0]} → expected={tc[1]}")
        if len(test_cases) > 3:
            print(f"[Coordinator]   ... and {len(test_cases)-3} more")

        prev_patch = None

        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            result["attempts"] = attempt
            llm_before = self.llm.total_calls

            print(f"\n{'~'*70}")
            print(f"[Coordinator] ===== ATTEMPT {attempt} of {MAX_RETRY_ATTEMPTS} =====")
            print(f"{'~'*70}")

            # ---- AGENT 1: Failure Detection (LLM) ----
            print(f"\n[Coordinator] >>> STEP 1/6: Failure Detection")
            failure_info = self.failure_detector.run(program_name, buggy_code, test_cases)
            result["error_type"] = failure_info.get("error_type", "Unknown")
            result["agent_log"].append({"agent": "FailureDetection", "attempt": attempt, "output": failure_info})

            # ---- AGENT 2: Code Localization (LLM) ----
            print(f"\n[Coordinator] >>> STEP 2/6: Code Localization")
            localization_info = self.code_localizer.run(program_name, buggy_code, failure_info)
            result["agent_log"].append({"agent": "CodeLocalization", "attempt": attempt, "output": localization_info})

            # ---- AGENT 3: Debugging (LLM) ----
            print(f"\n[Coordinator] >>> STEP 3/6: Debugging & Root Cause Analysis")
            debugging_info = self.debugger.run(program_name, buggy_code, failure_info, localization_info, prev_patch)
            result["agent_log"].append({"agent": "Debugging", "attempt": attempt, "output": debugging_info})

            # ---- AGENT 4: Patch Generation (LLM) ----
            print(f"\n[Coordinator] >>> STEP 4/6: Patch Generation")
            patch_info = self.patch_generator.run(program_name, buggy_code, debugging_info)
            patched_code = patch_info.get("corrected_code", "")
            result["agent_log"].append({"agent": "PatchGeneration", "attempt": attempt, "output": {
                "changes_made": patch_info.get("changes_made", ""),
                "code_length": len(patched_code),
            }})

            # ---- AGENT 5: Patch Application (Python) ----
            print(f"\n[Coordinator] >>> STEP 5/6: Patch Application")
            application_result = self.patch_applier.run(buggy_code, patched_code)
            result["agent_log"].append({"agent": "PatchApplication", "attempt": attempt, "output": application_result})

            if not application_result["success"]:
                print(f"\n[Coordinator] Patch application failed — skipping to next attempt")
                prev_patch = patched_code
                result["llm_calls"] = self.llm.total_calls - llm_before + result.get("llm_calls", 0)
                continue

            # ---- AGENT 6: Validation (Python) ----
            print(f"\n[Coordinator] >>> STEP 6/6: Validation")
            validation = self.validator.run(program_name, application_result["applied_code"], test_cases)
            result["agent_log"].append({"agent": "Validation", "attempt": attempt, "output": validation})

            llm_this_attempt = self.llm.total_calls - llm_before
            print(f"\n[Coordinator] Attempt {attempt} summary: {validation['passed']}/{validation['total_tests']} passed, {llm_this_attempt} LLM calls")

            if validation["all_passed"]:
                result["success"] = True
                result["patch"] = application_result["applied_code"]
                result["time_seconds"] = round(time.time() - start_time, 2)
                result["llm_calls"] = self.llm.total_calls
                print(f"\n{'*'*70}")
                print(f"[Coordinator] SUCCESS! Fixed '{program_name}' on attempt {attempt}!")
                print(f"[Coordinator] Time: {result['time_seconds']}s | LLM calls this bug: {llm_this_attempt}")
                print(f"{'*'*70}")
                return result

            # Failed — save for retry context
            prev_patch = patched_code
            print(f"\n[Coordinator] Fix failed — will retry with error feedback")

        result["time_seconds"] = round(time.time() - start_time, 2)
        result["llm_calls"] = self.llm.total_calls
        print(f"\n{'X'*70}")
        print(f"[Coordinator] FAILED '{program_name}' after {MAX_RETRY_ATTEMPTS} attempts ({result['time_seconds']}s)")
        print(f"{'X'*70}")
        return result
