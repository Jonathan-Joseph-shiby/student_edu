"""Optional AI normalization boundary.

The deterministic cache is authoritative for Phase 3. This module deliberately
does not call a provider automatically; a future review workflow can invoke it
with ANTHROPIC_API_KEY and validate the returned canonical skill against the
existing skills table before persisting a review decision.
"""

from __future__ import annotations

import json
import sqlite3

from ..config import get_settings


def ai_normalization_available() -> bool:
    return bool(get_settings().anthropic_api_key)


def validate_ai_mapping(connection: sqlite3.Connection, raw_skill: str, response_text: str) -> str | None:
    """Accept only a JSON canonical_skill that already exists in the taxonomy."""
    try:
        payload = json.loads(response_text)
        proposed = payload["canonical_skill"]
        if not isinstance(proposed, str) or not proposed.strip():
            return None
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    row = connection.execute("SELECT canonical_name FROM skills WHERE lower(canonical_name) = lower(?)", (proposed.strip(),)).fetchone()
    return row[0] if row else None
