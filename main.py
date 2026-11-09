
import os
import asyncio

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# OpenAI configuration
ai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

SYSTEM_PROMPT = """
You are NEXORA, a friendly and intelligent AI assistant.

You understand Hindi, Hinglish and English.
Remember the conversation context.
Give helpful, clear, natural and accurate answers.
"""

# Separate memory for each Telegram chat
chat_memory = {}

MAX_MESSAGES = 20


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "Welcome to NEXORA AI! 🤖\n\n"
        "Main tumhara AI assistant hoon.\n"
        "Mujhse kuch bhi pooch sakte ho!\n\n"
        "Commands:\n"
        "/start - Start bot\n"
        "/reset - Reset conversation"
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_memory.pop(update.effective_chat.id, None)

    await update.message.reply_text(
        "🧠 Chat memory reset ho gayi!\n"
        "Chalo nayi conversation shuru karte hain."
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    user_message = update.message.text

    history = chat_memory.setdefault(chat_id, [])

    history.append({
        "role": "user",
        "content": user_message
    })

    try:

        response = await asyncio.to_thread(
            ai.responses.create,
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=history,
        )

        answer = response.output_text or "Sorry, mujhe jawab nahi mila."

        history.append({
            "role": "assistant",
            "content": answer
        })

        # Keep latest 20 messages
        if len(history) > MAX_MESSAGES:
            del history[:-MAX_MESSAGES]

        # Split long Telegram messages
        for i in range(0, len(answer), 3500):

            await update.message.reply_text(
                answer[i:i + 3500]
            )

    except Exception as error:

        if history and history[-1] == {
            "role": "user",
            "content": user_message
        }:
            history.pop()

        print("NEXORA ERROR:", repr(error))

        await update.message.reply_text(
            "NEXORA ko abhi problem aa rahi hai. "
            "Thodi der baad try karo."
        )


def main():

    token = os.environ["TELEGRAM_BOT_TOKEN"]

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat
        )
    )

    print("NEXORA 2.0 is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
