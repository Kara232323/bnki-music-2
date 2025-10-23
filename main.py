#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
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
SESSION_STRING = os.getenv("SESSION_STRING", "")

app = Client("musicbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) if SESSION_STRING else None
calls = PyTgCalls(user if user else app)

queues = defaultdict(list)
playing = {}

async def get_link(query: str):
    try:
        opts = {'format': 'bestaudio', 'quiet': True, 'no_warnings': True}
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
    try:
        stream = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls.play(cid, stream)
        playing[cid] = song
        logger.info(f"Playing: {song['title']}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_cmd(c, m: Message):
    await m.reply_text("Voice Chat Music Bot\n\nCommands:\n/play <song>\n/queue\n/skip\n/stop\n\nSetup:\n1. Make bot admin\n2. Start voice chat\n3. Use /play")

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
        msg = await m.reply_text(f"Searching: {query}")
        
        song = await get_link(query)
        if not song:
            await msg.edit_text("Song not found!")
            return
        
        song['by'] = m.from_user.mention or m.from_user.first_name
        queues[cid].append(song)
        pos = len(queues[cid])
        
        if pos == 1:
            await msg.edit_text("Joining VC...")
            ok = await play(cid, song)
            if ok:
                dur = f"{song['duration']//60}:{song['duration']%60:02d}" if song['duration'] > 0 else "?"
                await msg.edit_text(f"Now Playing:\n{song['title']}\nDuration: {dur}\nBy: {song['by']}")
            else:
                await msg.edit_text("Failed to join VC!\n\nMake sure:\n- VC is started\n- Bot is admin\n- Bot has VC permissions")
                queues[cid].clear()
        else:
            await msg.edit_text(f"Added to queue!\n{song['title']}\nPosition: #{pos}\nBy: {song['by']}")
    except Exception as e:
        logger.error(f"Play cmd error: {e}")
        await m.reply_text("Error!")

@app.on_message(filters.command("queue"))
async def queue_cmd(c, m: Message):
    try:
        q = queues.get(m.chat.id, [])
        if not q:
            await m.reply_text("Queue is empty!")
            return
        txt = f"Queue ({len(q)} songs):\n\n"
        for i, s in enumerate(q[:10], 1):
            txt += f"{'▶️' if i==1 else str(i)+'.'} {s['title']}\n"
        if len(q) > 10:
            txt += f"...{len(q)-10} more"
        await m.reply_text(txt)
    except Exception as e:
        logger.error(f"Queue error: {e}")

@app.on_message(filters.command("skip"))
async def skip_cmd(c, m: Message):
    try:
        cid = m.chat.id
        if not queues[cid]:
            await m.reply_text("Nothing playing!")
            return
        queues[cid].pop(0)
        if queues[cid]:
            await play(cid, queues[cid][0])
            await m.reply_text(f"Skipped!\n\nNow: {queues[cid][0]['title']}")
        else:
            await calls.leave_call(cid)
            playing.pop(cid, None)
            await m.reply_text("Skipped! No more songs")
    except Exception as e:
        logger.error(f"Skip error: {e}")

@app.on_message(filters.command("stop"))
async def stop_cmd(c, m: Message):
    try:
        await calls.leave_call(m.chat.id)
        queues[m.chat.id].clear()
        playing.pop(m.chat.id, None)
        await m.reply_text("Stopped!")
    except Exception as e:
        logger.error(f"Stop error: {e}")

@calls.on_stream_end()
async def on_end(c, u):
    try:
        cid = u.chat_id
        if queues[cid]:
            queues[cid].pop(0)
            if queues[cid]:
                await play(cid, queues[cid][0])
            else:
                await calls.leave_call(cid)
                playing.pop(cid, None)
    except Exception as e:
        logger.error(f"End error: {e}")

async def main():
    logger.info("Starting Voice Chat Bot...")
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("Missing credentials!")
        sys.exit(1)
    if not SESSION_STRING:
        logger.warning("SESSION_STRING missing - may not work!")
    
    await app.start()
    if user and SESSION_STRING:
        await user.start()
    await calls.start()
    
    logger.info("Bot ready!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())


