import os
import logging
from typing import Optional, Any, Dict

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv


# Load environment from .env if present
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

if not TELEGRAM_TOKEN:
    logging.warning(
        "TELEGRAM_TOKEN is not set. Telegram webhook will not be able to send replies."
    )

TELEGRAM_API_BASE = (
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else ""
)

WELCOME_MESSAGE = (
    "Welcome to Nestr, thanks for joining the adventure! I'm a bot, proudly made by Arthus, ready to help you!"
)

app = FastAPI(title="Nestr", version="1.0.0")


# Minimal Telegram Update models (only required fields for our use case)
class TgChat(BaseModel):
    id: int


class TgMessage(BaseModel):
    message_id: int
    chat: TgChat
    text: Optional[str] = None


class TgUpdate(BaseModel):
    update_id: int
    message: Optional[TgMessage] = None


async def send_telegram_message(chat_id: int, text: str) -> None:
    if not TELEGRAM_API_BASE:
        logging.error("Cannot send message: TELEGRAM_TOKEN is not configured.")
        return

    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        if r.status_code != 200:
            logging.error(
                "Failed to send Telegram message: %s - %s", r.status_code, r.text
            )


@app.get("/healthz")
async def healthz() -> Dict[str, Any]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(update: TgUpdate) -> Dict[str, Any]:
    # Only handle message updates
    if not update.message or update.message.chat is None:
        return {"ok": True}

    chat_id = update.message.chat.id
    text = (update.message.text or "").strip()

    # Basic routing
    if text.lower().startswith("/start"):
        await send_telegram_message(chat_id, WELCOME_MESSAGE)
    elif text:
        # For now: start conversation by echoing the message
        await send_telegram_message(chat_id, text)

    # Respond 200 to Telegram immediately
    return {"ok": True}


if __name__ == "__main__":
    # Optional local run: uvicorn app.main:app --host $HOST --port $PORT
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
