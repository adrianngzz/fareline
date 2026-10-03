"""Optional ASI:One rewrite for messages the ledger grammar does not match.

Recognized commands never call this. Tests run without ASI1_API_KEY.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_SYSTEM = """You rewrite one carpool-ledger message into a single canonical line.
Return only that line, or the word NONE if it is not a ledger command.

Canonical forms, with real names and amounts from the user:
- I'm in
- I'm out
- I paid $48, Alex and Sam rode.
- I paid $48
- I just paid Alex $45.
- What do I owe?

Do not explain. Do not invent riders or amounts that the user did not state.
"""


def canonicalize(text: str) -> str | None:
    api_key = os.environ.get("ASI1_API_KEY", "").strip()
    if not api_key:
        return None
    payload = {
        "model": "asi1",
        "temperature": 0,
        "max_tokens": 80,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": text},
        ],
    }
    request = urllib.request.Request(
        "https://api.asi1.ai/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    try:
        line = str(body["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        return None
    if not line or line.upper() == "NONE":
        return None
    return line.splitlines()[0].strip().strip('"')
