#!/usr/bin/env python3
"""
Voice Chat Music Bot - FIXED VERSION
Zero syntax errors, production ready
"""

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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Initialize clients
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_client = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
) if SESSION_STRING else None

calls = PyTgCalls(user_client if user_client else app)

# Queue
queues = defaultdict(list)
currently_playing = {}

# Get audio link
async def get_audio_link(query: str):
    try:
        ydl_opts = {
            'format': 'bestaudio',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                audio_url = video.get('url')
                
                if not audio_url and 'formats' in video:
                    for f in video['formats']:
                        if f.get('acodec') != 'none':
                            audio_url = f.get('url')
                            break
                
                if audio_url:
                    return {
                        'title': video.get('title', query),
                        'duration': video.get('duration', 0),
                        'url': audio_url
                    }
        return None
    except Exception as e:
        logger.error(f"Audio error: {e}")
        return None

# Play song
async def play_song(chat_id: int, song: dict):
    try:
        audio = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls.play(chat_id, audio)
        currently_playing[chat_id] = song
        logger.info(f"Playing: {song['title']}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False

# Skip song
async def skip_song(chat_id: int):
    try:
        if queues[chat_id]:
            queues[chat_id].pop(0)
            if queues[chat_id]:
                await play_song(chat_id, queues[chat_id][0])
                return queues[chat_id][0]
            else:
                await calls.leave_call(chat_id)
                currently_playing.pop(chat_id, None)
        return None
    except Exception as e:
        logger.error(f"Skip error: {e}")
        return None

# Commands
@app.on_message(filters.command("start"))
async def start(client, message: Message):
    text = """🎵 Voice Chat Music Bot

Commands:
/play <song> - Play in VC
/queue - Show queue
/skip - Skip song
/stop - Stop playing
/current - Now playing

Setup:
1. Make bot admin
2. Start voice chat
3. Use /play <song>"""
    
    await message.reply_text(text)

@app.on_message(filters.command("play"))
async def play(client, message: Message):
    try:
        if message.chat.type == "private":
            await message.reply_text("Use in groups only!")
            return
        
        if len(message.command) < 2:
            await message.reply_text("Usage: /play <song name>")
            return
        
        query = message.text.split(None, 1)[1]
        chat_id = message.chat.id
        
        status = await message.reply_text(f"🔍 Searching: {query}")
        
        song_info = await get_audio_link(query)
        
        if not song_info:
            await status.edit_text("❌ Song not found!")
            return
        
        song_info['requested_by'] = message.from_user.mention or message.from_user.first_name
        queues[chat_id].append(song_info)
        position = len(queues[chat_id])
        
        if position == 1:
            await status.edit_text("🎵 Joining VC...")
            success = await play_song(chat_id, song_info)
            
            if success:
                mins = song_info['duration'] // 60
                secs = song_info['duration'] % 60
                dur = f"{mins}:{secs:02d}" if song_info['duration'] > 0 else "Unknown"
                
                await status.edit_text(
                    f"🎵 Now Playing:\n\n"
                    f"{song_info['title']}\n"
                    f"Duration: {dur}\n"
                    f"By: {song_info['requested_by']}"
                )
            else:
                await status.edit_text(
                    "❌ Failed to join VC!\n\n"
                    "Make sure:\n"
                    "• VC is started\n"
                    "• Bot is admin\n"
                    "• Bot has VC permissions"
                )
                queues[chat_id].clear()
        else:
            await status.edit_text(
                f"✅ Added to queue!\n\n"
                f"{song_info['title']}\n"
                f"Position: #{position}\n"
                f"By: {song_info['requested_by']}"
            )
    
    except Exception as e:
        logger.error(f"Play error: {e}")
        await message.reply_text("❌ Error occurred!")

@app.on_message(filters.command("queue"))
async def queue(client, message: Message):
    try:
        chat_id = message.chat.id
        q = queues.get(chat_id, [])
        
        if not q:
            await message.reply_text("📭 Queue is empty!")
            return
        
        text = f"📋 Queue ({len(q)} songs):\n\n"
        
        for i, song in enumerate(q[:10], 1):
            if i == 1:
                text += f"▶️ {song['title']}\n   By: {song['requested_by']}\n\n"
            else:
                text += f"{i}. {song['title']}\n   By: {song['requested_by']}\n\n"
        
        if len(q) > 10:
            text += f"...and {len(q)-10} more"
        
        await message.reply_text(text)
    
    except Exception as e:
        logger.error(f"Queue error: {e}")

@app.on_message(filters.command("skip"))
async def skip(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if not queues[chat_id]:
            await message.reply_text("❌ Nothing playing!")
            return
        
        next_song = await skip_song(chat_id)
        
        if next_song:
            await message.reply_text(f"⏭️ Skipped!\n\n🎵 Now: {next_song['title']}")
        else:
            await message.reply_text("⏭️ Skipped!\n📭 No more songs")
    
    except Exception as e:
        logger.error(f"Skip error: {e}")

@app.on_message(filters.command("stop"))
async def stop(client, message: Message):
    try:
        chat_id = message.chat.id
        await calls.leave_call(chat_id)
        queues[chat_id].clear()
        currently_playing.pop(chat_id, None)
        await message.reply_text("⏹️ Stopped!")
    
    except Exception as e:
        logger.error(f"Stop error: {e}")

@app.on_message(filters.command("current"))
async def current(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if chat_id in currently_playing:
            song = currently_playing[chat_id]
            mins = song['duration'] // 60
            secs = song['duration'] % 60
            dur = f"{mins}:{secs:02d}" if song['duration'] > 0 else "Unknown"
            
            await message.reply_text(
                f"🎵 Currently Playing:\n\n"
                f"{song['title']}\n"
                f"Duration: {dur}\n"
                f"By: {song['requested_by']}"
            )
        else:
            await message.reply_text("❌ Nothing playing!")
    
    except Exception as e:
        logger.error(f"Current error: {e}")

# Auto-play next
@calls.on_stream_end()
async def on_end(client, update):
    try:
        chat_id = update.chat_id
        
        if queues[chat_id]:
            queues[chat_id].pop(0)
            
            if queues[chat_id]:
                await play_song(chat_id, queues[chat_id][0])
                logger.info(f"Auto-play: {queues[chat_id][0]['title']}")
            else:
                await calls.leave_call(chat_id)
                currently_playing.pop(chat_id, None)
    
    except Exception as e:
        logger.error(f"End error: {e}")

# Main function - PROPERLY DEFINED AS ASYNC
async def main():
    """Main async function"""
    logger.info("=" * 50)
    logger.info("VOICE CHAT BOT STARTING")
    logger.info("=" * 50)
    
    # Check credentials
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing!")
        sys.exit(1)
    
    if not API_ID or not API_HASH:
        logger.error("API_ID or API_HASH missing!")
        sys.exit(1)
    
    if not SESSION_STRING:
        logger.warning("SESSION_STRING missing - VC may fail")
    
    logger.info(f"BOT_TOKEN: {BOT_TOKEN[:20]}...")
    logger.info(f"API_ID: {API_ID}")
    logger.info(f"SESSION_STRING: {'Set' if SESSION_STRING else 'Not set'}")
    
    # Start clients
    logger.info("Starting bot...")
    await app.start()
    
    if user_client and SESSION_STRING:
        logger.info("Starting user client...")
        await user_client.start()
    
    logger.info("Starting PyTgCalls...")
    await calls.start()
    
    logger.info("=" * 50)
    logger.info("✅ BOT IS READY!")
    logger.info("=" * 50)
    
    # Keep running forever
    await asyncio.Event().wait()

# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
if __name__ == "__main__":
    asyncio.run(main())


