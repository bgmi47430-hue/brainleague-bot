"""Quiz timeout and result publishing helpers."""

from __future__ import annotations

import asyncio
import logging
from html import escape

from telegram import Bot
from telegram.constants import ParseMode

from config import Config
from database import AnswerRecord, Database

logger = logging.getLogger(__name__)

MEDALS = ("🥇", "🥈", "🥉")


def display_name(record: AnswerRecord | None) -> str:
    if record is None:
        return "—"
    name = record.first_name or (f"@{record.username}" if record.username else f"User {record.user_id}")
    return escape(name)


async def build_results_message(db: Database) -> str:
    winners = await db.winners(3)
    stats = await db.stats()
    winner_lines = [f"{medal} {display_name(winners[index] if index < len(winners) else None)}" for index, medal in enumerate(MEDALS)]
    return "\n".join(
        [
            "🏆 <b>Today's Quiz Results</b>",
            "",
            *winner_lines,
            "",
            f"Participants: {stats['participants']}",
            f"Correct: {stats['correct']}",
            f"Wrong: {stats['wrong']}",
        ]
    )


async def publish_results(bot: Bot, db: Database, config: Config) -> None:
    """End the current quiz and post final results to the configured channel."""
    try:
        await db.end_quiz()
        message = await build_results_message(db)
        await bot.send_message(chat_id=config.channel_id, text=message, parse_mode=ParseMode.HTML)
        logger.info("Quiz results published to channel %s", config.channel_id)
    except Exception:
        logger.exception("Failed to publish quiz results")


async def quiz_timeout(bot: Bot, db: Database, config: Config) -> None:
    """Wait for the configured quiz duration, then publish results if still active."""
    try:
        await asyncio.sleep(config.quiz_duration_seconds)
        state = await db.get_state()
        if state.get("active"):
            logger.info("Quiz timeout reached; publishing results")
            await publish_results(bot, db, config)
    except asyncio.CancelledError:
        logger.info("Quiz timeout task cancelled")
        raise
    except Exception:
        logger.exception("Quiz timeout task failed")
