"""Run the test chat."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    port = int(os.environ.get("COMMUTE_PORT", "47291"))
    uvicorn.run(
        "commute_split.web:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
