"""Test chat and the shared inbound HTTP path."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from commute_split.handle import handle_inbound, public_state
from commute_split.ledger import Ledger

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
SOURCES = {"test_chat", "spectrum", "fetch"}


class IncomingMessage(BaseModel):
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1)
    source: str = "test_chat"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    path = db_path or os.environ.get("COMMUTE_DB_PATH", "data/commute.db")
    application = FastAPI(title="Fareline")
    application.state.ledger = Ledger(path)

    @application.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @application.get("/api/state")
    def state() -> dict:
        return public_state(application.state.ledger)

    @application.post("/api/messages")
    def post_message(body: IncomingMessage) -> dict:
        sender = " ".join(body.sender.split())
        text = " ".join(body.text.split())
        if not sender:
            raise HTTPException(status_code=400, detail="Pick who is speaking.")
        if not text:
            raise HTTPException(status_code=400, detail="Write a message first.")
        if body.source not in SOURCES:
            raise HTTPException(status_code=400, detail="Unknown message source.")
        result = handle_inbound(
            application.state.ledger,
            sender,
            text,
            source=body.source,
        )
        return {
            "reply": result.reply,
            "sender": result.sender,
            "changed_balances": result.changed_balances,
            "state": public_state(application.state.ledger),
        }

    @application.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    application.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")
    return application


app = create_app()
