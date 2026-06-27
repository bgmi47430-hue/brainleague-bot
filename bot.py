"""Entrypoint for the Telegram Quiz Bot."""

from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import CONFIG
from database import Database
from handlers import end_quiz, error_handler, handle_private_answer, help_command, reset, start_quiz, status, winners


logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    db = Database(CONFIG.database_path)
    await db.initialize()
    application.bot_data["db"] = db
    logger.info("Bot initialized")


async def post_shutdown(application: Application) -> None:
    task = application.bot_data.get("quiz_task")
    if task and not task.done():
        task.cancel()
    logger.info("Bot shutdown complete")


def build_application() -> Application:
    application = Application.builder().token(CONFIG.bot_token).post_init(post_init).post_shutdown(post_shutdown).build()
    application.add_handler(CommandHandler("startquiz", start_quiz))
    application.add_handler(CommandHandler("endquiz", end_quiz))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("winners", winners))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_answer))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    logger.info("Starting Telegram Quiz Bot")
    build_application().run_polling(allowed_updates=["message", "channel_post"])


if __name__ == "__main__":
    main()
