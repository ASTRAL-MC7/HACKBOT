"""
Telegram Status Watcher Bot - Render Web Service ready
--------------------------------------------------------
Watches a webpage for a status value like "ON:8928" (a fixed keyword
followed by a number that changes) and reports it to you on Telegram.

- /start   -> refreshes the page right now and shows the current value
- /status  -> same, on demand, anytime
- Background job checks the page every CHECK_INTERVAL_SECONDS and messages
  you automatically ONLY when the value changes.

Also runs a tiny built-in HTTP server so Render's Web Service health check
has something to ping (Render requires a service to bind to $PORT).

CONFIG: all set via environment variables (set these in Render's dashboard
under your service -> Environment):
    BOT_TOKEN              (required) from @BotFather
    CHAT_ID                (required) your numeric Telegram chat id
    WATCH_URL              (required) the page to watch
    KEYWORD                (optional, default "ON") label to search for
    CHECK_INTERVAL_SECONDS (optional, default "60")
"""

import os
import re
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============== CONFIG (from environment variables) ==============

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
URL = os.environ.get("WATCH_URL", "")
KEYWORD = os.environ.get("KEYWORD", "ON")
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))
PORT = int(os.environ.get("PORT", "10000"))  # Render sets PORT automatically

# Matches KEYWORD followed by ":" and one or more digits, e.g. ON:8928
PATTERN = rf"{re.escape(KEYWORD)}:\d+"

# ===================================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATE_FILE = "last_value.txt"


def fetch_value() -> str:
    """Fetch the page and extract the status text."""
    try:
        resp = requests.get(URL, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"ERROR: could not reach page ({e})"

    match = re.search(PATTERN, resp.text)
    if match:
        return match.group(0)
    return f"NOT_FOUND: '{KEYWORD}:<number>' pattern not found on the page"


def load_last_value():
    try:
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def save_last_value(value: str):
    with open(STATE_FILE, "w") as f:
        f.write(value)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = fetch_value()
    save_last_value(value)
    await update.message.reply_text(
        f"Bot started. Watching:\n{URL}\n\nCurrent value: {value}"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = fetch_value()
    await update.message.reply_text(value)


async def check_for_changes(context: ContextTypes.DEFAULT_TYPE):
    value = fetch_value()
    last_value = load_last_value()

    if value != last_value:
        save_last_value(value)
        if last_value is not None:
            await context.bot.send_message(chat_id=CHAT_ID, text=f"Status changed: {value}")
        else:
            logger.info("Initial value recorded: %s", value)


# ---------------- tiny web server, only for Render's health check ----------------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # silence default per-request logging


def run_web_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Health-check server listening on port %s", PORT)
    server.serve_forever()


def main():
    missing = [name for name, val in
               [("BOT_TOKEN", BOT_TOKEN), ("CHAT_ID", CHAT_ID), ("WATCH_URL", URL)]
               if not val]
    if missing:
        raise SystemExit(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in Render -> your service -> Environment."
        )

    # Start the health-check server in the background so Render sees the
    # port bound quickly, then run the bot in the main thread.
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.job_queue.run_repeating(check_for_changes, interval=CHECK_INTERVAL_SECONDS, first=10)

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
