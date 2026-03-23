"""
Quick test: Run the multi-agent system on just ONE bug (bitcount).
Use this to verify everything works before running the full experiment.

Usage:
    cd src
    python test_one.py
"""

from gemini_client import GeminiClient
from coordinator import RecoveryCoordinator

# The buggy bitcount program (uses ^ instead of &)
buggy_code = """def bitcount(n):
    count = 0
    while n:
        n ^= n - 1
        count += 1
    return count"""

# Test cases: [inputs, expected_output]
test_cases = [
    [[127], 7],
    [[128], 1],
    [[3005], 9],
    [[13], 3],
    [[14], 3],
]

print("=" * 60)
print("TEST RUN: bitcount (single bug)")
print("=" * 60)
print(f"\nBuggy code:\n{buggy_code}\n")
print(f"Test cases: {len(test_cases)}")
print(f"Expected: bitcount(127)=7, bitcount(128)=1\n")

# Initialize
llm = GeminiClient()
coordinator = RecoveryCoordinator(llm)

# Run recovery
result = coordinator.recover("bitcount", buggy_code, test_cases)

# Print result
print("\n" + "=" * 60)
print("RESULT")
print("=" * 60)
print(f"  Success: {result['success']}")
print(f"  Attempts: {result['attempts']}")
print(f"  Time: {result['time_seconds']}s")
print(f"  Error type: {result['error_type']}")
print(f"  API calls: {llm.total_calls}")

if result['success']:
    print(f"\n  Corrected code:\n{result['patch']}")
