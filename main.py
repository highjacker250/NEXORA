
import os
import asyncio
import logging
import threading

from openai import OpenAI
from flask import Flask, jsonify
from waitress import serve

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================================
# CONFIGURATION
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("NEXORA")

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

ai = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are NEXORA, a friendly and intelligent AI assistant.

You understand Hindi, Hinglish and English.

Remember the conversation context provided to you.
Give helpful, clear, natural and accurate answers.

Use simple explanations when possible.
Be polite and conversational.
"""

MAX_MESSAGES = 20

# ==========================================
# CONVERSATION MEMORY
# ==========================================

chat_memory = {}

# Prevent simultaneous requests from mixing
# conversation history in the same chat.
chat_locks = {}

# ==========================================
# FLASK WEB SERVER
# ==========================================

web = Flask(__name__)


@web.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "service": "NEXORA AI",
        "version": "2.0",
        "message": "NEXORA Telegram AI is running"
    })


@web.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "healthy"
    }), 200


@web.route("/status", methods=["GET"])
def status():

    return jsonify({
        "service": "NEXORA AI",
        "status": "running",
        "model": MODEL
    })


def run_web():

    port = int(os.environ.get("PORT", 10000))

    logger.info("Starting web server on port %s", port)

    serve(
        web,
        host="0.0.0.0",
        port=port,
        threads=4
    )


# ==========================================
# TELEGRAM COMMANDS
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "Welcome to NEXORA AI! 🤖\n\n"
        "Main tumhara AI assistant hoon.\n"
        "Mujhse kuch bhi pooch sakte ho!\n\n"
        "Available Commands:\n"
        "/start - Start bot\n"
        "/reset - Reset conversation\n"
        "/help - Show help"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 NEXORA AI HELP\n\n"
        "Simply mujhe message bhejo aur main reply karunga.\n\n"
        "/start - Start NEXORA\n"
        "/reset - Clear conversation memory\n"
        "/help - Help information"
    )


async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    lock = chat_locks.setdefault(
        chat_id,
        asyncio.Lock()
    )

    async with lock:

        chat_memory.pop(chat_id, None)

    await update.message.reply_text(
        "🧠 Chat memory reset ho gayi!\n\n"
        "Chalo nayi conversation shuru karte hain."
    )


# ==========================================
# AI CHAT HANDLER
# ==========================================

async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_id = update.effective_chat.id

    user_message = update.message.text

    lock = chat_locks.setdefault(
        chat_id,
        asyncio.Lock()
    )

    async with lock:

        history = chat_memory.setdefault(
            chat_id,
            []
        )

        user_item = {
            "role": "user",
            "content": user_message
        }

        history.append(user_item)

        try:

            logger.info(
                "New message received from chat %s",
                chat_id
            )

            # OpenAI API call without blocking
            # Telegram's asynchronous event loop.

            response = await asyncio.to_thread(
                ai.responses.create,
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=history,
            )

            answer = (
                response.output_text
                or "Sorry, mujhe jawab nahi mila."
            )

            history.append({
                "role": "assistant",
                "content": answer
            })

            # Keep latest 20 messages
            if len(history) > MAX_MESSAGES:

                del history[:-MAX_MESSAGES]

            logger.info(
                "AI response generated successfully"
            )

            # Telegram message length handling
            for i in range(0, len(answer), 3500):

                await update.message.reply_text(
                    answer[i:i + 3500]
                )

        except Exception:

            logger.exception(
                "NEXORA AI request failed"
            )

            # Remove failed user message
            if history and history[-1] is user_item:

                history.pop()

            await update.message.reply_text(
                "NEXORA ko abhi problem aa rahi hai.\n"
                "Thodi der baad try karo."
            )


# ==========================================
# TELEGRAM ERROR HANDLER
# ==========================================

async def telegram_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram error: %s",
        context.error,
        exc_info=context.error
    )


# ==========================================
# MAIN APPLICATION
# ==========================================

def main():

    logger.info("Starting NEXORA AI 2.0")

    # Start Flask/Waitress web server
    web_thread = threading.Thread(
        target=run_web,
        name="NEXORA-Web",
        daemon=True
    )

    web_thread.start()

    # Initialize Telegram bot
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Register commands
    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("reset", reset)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    # Register normal text messages
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat
        )
    )

    # Register error handler
    app.add_error_handler(telegram_error)

    logger.info("NEXORA Telegram bot is starting")

    # Start Telegram polling
    app.run_polling(
        drop_pending_updates=False
    )


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    main()
