import os
import asyncio
import traceback

import aiohttp
from aiohttp import web

from pyrogram import Client, filters, idle
from pyrogram.types import Message

import yt_dlp


# =========================================================
# CONFIG
# =========================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

PORT = int(os.environ.get("PORT", "10000"))


# =========================================================
# PYROGRAM CLIENT
# =========================================================

bot = Client(
    "yurix_music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
    no_updates=False
)


# =========================================================
# MUSIC DATA
# =========================================================

queues = {}
now_playing = {}


# =========================================================
# REMOVE TELEGRAM WEBHOOK
# =========================================================

async def delete_webhook():
    print("🧹 Checking Telegram webhook...", flush=True)

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/deleteWebhook"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"drop_pending_updates": "false"}
            ) as response:

                result = await response.json()

                print(
                    f"🧹 Webhook removal result: {result}",
                    flush=True
                )

                if result.get("ok"):
                    print(
                        "✅ Telegram webhook removed.",
                        flush=True
                    )
                else:
                    print(
                        "⚠️ Telegram webhook removal failed.",
                        flush=True
                    )

    except Exception as error:
        print(
            f"❌ Webhook check error: "
            f"{type(error).__name__}: {error}",
            flush=True
        )


# =========================================================
# RAW UPDATE DIAGNOSTIC
# =========================================================

@bot.on_raw_update()
async def raw_update_debug(
    client,
    update,
    users,
    chats
):
    print(
        "========================================",
        flush=True
    )

    print(
        f"📡 RAW TELEGRAM UPDATE: "
        f"{type(update).__name__}",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )


# =========================================================
# ALL MESSAGE DIAGNOSTIC
# =========================================================

@bot.on_message(
    filters.all,
    group=-100
)
async def diagnostic_handler(
    client,
    message: Message
):
    try:
        user_id = (
            message.from_user.id
            if message.from_user
            else "Unknown"
        )

        text = message.text

        print(
            "========================================",
            flush=True
        )

        print(
            "📩 MESSAGE RECEIVED",
            flush=True
        )

        print(
            f"👤 User ID: {user_id}",
            flush=True
        )

        print(
            f"💬 Text: {text!r}",
            flush=True
        )

        print(
            f"💬 Chat ID: {message.chat.id}",
            flush=True
        )

        print(
            "========================================",
            flush=True
        )

    except Exception as error:
        print(
            f"❌ Diagnostic error: {error}",
            flush=True
        )


# =========================================================
# /START
# =========================================================

@bot.on_message(
    filters.command("start"),
    group=0
)
async def start_command(
    client,
    message: Message
):
    print(
        "▶️ /start HANDLER EXECUTED",
        flush=True
    )

    try:
        await message.reply_text(
            "🎵 **Yurix Music Bot**\n\n"
            "✅ Bot is online!\n\n"
            "🎶 Music commands:\n"
            "• `/play <song>`\n"
            "• `/queue`\n"
            "• `/skip`\n"
            "• `/stop`\n\n"
            "❓ `/help`"
        )

        print(
            "✅ /start reply sent.",
            flush=True
        )

    except Exception as error:
        print(
            f"❌ /start error: "
            f"{type(error).__name__}: {error}",
            flush=True
        )


# =========================================================
# /HELP
# =========================================================

@bot.on_message(
    filters.command("help"),
    group=0
)
async def help_command(
    client,
    message: Message
):
    print(
        "▶️ /help HANDLER EXECUTED",
        flush=True
    )

    await message.reply_text(
        "🎵 **Music Bot Help**\n\n"
        "▶️ `/play <song>` — Play/search a song\n"
        "📜 `/queue` — Show queue\n"
        "⏭ `/skip` — Skip current song\n"
        "⏹ `/stop` — Stop music\n"
        "❓ `/help` — Show help"
    )


# =========================================================
# YOUTUBE SEARCH
# =========================================================

def search_song(query):
    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            query,
            download=False
        )

        if not info:
            raise Exception(
                "No result found."
            )

        if "entries" in info:

            entries = info.get("entries") or []

            if not entries:
                raise Exception(
                    "Song not found."
                )

            info = entries[0]

        return {
            "title": info.get(
                "title",
                "Unknown"
            ),
            "url": info.get("url"),
            "webpage_url": info.get(
                "webpage_url"
            )
        }


# =========================================================
# /PLAY
# =========================================================

@bot.on_message(
    filters.command("play"),
    group=0
)
async def play_command(
    client,
    message: Message
):
    print(
        "▶️ /play HANDLER EXECUTED",
        flush=True
    )

    if len(message.command) < 2:

        await message.reply_text(
            "❌ Usage:\n"
            "`/play song name`"
        )

        return

    query = " ".join(
        message.command[1:]
    )

    status = await message.reply_text(
        "🔎 Searching for the song..."
    )

    try:

        song = await asyncio.to_thread(
            search_song,
            query
        )

    except Exception as error:

        print(
            f"❌ Search error: {error}",
            flush=True
        )

        await status.edit_text(
            "❌ Couldn't find the song."
        )

        return

    chat_id = message.chat.id

    if chat_id not in queues:
        queues[chat_id] = []

    queues[chat_id].append(song)

    position = len(
        queues[chat_id]
    )

    await status.edit_text(
        "🎵 **Song added!**\n\n"
        f"🎶 {song['title']}\n\n"
        f"📌 Queue position: `{position}`\n\n"
        "⚠️ Voice playback is not connected "
        "in this diagnostic version."
    )


# =========================================================
# /QUEUE
# =========================================================

@bot.on_message(
    filters.command("queue"),
    group=0
)
async def queue_command(
    client,
    message: Message
):
    print(
        "▶️ /queue HANDLER EXECUTED",
        flush=True
    )

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        []
    )

    if not queue:

        await message.reply_text(
            "📜 **Queue is empty.**"
        )

        return

    text = "📜 **Music Queue**\n\n"

    for index, song in enumerate(
        queue,
        1
    ):

        title = song.get(
            "title",
            "Unknown"
        )

        text += (
            f"`{index}.` {title}\n"
        )

    await message.reply_text(text)


# =========================================================
# /SKIP
# =========================================================

@bot.on_message(
    filters.command("skip"),
    group=0
)
async def skip_command(
    client,
    message: Message
):
    print(
        "▶️ /skip HANDLER EXECUTED",
        flush=True
    )

    chat_id = message.chat.id

    queue = queues.get(
        chat_id,
        []
    )

    if not queue:

        await message.reply_text(
            "❌ Queue is empty."
        )

        return

    skipped = queue.pop(0)

    await message.reply_text(
        "⏭ **Skipped!**\n\n"
        f"🎶 {skipped.get('title', 'Unknown')}"
    )


# =========================================================
# /STOP
# =========================================================

@bot.on_message(
    filters.command("stop"),
    group=0
)
async def stop_command(
    client,
    message: Message
):
    print(
        "▶️ /stop HANDLER EXECUTED",
        flush=True
    )

    chat_id = message.chat.id

    queues.pop(
        chat_id,
        None
    )

    now_playing.pop(
        chat_id,
        None
    )

    await message.reply_text(
        "⏹ **Music stopped.**\n\n"
        "🗑 Queue cleared."
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

async def health(request):

    return web.Response(
        text="🎵 Yurix Music Bot is running!"
    )


async def start_health_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    app.router.add_get(
        "/health",
        health
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    print(
        f"🌐 Health server running "
        f"on port {PORT}",
        flush=True
    )

    return runner


# =========================================================
# START TELEGRAM
# =========================================================

async def start_telegram_bot():

    print(
        "🤖 Connecting to Telegram...",
        flush=True
    )

    try:

        await bot.start()

        print(
            "✅ Telegram connection successful!",
            flush=True
        )

        me = await bot.get_me()

        print(
            "========================================",
            flush=True
        )

        print(
            f"🤖 Bot: {me.first_name}",
            flush=True
        )

        print(
            f"👤 Username: @{me.username}",
            flush=True
        )

        print(
            f"🆔 ID: {me.id}",
            flush=True
        )

        print(
            "🎵 MUSIC BOT IS READY",
            flush=True
        )

        print(
            "========================================",
            flush=True
        )

        return True

    except Exception as error:

        print(
            "========================================",
            flush=True
        )

        print(
            "❌ TELEGRAM START ERROR",
            flush=True
        )

        print(
            f"Type: {type(error).__name__}",
            flush=True
        )

        print(
            f"Error: {error}",
            flush=True
        )

        traceback.print_exc()

        print(
            "========================================",
            flush=True
        )

        return False


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "========================================",
        flush=True
    )

    print(
        "🚀 STARTING TELEGRAM MUSIC BOT",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    await start_health_server()

    print(
        "🌐 Render health server started.",
        flush=True
    )

    # Remove webhook BEFORE starting Pyrogram
    await delete_webhook()

    connected = await start_telegram_bot()

    if not connected:

        print(
            "❌ Telegram bot failed to start.",
            flush=True
        )

        await asyncio.Event().wait()

        return

    print(
        "💚 Bot is running and waiting "
        "for Telegram messages...",
        flush=True
    )

    # Keep Pyrogram's update dispatcher alive
    await idle()

    print(
        "🛑 Pyrogram stopped.",
        flush=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 Bot stopped manually.",
            flush=True
        )

    except Exception as error:

        print(
            "========================================",
            flush=True
        )

        print(
            "❌ FATAL ERROR",
            flush=True
        )

        print(
            f"Type: {type(error).__name__}",
            flush=True
        )

        print(
            f"Error: {error}",
            flush=True
        )

        traceback.print_exc()

        print(
            "========================================",
            flush=True
)
