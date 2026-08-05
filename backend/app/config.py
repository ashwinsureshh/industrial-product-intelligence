"""Runtime configuration.

The default is deliberately `demo`: the app must be fully explorable by a
reviewer who has no API key and no intention of spending money. Live mode is
opt-in per request, with the caller supplying their own key.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
CACHE_DIR = Path(os.getenv("PI_CACHE_DIR", APP_DIR.parent / ".cache"))

# Server-side key is optional. If absent, live mode simply requires the caller
# to pass one; if present it acts as the fallback for local development.
SERVER_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Allowing live mode at all is a deployment decision. Set PI_ALLOW_LIVE=0 when
# hosting a public demo so no request can ever trigger a paid call.
ALLOW_LIVE = os.getenv("PI_ALLOW_LIVE", "1") != "0"

# Whether a request with no key may fall back to the server's own key. Off by
# default so a hosted instance never spends the owner's credits.
ALLOW_SERVER_KEY_FALLBACK = os.getenv("PI_ALLOW_SERVER_KEY", "0") == "1"

MODEL = os.getenv("PI_MODEL", "claude-sonnet-5")
MAX_TOKENS = int(os.getenv("PI_MAX_TOKENS", "4096"))

# Cache is on by default: identical inputs never pay twice.
CACHE_ENABLED = os.getenv("PI_CACHE", "1") != "0"

CORS_ORIGINS = os.getenv(
    "PI_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
).split(",")
