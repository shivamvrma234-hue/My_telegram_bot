import asyncio
import os
import tempfile
import logging
from collections import defaultdict, deque

import yt_dlp
from aiohttp import web

from pyrogram import Client, filters
from pyrogram.types import Message

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
from pytgcalls.types import StreamEnded


# ============================================================
# CONFIG
# ============================================================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SESSION_STRING = os.environ["SESSION_STRING"]

PORT = int(os.environ.get("PORT", "10000"))


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

log = logging.getLogger("musicbot")


# ============================================================
# TELEGRAM CLIENTS
# ============================================================

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = Client(
    "music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

voice = PyTgCalls(assistant)


# ============================================================
# MUSIC STATE
# ============================================================

queues = defaultdict(deque)
current = {}
downloads = {}

locks = defaultdict(asyncio.Lock)


# ============================================================
# YOUTUBE DOWNLOAD
# ============================================================

async def search_song(query: str):
    """
    Search YouTube and return:
    title, webpage_url
    """

    if query.startswith("http://") or query.startswith("https://"):
        return query, query

    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "default_search": "ytsearch1",
    }

    def do_search():
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                f"ytsearch1:{query}",
                download=False,
            )

            if not info or not info.get("entries"):
                return None, None

            item = info["entries"][0]

            return (
                item.get("title", query),
                item.get("webpage_url") or item.get("url"),
            )

    return await asyncio.to_thread(do_search)


async def download_audio(url: str):
    """
    Download audio as a local file for FFmpeg/PyTgCalls.
    """

    cache_key = url

    if cache_key in downloads:
        path = downloads[cache_key]

        if os.path.exists(path):
            return path

    temp_dir = tempfile.mkdtemp(prefix="telegram_music_")

    output = os.path.join(
        temp_dir,
        "audio.%(ext)s",
    )

    options = {
        "format": "bestaudio/best",
        "outtmpl": output,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    def do_download():
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                url,
                download=True,
            )

            original = ydl.prepare_filename(info)

            base, _ = os.path.splitext(original)

            mp3 = base + ".mp3"

            if os.path.exists(mp3):
                return mp3

            return original

    path = await asyncio.to_thread(do_download)

    downloads[cache_key] = path

    return path


# ============================================================
# PLAY NEXT
# ============================================================

async def play_next(chat_id: int):

    async with locks[chat_id]:

        if not queues[chat_id]:
            current.pop(chat_id, None)
            return

        item = queues[chat_id].popleft()

        current[chat_id] = item

        title = item["title"]
        url = item["url"]

        try:
            path = await download_audio(url)

            stream = MediaStream(
                path,
                video_flags=MediaStream.Flags.IGNORE,
            )

            await voice.play(
                chat_id,
                stream,
            )

            log.info(
                "Playing %s in %s",
                title,
                chat_id,
            )

        except Exception as e:

            log.exception(
                "Playback error: %s",
                e,
            )

            current.pop(chat_id, None)

            await play_next(chat_id)


# ============================================================
# STREAM ENDED
# ============================================================

@voice.on_update()
async def voice_update(_, update):

    try:

        if isinstance(update, StreamEnded):

            chat_id = update.chat_id

            current.pop(chat_id, None)

            await play_next(chat_id)

    except Exception:

        log.exception(
            "Voice update error"
        )


# ============================================================
# /START
# ============================================================

@bot.on_message(filters.command("start"))
async def start_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Telegram Music Bot**\n\n"
        "Commands:\n"
        "/play <song>\n"
        "/pause\n"
        "/resume\n"
        "/skip\n"
        "/stop\n"
        "/queue\n"
        "/leave\n"
        "/help"
    )


# ============================================================
# /HELP
# ============================================================

@bot.on_message(filters.command("help"))
async def help_handler(_, message: Message):

    await message.reply_text(
        "🎵 **Music Commands**\n\n"
        "▶️ `/play <song>` — Play a song\n"
        "⏸ `/pause` — Pause playback\n"
        "▶️ `/resume` — Resume playback\n"
        "⏭ `/skip` — Skip current song\n"
        "⏹ `/stop` — Stop and clear queue\n"
        "📜 `/queue` — Show queue\n"
        "🚪 `/leave` — Leave voice chat"
    )


# ============================================================
# /PLAY
# ============================================================

@bot.on_message(filters.command("play"))
async def play_handler(_, message: Message):

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
        "🔎 Searching..."
    )

    try:

        title, url = await search_song(query)

        if not url:

            await status.edit_text(
                "❌ Song not found."
            )

            return

        item = {
            "title": title,
            "url": url,
        }

        chat_id = message.chat.id

        is_playing = chat_id in current

        queues[chat_id].append(item)

        if is_playing:

            position = len(
                queues[chat_id]
            )

            await status.edit_text(
                f"✅ **Added to queue**\n\n"
                f"🎵 {title}\n"
                f"📌 Position: {position}"
            )

        else:

            await status.edit_text(
                f"🎵 **Starting:** {title}"
            )

            await play_next(chat_id)

    except Exception as e:

        log.exception(
            "Play command failed"
        )

        await status.edit_text(
            f"❌ Error: `{e}`"
        )


# ============================================================
# /PAUSE
# ============================================================

@bot.on_message(filters.command("pause"))
async def pause_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:

        await voice.pause(chat_id)

        await message.reply_text(
            "⏸ Playback paused."
        )

    except Exception as e:

        await message.reply_text(
            f"❌ Couldn't pause:\n`{e}`"
        )


# ============================================================
# /RESUME
# ============================================================

@bot.on_message(filters.command("resume"))
async def resume_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:

        await voice.resume(chat_id)

        await message.reply_text(
            "▶️ Playback resumed."
        )

    except Exception as e:

        await message.reply_text(
            f"❌ Couldn't resume:\n`{e}`"
        )


# ============================================================
# /SKIP
# ============================================================

@bot.on_message(filters.command("skip"))
async def skip_handler(_, message: Message):

    chat_id = message.chat.id

    if chat_id not in current:

        await message.reply_text(
            "❌ Nothing is playing."
        )

        return

    try:

        await voice.leave_call(
            chat_id
        )

        current.pop(
            chat_id,
            None
        )

        await message.reply_text(
            "⏭ Skipped."
        )

        await asyncio.sleep(1)

        await play_next(
            chat_id
        )

    except Exception as e:

        await message.reply_text(
            f"❌ Skip failed:\n`{e}`"
        )


# ============================================================
# /STOP
# ============================================================

@bot.on_message(filters.command("stop"))
async def stop_handler(_, message: Message):

    chat_id = message.chat.id

    queues[chat_id].clear()

    current.pop(
        chat_id,
        None
    )

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:

        pass

    await message.reply_text(
        "⏹ Stopped playback and cleared the queue."
    )


# ============================================================
# /LEAVE
# ============================================================

@bot.on_message(filters.command("leave"))
async def leave_handler(_, message: Message):

    chat_id = message.chat.id

    queues[chat_id].clear()

    current.pop(
        chat_id,
        None
    )

    try:

        await voice.leave_call(
            chat_id
        )

    except Exception:

        pass

    await message.reply_text(
        "🚪 Left the voice chat."
    )


# ============================================================
# /QUEUE
# ============================================================

@bot.on_message(filters.command("queue"))
async def queue_handler(_, message: Message):

    chat_id = message.chat.id

    lines = []

    if chat_id in current:

        lines.append(
            f"▶️ **Now playing:**\n"
            f"{current[chat_id]['title']}"
        )

    if queues[chat_id]:

        lines.append(
            "\n📜 **Up next:**"
        )

        for index, item in enumerate(
            queues[chat_id],
            start=1
        ):

            lines.append(
                f"{index}. {item['title']}"
            )

    if not lines:

        await message.reply_text(
            "📭 Queue is empty."
        )

        return

    await message.reply_text(
        "\n".join(lines)
    )


# ============================================================
# HEALTH SERVER FOR RENDER
# ============================================================

async def health(request):

    return web.Response(
        text="Telegram Music Bot is running."
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

    log.info(
        "Health server listening on port %s",
        PORT
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    log.info(
        "Starting Telegram Music Bot..."
    )

    await assistant.start()

    log.info(
        "Assistant account started."
    )

    voice.start()

    log.info(
        "Voice engine started."
    )

    await bot.start()

    log.info(
        "Bot account started."
    )

    await start_health_server()

    log.info(
        "🎵 TELEGRAM MUSIC BOT IS READY"
    )

    await asyncio.Event().wait()


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        log.info(
            "Bot stopped."
    )
