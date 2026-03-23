import time
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, DELAY_BETWEEN_CALLS


class GeminiClient:
    """Wrapper for Gemini API with rate limiting."""

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model = GEMINI_MODEL
        self.last_call_time = 0
        self.total_calls = 0
        print(f"[GeminiClient] Initialized with model: {self.model}")
        print(f"[GeminiClient] Rate limit delay: {DELAY_BETWEEN_CALLS}s between calls")

    def _rate_limit(self):
        """Enforce delay between API calls to respect free tier limits."""
        elapsed = time.time() - self.last_call_time
        if elapsed < DELAY_BETWEEN_CALLS:
            wait = round(DELAY_BETWEEN_CALLS - elapsed, 1)
            print(f"  [GeminiClient] Rate limiting... waiting {wait}s")
            time.sleep(DELAY_BETWEEN_CALLS - elapsed)

    def generate(self, prompt: str, max_retries: int = 4) -> str:
        """Send a prompt to Gemini and return the text response."""
        self._rate_limit()

        prompt_preview = prompt[:100].replace('\n', ' ')
        print(f"\n  [GeminiClient] === API Call #{self.total_calls + 1} ===")
        print(f"  [GeminiClient] Prompt preview: {prompt_preview}...")
        print(f"  [GeminiClient] Prompt length: {len(prompt)} chars")

        for attempt in range(max_retries + 1):
            try:
                print(f"  [GeminiClient] Sending request to {self.model} (attempt {attempt+1}/{max_retries+1})...", flush=True)
                start = time.time()

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=2048,
                    ),
                )

                elapsed = round(time.time() - start, 1)
                self.last_call_time = time.time()
                self.total_calls += 1

                if response.text:
                    resp_preview = response.text[:200].replace('\n', ' ')
                    print(f"  [GeminiClient] Response received in {elapsed}s ({len(response.text)} chars)")
                    print(f"  [GeminiClient] Response preview: {resp_preview}...")
                    return response.text.strip()

                print(f"  [GeminiClient] WARNING: Empty response received in {elapsed}s")
                return ""

            except Exception as e:
                elapsed = round(time.time() - start, 1)
                if attempt < max_retries:
                    # Exponential backoff: 10s, 20s, 40s, 80s
                    wait = 10 * (2 ** attempt)
                    print(f"  [GeminiClient] ERROR after {elapsed}s: {e}")
                    print(f"  [GeminiClient] Retrying in {wait}s (attempt {attempt+2}/{max_retries+1})...")
                    time.sleep(wait)
                else:
                    print(f"  [GeminiClient] FAILED after {max_retries + 1} attempts ({elapsed}s): {e}")
                    return f"ERROR: {e}"

        return "ERROR: Unknown failure"
