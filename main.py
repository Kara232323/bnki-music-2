
#!/usr/bin/env python3
"""
Bankai Music Bot - Railway Optimized
Railway auto-detects port, no web server needed!
"""

import os
import sys
import asyncio
import logging
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import FloodWait
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
import yt_dlp

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "bankai_owner")

# Initialize clients
app = Client("bankai_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) if SESSION_STRING else None

# Queue
queues = defaultdict(list)
currently_playing = {}

# Get audio
async def get_audio(query: str):
    try:
        opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True, 'socket_timeout': 10}
        
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
                    return {
                        'title': v.get('title', query),
                        'duration': v.get('duration', 0),
                        'url': url,
                        'webpage_url': v.get('webpage_url', '')
                    }
        return None
    except Exception as e:
        logger.error(f"Audio error: {e}")
        return None

# Play
async def play_song(chat_id: int, song: dict, calls_client):
    try:
        stream = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls_client.play(chat_id, stream)
        currently_playing[chat_id] = song
        logger.info(f"Playing: {song['title']}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False

# Commands
@app.on_message(filters.command("start"))
async def start_cmd(c, m: Message):
    try:
        btns = [[InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]]
        
        welcome = (
            "⚔️ **Bankai Music Bot** ⚔️\n\n"
            "🎵 Play music in voice chats!\n\n"
            "**Setup:**\n"
            "• Add me as admin\n"
            "• Start voice chat\n"
            "• Use `/play <song>`\n\n"
            "**Commands:**\n"
            "`/play` - Play song\n"
            "`/pause` - Pause\n"
            "`/resume` - Resume\n"
            "`/stop` - Stop\n"
            "`/queue` - Show queue\n"
            "`/help` - Help"
        )
        
        await m.reply_text(welcome, reply_markup=InlineKeyboardMarkup(btns))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Start error: {e}")

@app.on_message(filters.command("play"))
async def play_cmd(c, m: Message):
    try:
        if m.chat.type == "private":
            await m.reply_text("❌ Use in groups only!")
            return
        
        if len(m.command) < 2:
            await m.reply_text("❌ **Usage:** `/play <song>`\n**Example:** `/play Despacito`")
            return
        
        query = m.text.split(None, 1)[1]
        chat_id = m.chat.id
        msg = await m.reply_text(f"🔍 Searching: `{query}`")
        
        song = await get_audio(query)
        if not song:
            await msg.edit_text("❌ Not found!")
            return
        
        song['by'] = m.from_user.mention or m.from_user.first_name
        queues[chat_id].append(song)
        pos = len(queues[chat_id])
        
        if pos == 1:
            await msg.edit_text("🎵 Joining VC...")
            calls_client = globals().get('calls_client')
            
            if not calls_client:
                await msg.edit_text("❌ Not initialized!")
                queues[chat_id].clear()
                return
            
            ok = await play_song(chat_id, song, calls_client)
            
            if ok:
                dur = f"{song['duration']//60}:{song['duration']%60:02d}" if song['duration'] > 0 else "?"
                btns = [[InlineKeyboardButton("🔗 YouTube", url=song['webpage_url'])]] if song.get('webpage_url') else []
                
                await msg.edit_text(
                    f"⚔️ **Now Playing:**\n"
                    f"🎵 {song['title']}\n"
                    f"⏱️ {dur}\n"
                    f"👤 {song['by']}",
                    reply_markup=InlineKeyboardMarkup(btns) if btns else None
                )
            else:
                await msg.edit_text("❌ Failed! Check:\n• VC started\n• Bot is admin\n• VC permissions")
                queues[chat_id].clear()
        else:
            await msg.edit_text(f"✅ Added:\n🎵 {song['title']}\n📍 Position: #{pos}\n👤 {song['by']}")
    
    except FloodWait as e:
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
        
        txt = f"📋 **Queue ({len(q)}):**\n\n"
        for i, s in enumerate(q[:10], 1):
            txt += f"{'▶️' if i==1 else f'{i}.'} {s['title']}\n"
        if len(q) > 10:
            txt += f"...+{len(q)-10} more"
        await m.reply_text(txt)
    except Exception as e:
        logger.error(f"Queue error: {e}")

@app.on_message(filters.command("pause"))
async def pause_cmd(c, m: Message):
    try:
        calls_client = globals().get('calls_client')
        await calls_client.pause_stream(m.chat.id)
        await m.reply_text("⏸️ Paused!")
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("resume"))
async def resume_cmd(c, m: Message):
    try:
        calls_client = globals().get('calls_client')
        await calls_client.resume_stream(m.chat.id)
        await m.reply_text("▶️ Resumed!")
    except Exception as e:
        await m.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("stop"))
async def stop_cmd(c, m: Message):
    try:
        calls_client = globals().get('calls_client')
        await calls_client.leave_call(m.chat.id)
        queues[m.chat.id].clear()
        currently_playing.pop(m.chat.id, None)
        await m.reply_text("⏹️ Stopped!")
    except Exception as e:
        logger.error(f"Stop error: {e}")

@app.on_message(filters.command("help"))
async def help_cmd(c, m: Message):
    help_text = (
        "⚔️ **Bankai Bot Commands**\n\n"
        "`/play <song>` - Play\n"
        "`/queue` - Show queue\n"
        "`/pause` - Pause\n"
        "`/resume` - Resume\n"
        "`/stop` - Stop\n\n"
        "**Setup:**\n"
        "1. Make bot admin\n"
        "2. Start VC\n"
        "3. Use /play!"
    )
    await m.reply_text(help_text)

# Main
async def main():
    global calls_client
    
    logger.info("="*50)
    logger.info("⚔️  BANKAI BOT STARTING (RAILWAY)")
    logger.info("="*50)
    
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("❌ Missing credentials!")
        sys.exit(1)
    
    logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:20]}...")
    logger.info(f"✅ API_ID: {API_ID}")
    logger.info("✅ Railway detected - No web server needed!")
    
    try:
        await app.start()
        logger.info("✅ Bot started")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)
    
    user_started = False
    if user and SESSION_STRING:
        try:
            await user.start()
            logger.info("✅ User client started")
            user_started = True
        except Exception as e:
            logger.warning(f"⚠️  User client: {e}")
    
    try:
        if user_started and user:
            calls_client = PyTgCalls(user)
            logger.info("Using userbot for VC")
        else:
            calls_client = PyTgCalls(app)
            logger.info("Using bot account for VC")
        
        await calls_client.start()
        logger.info("✅ PyTgCalls started")
    except Exception as e:
        logger.error(f"PyTgCalls error: {e}")
        sys.exit(1)
    
    logger.info("="*50)
    logger.info("⚔️  BANKAI BOT READY!")
    logger.info("="*50)
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal: {e}")
        sys.exit(1)
