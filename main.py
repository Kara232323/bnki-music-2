#!/usr/bin/env python3
"""
Voice Chat Music Bot
- Streams music directly in Telegram voice chats
- Queue management (up to 20 songs)
- No lag, optimized performance
- Auto-play next song
"""

import os
import sys
import asyncio
import logging
from collections import defaultdict
from typing import Dict, List
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
import yt_dlp

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Bot clients
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_client = Client(
    "assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
) if SESSION_STRING else None

calls = PyTgCalls(user_client if user_client else app)

# Queue management
queues: Dict[int, List[dict]] = defaultdict(list)
currently_playing: Dict[int, dict] = {}
MAX_QUEUE_SIZE = 20

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def get_audio_direct_link(query: str) -> dict:
    """Get direct audio link from YouTube"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'geo_bypass': True,
            'nocheckcertificate': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                
                # Get direct audio URL
                audio_url = None
                if 'url' in video:
                    audio_url = video['url']
                elif 'formats' in video:
                    for f in video['formats']:
                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                            audio_url = f.get('url')
                            break
                
                if audio_url:
                    return {
                        'title': video.get('title', query),
                        'duration': video.get('duration', 0),
                        'url': audio_url,
                        'thumbnail': video.get('thumbnail'),
                        'webpage_url': video.get('webpage_url')
                    }
        
        return None
    except Exception as e:
        logger.error(f"Error getting audio link: {e}")
        return None

def add_to_queue(chat_id: int, song: dict) -> int:
    """Add song to queue"""
    if len(queues[chat_id]) >= MAX_QUEUE_SIZE:
        return -1
    queues[chat_id].append(song)
    return len(queues[chat_id])

def get_queue(chat_id: int) -> List[dict]:
    """Get queue for chat"""
    return queues.get(chat_id, [])

def clear_queue(chat_id: int):
    """Clear queue"""
    queues[chat_id] = []
    currently_playing.pop(chat_id, None)

def remove_from_queue(chat_id: int, position: int) -> bool:
    """Remove song from queue"""
    try:
        if 0 <= position < len(queues[chat_id]):
            queues[chat_id].pop(position)
            return True
        return False
    except:
        return False

# ============================================================================
# VOICE CHAT FUNCTIONS
# ============================================================================

async def play_song(chat_id: int, song: dict):
    """Play song in voice chat"""
    try:
        audio_stream = AudioPiped(
            song['url'],
            audio_parameters=HighQualityAudio(),
        )
        
        await calls.play(
            chat_id,
            audio_stream,
            stream_type=StreamType().pulse_stream
        )
        
        currently_playing[chat_id] = song
        logger.info(f"Playing: {song['title']} in chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error playing song: {e}")
        raise

async def skip_current_song(chat_id: int):
    """Skip current song and play next"""
    try:
        if chat_id in queues and queues[chat_id]:
            queues[chat_id].pop(0)
            
            if queues[chat_id]:
                next_song = queues[chat_id][0]
                await play_song(chat_id, next_song)
                return next_song
            else:
                await calls.leave_call(chat_id)
                currently_playing.pop(chat_id, None)
                return None
        return None
    except Exception as e:
        logger.error(f"Error skipping song: {e}")
        return None

# ============================================================================
# BOT COMMANDS
# ============================================================================

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command"""
    welcome = (
        "🎵 **Voice Chat Music Bot**

"
        "Play music directly in voice chats!

"
        "**Commands:**
"
        "/play <song> - Play song in VC
"
        "/queue - Show queue
"
        "/skip - Skip current song
"
        "/stop - Stop playing
"
        "/clear - Clear queue
"
        "/current - Current song

"
        "**Queue limit: 20 songs**

"
        "Made with ❤️"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Help", callback_data="help")]
    ])
    
    await message.reply_text(welcome, reply_markup=keyboard)

@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    """Play song in voice chat"""
    try:
        chat_id = message.chat.id
        
        # Check if in group
        if message.chat.type == "private":
            await message.reply_text("❌ This command works only in groups!")
            return
        
        # Get song query
        if len(message.command) < 2:
            await message.reply_text("❌ Usage: `/play <song name>`")
            return
        
        query = message.text.split(None, 1)[1]
        
        # Send searching message
        status = await message.reply_text(f"🔍 Searching: **{query}**...")
        
        # Get audio link
        song_info = await get_audio_direct_link(query)
        
        if not song_info:
            await status.edit_text("❌ Could not find song! Try different keywords.")
            return
        
        # Add to queue
        song_info['requested_by'] = message.from_user.mention
        queue_position = add_to_queue(chat_id, song_info)
        
        if queue_position == -1:
            await status.edit_text(f"❌ Queue is full! (Max {MAX_QUEUE_SIZE} songs)")
            return
        
        # If first song, join VC and play
        if queue_position == 1:
            try:
                await status.edit_text("🎵 **Joining voice chat...**")
                await play_song(chat_id, song_info)
                
                await status.edit_text(
                    f"🎵 **Now Playing:**

"
                    f"**Title:** {song_info['title']}
"
                    f"**Duration:** {song_info['duration']//60}:{song_info['duration']%60:02d}
"
                    f"**Requested by:** {song_info['requested_by']}"
                )
            except Exception as e:
                logger.error(f"Play error: {e}")
                await status.edit_text(
                    "❌ Failed to join voice chat!

"
                    "Make sure:
"
                    "1. Voice chat is started in group
"
                    "2. Bot is admin with voice chat permissions"
                )
                queues[chat_id].clear()
        else:
            await status.edit_text(
                f"✅ **Added to queue:**

"
                f"**Title:** {song_info['title']}
"
                f"**Position:** #{queue_position}
"
                f"**Requested by:** {song_info['requested_by']}"
            )
    
    except Exception as e:
        logger.error(f"Play command error: {e}")
        await message.reply_text("❌ An error occurred!")

@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    """Show queue"""
    try:
        chat_id = message.chat.id
        queue = get_queue(chat_id)
        
        if not queue:
            await message.reply_text("📭 **Queue is empty!**")
            return
        
        queue_text = f"📋 **Current Queue ({len(queue)}/{MAX_QUEUE_SIZE}):**

"
        
        for i, song in enumerate(queue[:10], 1):
            status = "▶️ " if i == 1 else f"{i}. "
            queue_text += f"{status}**{song['title']}**
"
            queue_text += f"   └ By: {song['requested_by']}

"
        
        if len(queue) > 10:
            queue_text += f"
... and {len(queue) - 10} more songs"
        
        await message.reply_text(queue_text)
    
    except Exception as e:
        logger.error(f"Queue error: {e}")

@app.on_message(filters.command("skip"))
async def skip_command(client, message: Message):
    """Skip current song"""
    try:
        chat_id = message.chat.id
        
        next_song = await skip_current_song(chat_id)
        
        if next_song:
            await message.reply_text(
                f"⏭️ **Skipped!**

"
                f"🎵 **Now Playing:**
"
                f"**{next_song['title']}**"
            )
        else:
            await message.reply_text("📭 **No more songs in queue!**")
    
    except Exception as e:
        logger.error(f"Skip error: {e}")

@app.on_message(filters.command("stop"))
async def stop_command(client, message: Message):
    """Stop playing"""
    try:
        chat_id = message.chat.id
        
        await calls.leave_call(chat_id)
        clear_queue(chat_id)
        
        await message.reply_text("⏹️ **Stopped playing and left voice chat!**")
    
    except Exception as e:
        logger.error(f"Stop error: {e}")

@app.on_message(filters.command("clear"))
async def clear_command(client, message: Message):
    """Clear queue"""
    try:
        chat_id = message.chat.id
        clear_queue(chat_id)
        
        await message.reply_text("🗑️ **Queue cleared!**")
    
    except Exception as e:
        logger.error(f"Clear error: {e}")

@app.on_message(filters.command("current"))
async def current_command(client, message: Message):
    """Show current song"""
    try:
        chat_id = message.chat.id
        
        if chat_id in currently_playing:
            song = currently_playing[chat_id]
            await message.reply_text(
                f"🎵 **Currently Playing:**

"
                f"**Title:** {song['title']}
"
                f"**Duration:** {song['duration']//60}:{song['duration']%60:02d}
"
                f"**Requested by:** {song['requested_by']}"
            )
        else:
            await message.reply_text("📭 **Nothing is playing!**")
    
    except Exception as e:
        logger.error(f"Current error: {e}")

# ============================================================================
# STREAM END HANDLER
# ============================================================================

@calls.on_stream_end()
async def on_stream_end(client, update):
    """Auto-play next song when current ends"""
    try:
        chat_id = update.chat_id
        await skip_current_song(chat_id)
    except Exception as e:
        logger.error(f"Stream end error: {e}")

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("VOICE CHAT MUSIC BOT STARTING")
    logger.info("=" * 60)
    
    if not BOT_TOKEN or not API_ID or not API_HASH:
        logger.error("Missing credentials!")
        sys.exit(1)
    
    # Start clients
    await app.start()
    
    if user_client:
        await user_client.start()
    
    await calls.start()
    
    logger.info("✅ Bot started successfully!")
    logger.info("Bot is ready to stream music!")
    logger.info("=" * 60)
    
    # Keep alive
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
