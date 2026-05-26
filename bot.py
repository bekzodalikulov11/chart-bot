import asyncio
import json
import logging
import os
import signal
import threading
import urllib.error
import urllib.request
from io import BytesIO
from typing import NoReturn

from flask import Flask
from telegram import InputFile, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


CHART_API_URL = "https://api.chart-img.com/v2/tradingview/advanced-chart"
SYMBOL = "FX:EURUSD"
WIDTH = 800
HEIGHT = 500
BAR_COUNT = 10

INTERVALS = {
    "м5": ("5m", "M5"),
    "m5": ("5m", "M5"),
    "м15": ("15m", "M15"),
    "m15": ("15m", "M15"),
    "h1": ("1h", "H1"),
    "н1": ("1h", "H1"),
    "h4": ("4h", "H4"),
    "н4": ("4h", "H4"),
}
ALL_INTERVAL_KEYS = ("м5", "м15", "h1", "h4")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


keepalive_app = Flask(__name__)


@keepalive_app.get("/")
def index() -> str:
    return "Bot is running"


def start_keepalive_server() -> None:
    port = int(os.environ.get("PORT", "5000"))

    def _run() -> None:
        keepalive_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    thread = threading.Thread(target=_run, name="keepalive", daemon=True)
    thread.start()
    logger.info("Keepalive web server listening on port %s", port)


HELP_TEXT = (
    "Отправьте таймфрейм, чтобы получить график EURUSD за последние 10 свечей:\n\n"
    "М5 — 5 минут\n"
    "М15 — 15 минут\n"
    "H1 — 1 час\n"
    "H4 — 4 часа\n"
    "All — все 4 графика"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


def normalize_message(text: str) -> str:
    return text.strip().casefold()


def build_chart_payload(interval: str) -> bytes:
    payload = {
        "symbol": SYMBOL,
        "interval": interval,
        "width": WIDTH,
        "height": HEIGHT,
        "bar_count": BAR_COUNT,
    }
    return json.dumps(payload).encode("utf-8")


def fetch_chart_image(interval: str, api_key: str) -> bytes:
    request = urllib.request.Request(
        CHART_API_URL,
        data=build_chart_payload(interval),
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            status_code = response.status
            content_type = response.headers.get("Content-Type", "")
            image = response.read()
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace").strip()
        logger.error(
            "Chart API error for interval=%s status_code=%s message=%s",
            interval,
            error.code,
            error_body or error.reason,
        )
        raise RuntimeError(f"Chart API returned HTTP {error.code}: {error_body or error.reason}") from error
    except urllib.error.URLError as error:
        logger.error(
            "Chart API connection error for interval=%s message=%s",
            interval,
            error.reason,
        )
        raise RuntimeError("Chart API request failed") from error

    if not image:
        logger.error(
            "Chart API empty response for interval=%s status_code=%s content_type=%s",
            interval,
            status_code,
            content_type,
        )
        raise RuntimeError("Chart API returned an empty response")

    if "image" not in content_type.lower():
        response_text = image[:2000].decode("utf-8", errors="replace").strip()
        logger.error(
            "Chart API non-image response for interval=%s status_code=%s content_type=%s message=%s",
            interval,
            status_code,
            content_type,
            response_text,
        )
        raise RuntimeError(
            f"Chart API did not return an image. Status {status_code}: {response_text}"
        )

    logger.info(
        "Chart API success for interval=%s status_code=%s content_type=%s bytes=%s",
        interval,
        status_code,
        content_type,
        len(image),
    )

    return image


async def send_chart(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    interval: str,
    label: str,
) -> None:
    api_key = context.application.bot_data.get("chart_api_key")
    if not api_key:
        await update.message.reply_text("CHART_IMG_API_KEY не настроен.")
        return

    try:
        image = await asyncio.to_thread(fetch_chart_image, interval, api_key)
    except RuntimeError as error:
        logger.warning("Failed to fetch %s chart: %s", label, error)
        await update.message.reply_text(f"Не удалось получить график {label}. Попробуйте позже.")
        return

    photo = BytesIO(image)
    photo.name = f"eurusd_{label.lower()}.png"
    await update.message.reply_photo(
        photo=InputFile(photo, filename=photo.name),
        caption=f"EURUSD {label} — последние 10 свечей",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = normalize_message(update.message.text or "")

    if text == "all":
        await update.message.reply_text("Отправляю все 4 графика EURUSD...")
        for key in ALL_INTERVAL_KEYS:
            interval, label = INTERVALS[key]
            await send_chart(update, context, interval, label)
        return

    interval_config = INTERVALS.get(text)
    if interval_config:
        interval, label = interval_config
        await send_chart(update, context, interval, label)
        return

    await update.message.reply_text(HELP_TEXT)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram bot error", exc_info=context.error)


def missing_secret(name: str) -> NoReturn:
    raise RuntimeError(f"{name} is not configured. Add it to Replit Secrets.")


def main() -> None:
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        missing_secret("TELEGRAM_BOT_TOKEN")

    chart_api_key = os.environ.get("CHART_IMG_API_KEY")
    if not chart_api_key:
        missing_secret("CHART_IMG_API_KEY")

    application = Application.builder().token(telegram_token).build()
    application.bot_data["chart_api_key"] = chart_api_key

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(handle_error)

    start_keepalive_server()

    logger.info("Telegram EURUSD chart bot is starting")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        stop_signals=(signal.SIGINT, signal.SIGTERM),
    )


if __name__ == "__main__":
    main()
