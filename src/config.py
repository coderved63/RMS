import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ============================================================
# Set GEMINI_API_KEY in .env file in the project root
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Model: Gemini 3.1 Flash Lite — fastest, most generous free tier
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

# Rate limiting
REQUESTS_PER_MINUTE = 10
DELAY_BETWEEN_CALLS = 4  # seconds (10 RPM = 6s min, 4s with burst tolerance)

# Recovery settings
MAX_RETRY_ATTEMPTS = 3

# Paths
DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "quixbugs")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
