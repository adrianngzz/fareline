"""Fetch.ai uAgent. Chat protocol in, SQLite ledger out.

Registration needs AGENT_SEED and a reachable Agentverse mailbox. The test
chat does not start this process.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from commute_split.fetch_bridge import apply_fetch_text, load_sender_map
from commute_split.ledger import Ledger

AGENT_NAME = "Fareline"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"


def require_seed() -> str:
    seed = os.environ.get("AGENT_SEED", "").strip()
    if not seed:
        raise SystemExit(
            "AGENT_SEED is not set, so Fareline cannot register on Agentverse.\n"
            "Create a seed, export AGENT_SEED, then run python -m commute_split.fetch_agent.\n"
            "Open the inspector URL, choose Connect, then Mailbox.\n"
            "The test chat does not need AGENT_SEED.\n"
            "Docs: https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents"
        )
    return seed


def build_agent():
    from uagents import Agent

    port = int(os.environ.get("UAGENT_PORT", "8011"))
    return Agent(
        name=AGENT_NAME,
        seed=require_seed(),
        port=port,
        mailbox=True,
        publish_agent_details=True,
        description=(
            "Fareline splits a shared Uber or Lyft for the intern carpool. "
            "Whoever paid tells the chat who rode. Fareline records the even "
            "split and who owes whom. It does not book the car."
        ),
        handle="fareline",
        readme_path=str(README_PATH) if README_PATH.exists() else None,
    )


def attach_chat(agent, ledger: Ledger, sender_map: dict[str, str]) -> None:
    from uagents import Context, Protocol
    from uagents_core.contrib.protocols.chat import (
        ChatAcknowledgement,
        ChatMessage,
        TextContent,
        chat_protocol_spec,
    )

    chat_proto = Protocol(spec=chat_protocol_spec)

    def create_text_chat(text: str) -> ChatMessage:
        return ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[TextContent(type="text", text=text)],
        )

    @chat_proto.on_message(ChatMessage)
    async def handle_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.now(timezone.utc),
                acknowledged_msg_id=msg.msg_id,
            ),
        )
        text = "\n".join(
            item.text for item in msg.content if isinstance(item, TextContent)
        ).strip()
        if not text:
            return
        outcome = await asyncio.to_thread(
            apply_fetch_text, ledger, sender, text, sender_map
        )
        ctx.logger.info("ledger applied=%s sender=%s", outcome.applied, sender)
        await ctx.send(sender, create_text_chat(outcome.reply))

    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
        ctx.logger.info(
            "ack from %s for %s", sender, msg.acknowledged_msg_id
        )

    agent.include(chat_proto, publish_manifest=True)


def main() -> None:
    ledger = Ledger(os.environ.get("COMMUTE_DB_PATH", "data/commute.db"))
    sender_map = load_sender_map()
    agent = build_agent()
    attach_chat(agent, ledger, sender_map)
    agent.run()


if __name__ == "__main__":
    main()
