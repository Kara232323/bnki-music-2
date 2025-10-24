
#!/usr/bin/env python3
import os, sys, asyncio, logging
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
import yt_dlp

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

if not all([BOT_TOKEN, API_ID, API_HASH, SESSION_STRING]):
    logger.error("Missing: BOT_TOKEN, API_ID, API_HASH, or SESSION_STRING")
    sys.exit(1)

logger.info("✅ All credentials found!")
app = Client("bankai", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
calls = PyTgCalls(user)

queues = defaultdict(list)
now_playing = {}

async def get_audio(query: str):
    try:
        opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True}
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
        logger.error(f"Audio error: {e}")
        return None

async def play_song(cid, song):
    try:
        stream = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls.play(cid, stream)
        now_playing[cid] = song
        logger.info(f"▶️ Playing: {song['title']}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_cmd(c, m: Message):
    try:
        await m.reply_text("⚔️ *BANKAI MUSIC BOT*\n\n/play <song>\n/queue\n/skip\n/stop", parse_mode="Markdown")
    except: pass

@app.on_message(filters.command("play"))
async def play_cmd(c, m: Message):
    try:
        if m.chat.type == "private":
            await m.reply_text("Use in groups!")
            return
        if len(m.command) < 2:
            await m.reply_text("Usage: /play <song>")
            return
        
        query = m.text.split(None, 1)[1]
        cid = m.chat.id
        msg = await m.reply_text(f"🔍 Searching: {query}")
        
        song = await get_audio(query)
        if not song:
            await msg.edit_text("Not found!")
            return
        
        queues[cid].append(song)
        
        if len(queues[cid]) == 1:
            await msg.edit_text("Joining VC...")
            if await play_song(cid, song):
                await msg.edit_text(f"▶️ Now: {song['title']}")
            else:
                await msg.edit_text("Failed!")
                queues[cid].clear()
        else:
            await msg.edit_text(f"✅ Added #{len(queues[cid])}: {song['title']}")
    except Exception as e:
        logger.error(f"Play error: {e}")

@app.on_message(filters.command("queue"))
async def queue_cmd(c, m: Message):
    try:
        q = queues.get(m.chat.id, [])
        if not q:
            await m.reply_text("Queue empty!")
            return
        txt = "📋 Queue:\n"
        for i, s in enumerate(q[:10], 1):
            txt += f"{i}. {s['title']}\n"
        await m.reply_text(txt)
    except: pass

@app.on_message(filters.command("skip"))
async def skip_cmd(c, m: Message):
    try:
        cid = m.chat.id
        if not queues[cid]:
            await m.reply_text("Nothing!")
            return
        queues[cid].pop(0)
        if queues[cid]:
            await play_song(cid, queues[cid][0])
            await m.reply_text(f"⏭️ {queues[cid][0]['title']}")
        else:
            await calls.leave_call(cid)
            await m.reply_text("Queue ended!")
    except Exception as e:
        logger.error(f"Skip error: {e}")

@app.on_message(filters.command("stop"))
async def stop_cmd(c, m: Message):
    try:
        await calls.leave_call(m.chat.id)
        queues[m.chat.id].clear()
        await m.reply_text("⏹️ Stopped!")
    except Exception as e:
        logger.error(f"Stop error: {e}")

async def main():
    logger.info("="*50)
    logger.info("⚔️ BANKAI BOT - RAILWAY")
    logger.info("="*50)
    
    try:
        await app.start()
        logger.info("✅ Bot started")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)
    
    try:
        await user.start()
        logger.info("✅ User client started")
    except Exception as e:
        logger.error(f"User error: {e}")
        sys.exit(1)
    
    try:
        await calls.start()
        logger.info("✅ PyTgCalls started")
    except Exception as e:
        logger.error(f"PyTgCalls error: {e}")
        sys.exit(1)
    
    logger.info("="*50)
    logger.info("✅ BOT READY!")
    logger.info("="*50)
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
