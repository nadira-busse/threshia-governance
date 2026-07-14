"""
Threshia configuration.

All settings are loaded from environment variables with sensible defaults.
This module is imported by every other component that needs configuration,
so nothing is hardcoded elsewhere.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if it exists (no error if missing)
load_dotenv()

# --- Project paths ---
# Path.resolve() gives absolute paths regardless of where you run the script from.
# In Next.js you'd use process.cwd() — this is the Python equivalent.

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POLICIES_DIR = PROJECT_ROOT / "threshia" / "policies" / "documents"

# Writable runtime data (ChromaDB index, audit log) must not default to
# living inside the installed package location — that's read-only in many
# install scenarios, and conceptually wrong even when it happens to be
# Writable runtime data must not default to the installed package location.
# THRESHIA_RUNTIME_DIR lets you choose another location; when unset,
# runtime data is written relative to the current working directory.
_runtime_dir = os.getenv("THRESHIA_RUNTIME_DIR", "").strip()
RUNTIME_DIR = Path(_runtime_dir).expanduser().resolve() if _runtime_dir else Path.cwd()

CHROMA_PERSIST_DIR = RUNTIME_DIR / ".chroma"
AUDIT_LOG_PATH = RUNTIME_DIR / "audit.jsonl"

# --- LLM provider ---
# THRESHIA_PROVIDER selects which provider threshia/providers/base.py loads.
# Both "mistral" and "openai" are real, working implementations — see
# threshia/providers/base.py for the shared interface they both implement.


def get_provider_name() -> str:
    """
    Return the configured provider name, defaulting to "mistral".

    Exposed as a function (not just the PROVIDER constant below) so tests
    can check the default-fallback behavior directly via monkeypatch,
    without needing to reload this module — reloading would re-run
    load_dotenv() and silently re-populate THRESHIA_PROVIDER from a local
    .env file, defeating a test that just cleared it.
    """
    return os.getenv("THRESHIA_PROVIDER", "mistral").strip().lower()


PROVIDER = get_provider_name()

# Mistral settings
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = "https://api.openai.com/v1"

# --- RAG settings ---
TOP_K_POLICIES = 5  # Number of policy chunks to retrieve per evaluation
