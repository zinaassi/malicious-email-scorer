import os

# Set a dummy key before any module imports so genai.Client initializes without error.
# Tests mock client.models.generate_content, so no real API calls are made.
os.environ.setdefault("GEMINI_API_KEY", "test-placeholder-key")
