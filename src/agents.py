import json
import sys
import io
import threading
from gemini_client import GeminiClient

EXEC_TIMEOUT = 5  # seconds — kill any test that takes longer than this


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
        return None, TimeoutError(f"Execution timed out after {timeout}s (likely infinite loop)")
    return result[0], error[0]


def _extract_func(code):
    """Execute code and extract the first callable function."""
    namespace = {}
    exec(code, namespace)
    for name, obj in namespace.items():
        if callable(obj) and not name.startswith("_"):
            return obj
    return None


def _run_tests_quick(func, test_cases, limit=5):
    """Run test cases against a function. Returns list of error strings."""
    errors = []
    for i, tc in enumerate(test_cases[:limit]):
        inputs, expected = tc
        actual, exc = _run_with_timeout(func, inputs)
        if exc is not None:
            errors.append(f"Test {i+1}: {type(exc).__name__}: {exc}")
        elif actual != expected:
            errors.append(f"Test {i+1}: returned {repr(actual)}, expected {repr(expected)}")
    return errors


def _parse_json_response(response: str) -> dict:
    """Try to parse JSON from LLM response, handling markdown code blocks."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(cleaned)


# ============================================================
# AGENT 1: Failure Detection Agent (LLM)
# ============================================================
class FailureDetectionAgent:
    """Analyzes test failures and classifies the error type using LLM."""

    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def run(self, program_name: str, buggy_code: str, test_cases: list) -> dict:
        print(f"\n[Agent 1: FailureDetection] Analyzing failure...")

        # First, run tests in Python to get raw error output
        test_output = []
        try:
            func = _extract_func(buggy_code)
            if func is None:
                test_output.append("ERROR: No callable function found in code")
            else:
                for i, tc in enumerate(test_cases[:5]):
                    inputs, expected = tc
                    actual, exc = _run_with_timeout(func, inputs)
                    if exc is not None:
                        test_output.append(f"Test {i+1}: {type(exc).__name__}: {exc}")
                        print(f"[Agent 1]   ERROR — Test {i+1}: {type(exc).__name__}: {exc}")
                    elif actual != expected:
                        test_output.append(f"Test {i+1}: {program_name}({', '.join(map(repr, inputs))}) returned {repr(actual)}, expected {repr(expected)}")
                        print(f"[Agent 1]   FAIL — Test {i+1}: got {repr(actual)}, expected {repr(expected)}")
                    else:
                        print(f"[Agent 1]   PASS — Test {i+1}")
        except SyntaxError as e:
            test_output.append(f"SyntaxError: {e}")
            print(f"[Agent 1]   SyntaxError: {e}")

        test_output_str = "\n".join(test_output) if test_output else "Unknown failure"

        # Now ask LLM to classify the failure
        prompt = f"""You are a failure detection agent. Analyze the following buggy Python function and its test failures.

Function name: {program_name}

Buggy code:
```python
{buggy_code}
```

Test results:
{test_output_str}

Classify this failure. Respond in this exact JSON format (no markdown, no code blocks, just raw JSON):
{{"error_type": "one of: WrongOutput, RuntimeError, InfiniteLoop, SyntaxError, IndexError, TypeError, Other", "description": "brief description of what is going wrong", "key_observation": "the most important clue about what the bug might be"}}"""

        print(f"[Agent 1] Asking LLM to classify failure...")
        response = self.llm.generate(prompt)
        print(f"[Agent 1] LLM response: {response[:200]}")

        try:
            parsed = _parse_json_response(response)
            print(f"[Agent 1] Error type: {parsed.get('error_type', '?')}")
            print(f"[Agent 1] Description: {parsed.get('description', '?')[:100]}")
            print(f"[Agent 1] Key observation: {parsed.get('key_observation', '?')[:100]}")
            parsed["test_output"] = test_output_str
            return parsed
        except (json.JSONDecodeError, IndexError):
            print(f"[Agent 1] JSON parse failed, using raw test output")
            return {
                "error_type": "Unknown",
                "description": test_output_str[:200],
                "key_observation": test_output_str[:200],
                "test_output": test_output_str,
            }


# ============================================================
# AGENT 2: Code Localization Agent (LLM)
# ============================================================
class CodeLocalizationAgent:
    """Identifies the exact faulty line in the code using LLM."""

    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def run(self, program_name: str, buggy_code: str, failure_info: dict) -> dict:
        print(f"\n[Agent 2: CodeLocalization] Localizing fault...")

        # Number the lines for the LLM
        numbered_code = ""
        for i, line in enumerate(buggy_code.strip().split("\n"), 1):
            numbered_code += f"  {i}: {line}\n"

        prompt = f"""You are a code localization agent. Given a buggy Python function and failure analysis, identify the EXACT faulty line.

Function: {program_name}

Code (with line numbers):
{numbered_code}

Failure analysis:
- Error type: {failure_info.get('error_type', 'Unknown')}
- Description: {failure_info.get('description', 'Unknown')}
- Key observation: {failure_info.get('key_observation', 'Unknown')}
- Test output: {failure_info.get('test_output', 'Unknown')[:300]}

Respond in this exact JSON format (no markdown, no code blocks, just raw JSON):
{{"faulty_line_number": <int>, "faulty_line_content": "the exact line of code that is buggy", "reason": "why this line is incorrect"}}"""

        print(f"[Agent 2] Asking LLM to localize fault...")
        response = self.llm.generate(prompt)
        print(f"[Agent 2] LLM response: {response[:200]}")

        try:
            parsed = _parse_json_response(response)
            print(f"[Agent 2] Faulty line #{parsed.get('faulty_line_number', '?')}: {parsed.get('faulty_line_content', '?')}")
            print(f"[Agent 2] Reason: {parsed.get('reason', '?')[:100]}")
            return parsed
        except (json.JSONDecodeError, IndexError):
            print(f"[Agent 2] JSON parse failed, returning raw response")
            return {
                "faulty_line_number": -1,
                "faulty_line_content": "unknown",
                "reason": response[:200],
            }


# ============================================================
# AGENT 3: Debugging Agent (LLM)
# ============================================================
class DebuggingAgent:
    """Analyzes root cause and proposes a fix strategy using LLM."""

    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def run(self, program_name: str, buggy_code: str, failure_info: dict, localization_info: dict, prev_patch: str = None) -> dict:
        print(f"\n[Agent 3: Debugging] Analyzing root cause...")

        retry_context = ""
        if prev_patch:
            retry_context = f"""

IMPORTANT: A previous fix attempt FAILED. The previous patch was:
```python
{prev_patch}
```
That did NOT work. Propose a DIFFERENT fix strategy."""

        prompt = f"""You are a debugging agent. Analyze the root cause of the bug and propose a fix.

Function: {program_name}

Buggy code:
```python
{buggy_code}
```

Failure analysis:
- Error type: {failure_info.get('error_type', 'Unknown')}
- Description: {failure_info.get('description', 'Unknown')}

Fault localization:
- Faulty line: {localization_info.get('faulty_line_content', 'unknown')}
- Reason: {localization_info.get('reason', 'unknown')}
{retry_context}

Respond in this exact JSON format (no markdown, no code blocks, just raw JSON):
{{"root_cause": "detailed explanation of why the bug occurs", "fix_strategy": "what needs to change and why", "old_code": "the exact buggy expression or line", "new_code": "the exact corrected expression or line"}}"""

        print(f"[Agent 3] Asking LLM for root cause analysis...")
        response = self.llm.generate(prompt)
        print(f"[Agent 3] LLM response: {response[:200]}")

        try:
            parsed = _parse_json_response(response)
            print(f"[Agent 3] Root cause: {parsed.get('root_cause', '?')[:100]}")
            print(f"[Agent 3] Fix: {parsed.get('old_code', '?')} → {parsed.get('new_code', '?')}")
            return parsed
        except (json.JSONDecodeError, IndexError):
            print(f"[Agent 3] JSON parse failed, returning raw response")
            return {
                "root_cause": response[:200],
                "fix_strategy": "unknown",
                "old_code": "unknown",
                "new_code": "unknown",
            }


# ============================================================
# AGENT 4: Patch Generation Agent (LLM)
# ============================================================
class PatchGenerationAgent:
    """Generates the complete corrected function using LLM."""

    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def run(self, program_name: str, buggy_code: str, debugging_info: dict) -> dict:
        print(f"\n[Agent 4: PatchGeneration] Generating corrected code...")

        prompt = f"""You are a patch generation agent. Generate the COMPLETE corrected Python function.

Function: {program_name}

Buggy code:
```python
{buggy_code}
```

Debugging analysis:
- Root cause: {debugging_info.get('root_cause', 'unknown')}
- Fix strategy: {debugging_info.get('fix_strategy', 'unknown')}
- Change: {debugging_info.get('old_code', '?')} → {debugging_info.get('new_code', '?')}

Respond in this exact JSON format (no markdown, no code blocks, just raw JSON):
{{"corrected_code": "the COMPLETE corrected function", "changes_made": "brief summary of what was changed"}}

IMPORTANT: In corrected_code, use \\n for newlines. Return the COMPLETE function including the def line, not just the fixed line."""

        print(f"[Agent 4] Asking LLM to generate patch...")
        response = self.llm.generate(prompt)
        print(f"[Agent 4] LLM response: {response[:300]}")

        try:
            parsed = _parse_json_response(response)
            code = parsed.get("corrected_code", "")
            # Unescape newlines/tabs if they're literal strings
            if "\\n" in code and "\n" not in code:
                code = code.replace("\\n", "\n")
            if "\\t" in code:
                code = code.replace("\\t", "\t")
            # Fix indentation if tabs got lost
            lines = code.split("\n")
            if len(lines) > 1 and lines[1] and not lines[1][0].isspace():
                code = lines[0] + "\n" + "\n".join("    " + l if l.strip() else l for l in lines[1:])
            parsed["corrected_code"] = code

            print(f"[Agent 4] Changes: {parsed.get('changes_made', '?')[:100]}")
            print(f"[Agent 4] Corrected code:")
            for i, line in enumerate(code.strip().split('\n'), 1):
                print(f"[Agent 4]   {i:3d} | {line}")
            return parsed

        except (json.JSONDecodeError, IndexError):
            print(f"[Agent 4] JSON parse failed, extracting code from response")
            code = response.strip()
            if code.startswith("```"):
                code = code.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            if "def " in code:
                start = code.index("def ")
                code = code[start:]
            return {
                "corrected_code": code,
                "changes_made": "Extracted from raw LLM response",
            }


# ============================================================
# AGENT 5: Patch Application Agent (Pure Python — no LLM)
# ============================================================
class PatchApplicationAgent:
    """Applies the generated patch. Pure Python — no LLM needed."""

    def run(self, original_code: str, patched_code: str) -> dict:
        print(f"\n[Agent 5: PatchApplication] Applying patch...")

        if not patched_code or not patched_code.strip():
            print(f"[Agent 5] ERROR: Empty patch")
            return {"success": False, "applied_code": original_code, "error": "Empty patch"}

        # Verify patched code compiles
        try:
            compile(patched_code, "<patch>", "exec")
            print(f"[Agent 5] Patch compiles successfully")
            print(f"[Agent 5] Applied {len(patched_code)} chars of patched code")
            return {"success": True, "applied_code": patched_code, "error": None}
        except SyntaxError as e:
            print(f"[Agent 5] ERROR: Patch has syntax error: {e}")
            return {"success": False, "applied_code": original_code, "error": f"SyntaxError: {e}"}


# ============================================================
# AGENT 6: Validation Agent (Pure Python — no LLM)
# ============================================================
class ValidationAgent:
    """Validates patched code against test cases. Pure Python — no LLM needed."""

    def run(self, program_name: str, patched_code: str, test_cases: list) -> dict:
        results = {
            "all_passed": False,
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "errors": [],
        }

        print(f"\n[Agent 6: Validation] Running {len(test_cases)} tests on patched code...")

        # Check if code compiles
        try:
            compile(patched_code, "<patch>", "exec")
        except SyntaxError as e:
            print(f"[Agent 6] SYNTAX ERROR in patch: {e}")
            results["failed"] = results["total_tests"]
            results["errors"].append(f"SyntaxError: {e}")
            return results

        # Get function
        try:
            func = _extract_func(patched_code)
        except Exception as e:
            print(f"[Agent 6] ERROR executing patch: {e}")
            results["failed"] = results["total_tests"]
            results["errors"].append(f"ExecError: {e}")
            return results

        if func is None:
            print(f"[Agent 6] No callable function found in patched code")
            results["failed"] = results["total_tests"]
            results["errors"].append("No callable function found")
            return results

        # Run all tests
        for i, test_case in enumerate(test_cases):
            inputs = test_case[0]
            expected = test_case[1]

            actual, exc = _run_with_timeout(func, inputs)

            if exc is not None:
                results["failed"] += 1
                msg = f"Test {i+1}: {type(exc).__name__}: {exc}"
                results["errors"].append(msg)
                print(f"[Agent 6]   Test {i+1}: ERROR — {type(exc).__name__}: {exc}")
            elif actual == expected:
                results["passed"] += 1
                print(f"[Agent 6]   Test {i+1}: PASS — {repr(inputs)} → {repr(actual)}")
            else:
                results["failed"] += 1
                msg = f"Test {i+1}: Expected {expected}, got {actual}"
                results["errors"].append(msg)
                print(f"[Agent 6]   Test {i+1}: FAIL — expected {repr(expected)}, got {repr(actual)}")

        results["all_passed"] = results["passed"] == results["total_tests"]
        status = "ALL PASSED" if results["all_passed"] else f"{results['passed']}/{results['total_tests']} passed"
        print(f"[Agent 6] Result: {status}")
        return results
