"""
Quick test to verify your Gemini API key is working.

Usage:
    cd src
    python test_api.py
"""

from config import GEMINI_API_KEY, GEMINI_MODEL

print("=" * 50)
print("GEMINI API KEY TEST")
print("=" * 50)

# Step 1: Check if key is set
if not GEMINI_API_KEY:
    print("\n[FAIL] GEMINI_API_KEY is not set!")
    print("  → Create a .env file in the project root with:")
    print("    GEMINI_API_KEY=your_key_here")
    exit(1)

print(f"\n[OK] API key found: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-4:]}")
print(f"[OK] Model: {GEMINI_MODEL}")

# Step 2: Try importing the library
print("\n[...] Importing google-genai...")
try:
    from google import genai
    print("[OK] google-genai imported successfully")
except ImportError:
    print("[FAIL] google-genai not installed!")
    print("  → Run: pip install google-genai")
    exit(1)

# Step 3: Try connecting
print(f"\n[...] Sending test request to {GEMINI_MODEL}...")
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents="Reply with exactly: HELLO_TEST_SUCCESS"
    )
    print(f"[OK] Response received: {response.text.strip()}")
except Exception as e:
    print(f"[FAIL] API call failed: {e}")
    print("\n  Common fixes:")
    print("  → Invalid key: Double-check your API key at https://aistudio.google.com/apikey")
    print("  → Wrong model: Try changing GEMINI_MODEL in config.py")
    print("  → Rate limit: Wait a minute and try again")
    exit(1)

print("\n" + "=" * 50)
print("ALL TESTS PASSED — Your API key is working!")
print("=" * 50)
print("\nNext step: python test_one.py")
