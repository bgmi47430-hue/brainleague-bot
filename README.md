# Telegram Quiz Bot

A production-ready Telegram quiz bot built with Python 3.12 and `python-telegram-bot` v21. The bot is designed for Render worker deployment and uses SQLite for automatic local persistence.

## Features

- Admin posts quiz questions manually in a Telegram channel.
- Admin starts a quiz with `/startquiz <correct_answer>`.
- Users answer only in private chat with the bot, including via Telegram Channel Direct Messages.
- Duplicate answers from the same user are ignored.
- Matching ignores case and leading/trailing spaces, while requiring an exact answer otherwise.
- Stores every first answer in SQLite with user ID, username, first name, answer, correctness, and timestamp.
- Tracks the first three correct users as 🥇, 🥈, and 🥉 winners.
- Automatically posts results after 5 minutes or once three winners are found.
- Admin-only commands: `/startquiz`, `/endquiz`, `/reset`, `/status`, `/winners`, and `/help`.
- Async code, modular architecture, structured logging, exception handling, and automatic database creation.

## Files

```text
bot.py          # Application entrypoint and Telegram handler registration
database.py     # Async SQLite persistence wrapper
config.py       # Environment variable loading and validation
handlers.py     # Command and private-answer handlers
scheduler.py    # Quiz timeout and result publishing helpers
requirements.txt
Procfile
runtime.txt
README.md
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Bot token from BotFather. |
| `CHANNEL_ID` | Yes | Numeric Telegram channel ID, such as `-1001234567890`, or a public channel username like `@mychannel`. |
| `ADMIN_ID` | Yes | Numeric Telegram user ID of the administrator allowed to run admin commands. |
| `DATABASE_PATH` | No | SQLite database path. Defaults to `quiz.db`. |

## Telegram Setup

1. Create a bot with [BotFather](https://t.me/BotFather) and copy its token.
2. Add the bot to your Telegram channel as an administrator so it can post quiz results.
3. Enable or use the channel direct message/private bot flow for users to send answers privately to the bot.
4. Get your channel ID and admin user ID.
5. Set the environment variables listed above.

## Running Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="123456:ABC"
export CHANNEL_ID="-1001234567890"
export ADMIN_ID="123456789"
python bot.py
```

## Render Deployment

1. Push this repository to GitHub.
2. In Render, create a new **Worker** service from the GitHub repository.
3. Render will use:
   - `runtime.txt` for Python 3.12.
   - `requirements.txt` for dependencies.
   - `Procfile` with `worker: python bot.py` to start the bot.
4. Add these environment variables in the Render dashboard:
   - `BOT_TOKEN`
   - `CHANNEL_ID`
   - `ADMIN_ID`
5. Deploy the worker.

SQLite data is stored on the service filesystem. For persistent data across redeploys, attach a Render persistent disk and set `DATABASE_PATH` to a path on that disk, for example `/var/data/quiz.db`.

## Usage

1. Admin manually posts the question in the Telegram channel.
2. Admin sends the bot:

```text
/startquiz Paris
```

3. Users send answers in private chat with the bot.
4. The bot posts results to `CHANNEL_ID` after 5 minutes or after three correct answers.

## Commands

- `/startquiz <correct_answer>`: Starts a new quiz and clears previous answers.
- `/endquiz`: Ends the active quiz and posts results immediately.
- `/reset`: Clears quiz state and answers without posting results.
- `/status`: Shows quiz status and answer counts.
- `/winners`: Shows the current result table privately to the admin.
- `/help`: Shows help text.

## Result Format

```text
🏆 Today's Quiz Results

🥇 Name
🥈 Name
🥉 Name

Participants: 10
Correct: 3
Wrong: 7
```
