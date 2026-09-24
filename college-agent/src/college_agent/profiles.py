"""Minimal student-profile store (one JSON file).

Good enough for a demo. For real users you'd want per-user auth, encryption at
rest, and a delete tool, since profiles describe minors.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

STORE = Path(os.environ.get("PROFILE_STORE", "/tmp/college_agent_profiles.json"))
_lock = threading.Lock()


def _load() -> dict:
    return json.loads(STORE.read_text()) if STORE.exists() else {}


def save(profile: dict, profile_id: str | None = None) -> str:
    with _lock:
        data = _load()
        pid = profile_id or uuid.uuid4().hex[:10]
        data[pid] = {**data.get(pid, {}), **{k: v for k, v in profile.items() if v is not None}}
        STORE.write_text(json.dumps(data, indent=2))
        return pid


def get(profile_id: str) -> dict | None:
    return _load().get(profile_id)
