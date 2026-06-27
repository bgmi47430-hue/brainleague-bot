"""Telegram command and message handlers for the quiz bot."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, Concatenate, ParamSpec

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from config import CONFIG
from database import Database
from scheduler import build_results_message, publish_results, quiz_timeout

logger = logging.getLogger(__name__)
P = ParamSpec("P")
Handler = Callable[Concatenate[Update, ContextTypes.DEFAULT_TYPE, P], Awaitable[None]]


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == CONFIG.admin_id)


def admin_only(func: Handler[P]) -> Handler[P]:
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            if not is_admin(update):
                if update.effective_message:
                    await update.effective_message.reply_text("Only the quiz administrator can use this command.")
                return
            await func(update, context, *args, **kwargs)
        except Exception:
            logger.exception("Admin command failed: %s", func.__name__)
            if update.effective_message:
                await update.effective_message.reply_text("An error occurred while processing the command.")

    return wrapper


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    db = context.application.bot_data.get("db")
    if not isinstance(db, Database):
        raise RuntimeError("Database is not initialized")
    return db


def cancel_quiz_task(context: ContextTypes.DEFAULT_TYPE) -> None:
    task = context.application.bot_data.pop("quiz_task", None)
    if isinstance(task, asyncio.Task) and not task.done():
        task.cancel()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        text = (
            "🤖 <b>Telegram Quiz Bot</b>\n\n"
            "Users answer by sending a private message to this bot. Duplicate answers are ignored.\n\n"
            "<b>Admin commands</b>\n"
            "/startquiz &lt;correct_answer&gt; - Start a 5-minute quiz\n"
            "/endquiz - End the active quiz and publish results\n"
            "/reset - Clear quiz state and answers\n"
            "/status - Show current quiz status\n"
            "/winners - Show current top three winners\n"
            "/help - Show this help message"
        )
        if update.effective_message:
            await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("Failed to send help")


@admin_only
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.effective_message.reply_text("Usage: /startquiz <correct_answer>")
        return
    correct_answer = " ".join(context.args).strip()
    if not correct_answer:
        await update.effective_message.reply_text("The correct answer cannot be empty.")
        return

    db = get_db(context)
    cancel_quiz_task(context)
    await db.start_quiz(correct_answer)
    context.application.bot_data["quiz_task"] = asyncio.create_task(quiz_timeout(context.bot, db, CONFIG))
    await update.effective_message.reply_text("Quiz started. Users have 5 minutes to answer in private chat.")
    logger.info("Quiz started by admin %s", update.effective_user.id if update.effective_user else "unknown")


@admin_only
async def end_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db(context)
    state = await db.get_state()
    if not state.get("active"):
        await update.effective_message.reply_text("No quiz is currently active.")
        return
    cancel_quiz_task(context)
    await publish_results(context.bot, db, CONFIG)
    await update.effective_message.reply_text("Quiz ended and results were posted.")


@admin_only
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cancel_quiz_task(context)
    await get_db(context).reset()
    await update.effective_message.reply_text("Quiz state and answers have been reset.")


@admin_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db = get_db(context)
    state = await db.get_state()
    stats = await db.stats()
    status_text = "Active" if state.get("active") else "Inactive"
    message = (
        f"Status: {status_text}\n"
        f"Started: {state.get('started_at') or '—'}\n"
        f"Participants: {stats['participants']}\n"
        f"Correct: {stats['correct']}\n"
        f"Wrong: {stats['wrong']}"
    )
    await update.effective_message.reply_text(message)


@admin_only
async def winners(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await build_results_message(get_db(context))
    await update.effective_message.reply_text(message, parse_mode=ParseMode.HTML)


async def handle_private_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message = update.effective_message
        user = update.effective_user
        if message is None or user is None or message.text is None:
            return
        if update.effective_chat is None or update.effective_chat.type != ChatType.PRIVATE:
            return
        if message.text.startswith("/"):
            return

        db = get_db(context)
        state = await db.get_state()
        if not state.get("active") or not state.get("correct_answer"):
            await message.reply_text("There is no active quiz right now.")
            return

        answer = message.text.strip()
        correct = answer.casefold() == str(state["correct_answer"]).strip().casefold()
        saved = await db.save_answer(user.id, user.username, user.first_name, answer, correct)
        if not saved:
            logger.info("Ignored duplicate answer from user %s", user.id)
            return

        await message.reply_text("Your answer has been recorded.")
        if correct and len(await db.winners(3)) >= 3:
            cancel_quiz_task(context)
            await publish_results(context.bot, db, CONFIG)
    except Exception:
        logger.exception("Failed to handle private answer")
        if update.effective_message:
            await update.effective_message.reply_text("An error occurred while recording your answer.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram error for update %s", update, exc_info=context.error)
