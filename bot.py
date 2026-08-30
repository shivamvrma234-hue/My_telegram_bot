import os
import asyncio
import yt_dlp

from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

load_dotenv()

# =========================
# CONFIG
# =========================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Session of the Telegram USER account that joins the VC
SESSION_STRING = os.getenv("SESSION_STRING", "")

if not API_ID or not API_HASH or not BOT_TOKEN or not SESSION_STRING:
    raise RuntimeError(
        "Missing API_ID, API_HASH, BOT_TOKEN or SESSION_STRING"
    )

# =========================
# TELEGRAM CLIENT
# =========================

app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# User account used for voice chat
user = Client(
    "music_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

call = PyTgCalls(user)

# =========================
# QUEUES
# =========================

queues = {}
current = {}


# =========================
# YOUTUBE
# =========================

def get_audio_url(query):
    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "default_search": "ytsearch1",
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(query, download=False)

        if "entries" in info:
            info = info["entries"][0]

        return {
            "title": info.get("title", "Unknown"),
            "url": info["url"],
        }


# =========================
# PLAY NEXT
# =========================

async def play_next(chat_id):
    if chat_id not in queues or not queues[chat_id]:
        current.pop(chat_id, None)

        try:
            await call.leave_call(chat_id)
        except Exception:
            pass

        return

    song = queues[chat_id].pop(0)
    current[chat_id] = song

    try:
        await call.play(
            chat_id,
            MediaStream(song["url"])
        )

        await app.send_message(
            chat_id,
            f"🎵 **Now Playing**\n\n"
            f"🎶 {song['title']}"
        )

    except Exception as e:
        await app.send_message(
            chat_id,
            f"❌ Could not play:\n`{e}`"
        )

        await play_next(chat_id)


# =========================
# /start
# =========================

@app.on_message(filters.command("start"))
async def start_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "Use `/play song name` to play music in the group VC.\n\n"
        "Commands:\n"
        "▶️ `/play <song>`\n"
        "⏭ `/skip`\n"
        "⏹ `/stop`\n"
        "📜 `/queue`\n"
        "❓ `/help`"
    )


# =========================
# /help
# =========================

@app.on_message(filters.command("help"))
async def help_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Music Bot Commands**\n\n"
        "▶️ `/play <song>` — Play music\n"
        "⏭ `/skip` — Skip current song\n"
        "⏹ `/stop` — Stop music and leave VC\n"
        "📜 `/queue` — Show queue\n"
        "❓ `/help` — Show this menu"
    )


# =========================
# /play
# =========================

@app.on_message(filters.command("play"))
async def play_handler(_, message: Message):

    if len(message.command) < 2:
        await message.reply_text(
            "❌ Usage:\n`/play song name`"
        )
        return

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    status = await message.reply_text(
        "🔎 Searching..."
    )

    try:
        song = await asyncio.to_thread(
            get_audio_url,
            query
        )
    except Exception as e:
        await status.edit_text(
            f"❌ Search failed:\n`{e}`"
        )
        return

    if chat_id not in queues:
        queues[chat_id] = []

    # Nothing currently playing
    if chat_id not in current:
        queues[chat_id].append(song)

        await status.edit_text(
            f"🎵 **Playing:** {song['title']}"
        )

        try:
            await play_next(chat_id)
        except Exception as e:
            await status.edit_text(
                f"❌ VC error:\n`{e}`"
            )

    else:
        queues[chat_id].append(song)

        await status.edit_text(
            f"➕ Added to queue:\n\n"
            f"🎶 {song['title']}"
        )


# =========================
# /skip
# =========================

@app.on_message(filters.command("skip"))
async def skip_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current:
        await message.reply_text(
            "❌ Nothing is playing."
        )
        return

    try:
        await call.leave_call(chat_id)
    except Exception:
        pass

    current.pop(chat_id, None)

    await message.reply_text(
        "⏭ **Skipped!**"
    )

    await asyncio.sleep(1)

    await play_next(chat_id)


# =========================
# /stop
# =========================

@app.on_message(filters.command("stop"))
async def stop_handler(_, message: Message):

    chat_id = message.chat.id

    queues.pop(chat_id, None)
    current.pop(chat_id, None)

    try:
        await call.leave_call(chat_id)
    except Exception:
        pass

    await message.reply_text(
        "⏹ **Music stopped.**"
    )


# =========================
# /queue
# =========================

@app.on_message(filters.command("queue"))
async def queue_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in queues or not queues[chat_id]:
        await message.reply_text(
            "📜 Queue is empty."
        )
        return

    text = "📜 **Music Queue**\n\n"

    for i, song in enumerate(queues[chat_id], 1):
        text += f"{i}. {song['title']}\n"

    await message.reply_text(text)


# =========================
# START
# =========================

async def main():

    await app.start()
    await user.start()

    await call.start()

    print("================================")
    print("🎵 MUSIC BOT STARTED")
    print("================================")

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
