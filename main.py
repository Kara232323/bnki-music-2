#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from collections import defaultdict
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
import yt_dlp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")
PORT = int(os.getenv("PORT", 8080))

app = Client("musicbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) if SESSION_STRING else None

queues = defaultdict(list)
playing = {}
calls_client = None


async def health(request):
    return web.Response(text="Voice Chat Bot Running!", status=200)


async def get_link(query: str):
    try:
        opts = {'format': 'bestaudio', 'quiet': True, 'no_warnings': True, 'socket_timeout': 10}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if info and 'entries' in info and info['entries']:
                v = info['entries'][0]
                url = v.get('url')
                if not url and 'formats' in v:
                    for f in v['formats']:
                        if f.get('acodec') != 'none':
                            url = f.get('url')
                            break
                if url:
                    return {'title': v.get('title', query), 'duration': v.get('duration', 0), 'url': url}
        return None
    except Exception as e:
        logger.error(f"Link error: {e}")
        return None


async def play(cid: int, song: dict):
    global calls_client
    try:
        stream = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls_client.play(cid, stream)
        playing[cid] = song
        logger.info(f"Playing: {song['title']}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False


@app.on_message(filters.command("start"))
async def start_cmd(c, m: Message):
    try:
        await m.reply_text("🎵 Voice Chat Music Bot\n\nCommands:\n/play <song>\n/queue\n/skip\n/stop")
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Start error: {e}")


@app.on_message(filters.command("play"))
async def play_cmd(c, m: Message):
    try:
        if m.chat.type == "private":
            await m.reply_text("Use in groups only!")
            return
        
        if len(m.command) < 2:
            await m.reply_text("Usage: /play <song>")
            return
        
        query = m.text.split(None, 1)[1]
        cid = m.chat.id
        msg = await m.reply_text(f"🔍 Searching: {query}")
        
        song = await get_link(query)
        if not song:
            await msg.edit_text("❌ Song not found!")
            return
        
        song['by'] = m.from_user.mention or m.from_user.first_name
        queues[cid].append(song)
        pos = len(queues[cid])
        
        if pos == 1:
            await msg.edit_text("🎵 Joining VC...")
            ok = await play(cid, song)
            if ok:
                dur = f"{song['duration']//60}:{song['duration']%60:02d}" if song['duration'] > 0 else "?"
                await msg.edit_text(f"🎵 Now Playing:\n{song['title']}\nDuration: {dur}\nBy: {song['by']}")
            else:
                await msg.edit_text("❌ Failed to join VC!\n\nStart VC and make bot admin")
                queues[cid].clear()
        else:
            await msg.edit_text(f"✅ Added:\n{song['title']}\nPosition: #{pos}")
    
    except FloodWait as e:
        logger.warning(f"FloodWait: {e.value}s")
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Play error: {e}")


@app.on_message(filters.command("queue"))
async def queue_cmd(c, m: Message):
    try:
        q = queues.get(m.chat.id, [])
        if not q:
            await m.reply_text("📭 Queue empty!")
            return
        txt = f"📋 Queue ({len(q)}):\n\n"
        for i, s in enumerate(q[:10], 1):
            txt += f"{'▶️' if i==1 else str(i)+'.'} {s['title']}\n"
        await m.reply_text(txt)
    except Exception as e:
        logger.error(f"Queue error: {e}")


@app.on_message(filters.command("skip"))
async def skip_cmd(c, m: Message):
    global calls_client
    try:
        cid = m.chat.id
        if not queues[cid]:
            await m.reply_text("❌ Nothing playing!")
            return
        queues[cid].pop(0)
        if queues[cid]:
            await play(cid, queues[cid][0])
            await m.reply_text(f"⏭️ Now: {queues[cid][0]['title']}")
        else:
            await calls_client.leave_call(cid)
            playing.pop(cid, None)
            await m.reply_text("⏭️ Queue ended")
    except Exception as e:
        logger.error(f"Skip error: {e}")


@app.on_message(filters.command("stop"))
async def stop_cmd(c, m: Message):
    global calls_client
    try:
        await calls_client.leave_call(m.chat.id)
        queues[m.chat.id].clear()
        playing.pop(m.chat.id, None)
        await m.reply_text("⏹️ Stopped!")
    except Exception as e:
        logger.error(f"Stop error: {e}")


async def on_stream_end_handler(client, update):
    try:
        cid = update.chat_id
        if queues[cid]:
            queues[cid].pop(0)
            if queues[cid]:
                await play(cid, queues[cid][0])
            else:
                await calls_client.leave_call(cid)
                playing.pop(cid, None)
    except Exception as e:
        logger.error(f"End error: {e}")


async def start_web():
    try:
        app_web = web.Application()
        app_web.router.add_get('/', health)
        app_web.router.add_get('/health', health)
        runner = web.AppRunner(app_web)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        logger.info(f"Web server on port {PORT}")
        return runner
    except Exception as e:
        logger.error(f"Web error: {e}")
        return None


async def main():
    global calls_client
    
    logger.info("Starting Voice Chat Bot...")
    
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("Missing credentials!")
        sys.exit(1)
    
    if not SESSION_STRING:
        logger.warning("⚠️ SESSION_STRING not configured!")
        logger.warning("⚠️ Bot will use its own account for voice chat.")
        logger.warning("⚠️ This may not work in all groups.")
    
    web_runner = await start_web()
    if not web_runner:
        sys.exit(1)
    
    await asyncio.sleep(1)
    
    try:
        await app.start()
        logger.info("Bot started")
    except Exception as e:
        logger.error(f"Bot start error: {e}")
        sys.exit(1)
    
    user_started = False
    if user and SESSION_STRING:
        try:
            await user.start()
            logger.info("User client started")
            user_started = True
        except Exception as e:
            logger.warning(f"User client error: {e}")
            logger.warning("Continuing without userbot - bot will use its own account")
    
    if user_started and user:
        calls_client = PyTgCalls(user)
        logger.info("Using userbot for voice chat")
    else:
        calls_client = PyTgCalls(app)
        logger.info("Using bot account for voice chat")
    
    calls_client.on_stream_end()(on_stream_end_handler)
    
    try:
        await calls_client.start()
        logger.info("PyTgCalls started")
    except Exception as e:
        logger.error(f"PyTgCalls error: {e}")
        sys.exit(1)
    
    logger.info("✅ Bot ready!")
    
    try:
        await asyncio.Event().wait()
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped")
    except Exception as e:
        logger.error(f"Fatal: {e}")
