#!/usr/bin/env python3
"""
VOICE CHAT MUSIC BOT - WORKING VERSION
Plays music directly in Telegram voice chats
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Initialize clients
app = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# User client for voice chat (THIS IS CRUCIAL!)
user_client = Client(
    "assistant", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    session_string=SESSION_STRING
) if SESSION_STRING else None

# PyTgCalls instance
calls = PyTgCalls(user_client if user_client else app)

# Queue management
queues = defaultdict(list)
currently_playing = {}

async def get_direct_link(query: str):
    """Get direct audio URL from YouTube"""
    try:
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                
                # Get the best audio URL
                audio_url = None
                if 'url' in video:
                    audio_url = video['url']
                elif 'formats' in video:
                    for fmt in video['formats']:
                        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                            audio_url = fmt.get('url')
                            break
                    if not audio_url:
                        for fmt in video['formats']:
                            if fmt.get('acodec') != 'none':
                                audio_url = fmt.get('url')
                                break
                
                if audio_url:
                    return {
                        'title': video.get('title', query),
                        'duration': video.get('duration', 0),
                        'url': audio_url,
                        'thumbnail': video.get('thumbnail', ''),
                    }
        return None
    except Exception as e:
        logger.error(f"Error getting audio: {e}")
        return None

async def play_in_vc(chat_id: int, song: dict):
    """Play song in voice chat"""
    try:
        # Create audio stream
        audio_stream = AudioPiped(
            song['url'],
            audio_parameters=HighQualityAudio(),
        )
        
        # Join and play
        await calls.play(
            chat_id,
            audio_stream,
        )
        
        currently_playing[chat_id] = song
        logger.info(f"▶️ Playing: {song['title']} in chat {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error playing: {e}")
        return False

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command"""
    welcome = (
        "🎵 **Voice Chat Music Bot**\n\n"
        "I can play music directly in voice chats!\n\n"
        "**Commands:**\n"
        "• `/play <song>` - Play song in VC\n"
        "• `/queue` - Show queue\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop and leave VC\n"
        "• `/current` - Current playing\n\n"
        "**Setup required:**\n"
        "1. Add me as admin\n"
        "2. Start voice chat in group\n"
        "3. Use `/play <song name>`\n\n"
        "Ready to rock! 🎸"
    )
    await message.reply_text(welcome)

@app.on_message(filters.command("play"))
async def play_command(client, message: Message):
    """Play music in voice chat"""
    try:
        # Check if in group
        if message.chat.type == "private":
            await message.reply_text("❌ This command works only in groups with voice chat!")
            return
        
        # Check for song name
        if len(message.command) < 2:
            await message.reply_text("❌ Usage: `/play <song name>`\n\nExample: `/play Despacito`")
            return
        
        query = message.text.split(None, 1)[1]
        chat_id = message.chat.id
        
        # Show searching message
        status_msg = await message.reply_text(f"🔍 **Searching:** `{query}`\n⏳ Please wait...")
        
        # Get audio link
        song_info = await get_direct_link(query)
        
        if not song_info:
            await status_msg.edit_text("❌ **Song not found!**\n\nTry different keywords or check spelling.")
            return
        
        # Add user info
        song_info['requested_by'] = message.from_user.mention or message.from_user.first_name
        
        # Add to queue
        queues[chat_id].append(song_info)
        position = len(queues[chat_id])
        
        if position == 1:
            # First song - join VC and play
            await status_msg.edit_text("🎵 **Joining voice chat...**")
            
            success = await play_in_vc(chat_id, song_info)
            
            if success:
                mins = song_info['duration'] // 60
                secs = song_info['duration'] % 60
                duration = f"{mins}:{secs:02d}" if song_info['duration'] > 0 else "Unknown"
                
                await status_msg.edit_text(
                    f"🎵 **Now Playing:**\n\n"
                    f"**🎧 {song_info['title']}**\n"
                    f"⏱️ Duration: `{duration}`\n"
                    f"👤 Requested by: {song_info['requested_by']}\n\n"
                    f"🔊 **Playing in voice chat!**"
                )
            else:
                await status_msg.edit_text(
                    f"❌ **Failed to join voice chat!**\n\n"
                    f"**Make sure:**\n"
                    f"• Voice chat is started in group\n"
                    f"• Bot has admin permissions\n"
                    f"• Bot can manage voice chats\n\n"
                    f"**How to fix:**\n"
                    f"1. Start voice chat manually\n"
                    f"2. Make bot admin\n"
                    f"3. Try `/play` again"
                )
                queues[chat_id].clear()
        else:
            # Add to queue
            await status_msg.edit_text(
                f"✅ **Added to queue!**\n\n"
                f"**🎧 {song_info['title']}**\n"
                f"📍 Position: `#{position}`\n"
                f"👤 Requested by: {song_info['requested_by']}\n\n"
                f"⏳ Will play after current song ends."
            )
    
    except Exception as e:
        logger.error(f"Play command error: {e}")
        await message.reply_text("❌ **An error occurred!**\n\nPlease try again.")

@app.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    """Show current queue"""
    try:
        chat_id = message.chat.id
        queue = queues.get(chat_id, [])
        
        if not queue:
            await message.reply_text("📭 **Queue is empty!**\n\nUse `/play <song>` to add music.")
            return
        
        queue_text = f"📋 **Music Queue ({len(queue)} songs):**\n\n"
        
        for i, song in enumerate(queue[:10], 1):
            if i == 1:
                queue_text += f"▶️ **{song['title']}**\n   👤 {song['requested_by']}\n\n"
            else:
                queue_text += f"`{i}.` **{song['title']}**\n   👤 {song['requested_by']}\n\n"
        
        if len(queue) > 10:
            queue_text += f"➕ **...and {len(queue) - 10} more songs**"
        
        await message.reply_text(queue_text)
        
    except Exception as e:
        logger.error(f"Queue error: {e}")

@app.on_message(filters.command("skip"))
async def skip_command(client, message: Message):
    """Skip current song"""
    try:
        chat_id = message.chat.id
        
        if not queues[chat_id]:
            await message.reply_text("❌ **Nothing is playing!**")
            return
        
        # Remove current song
        skipped_song = queues[chat_id].pop(0)
        
        if queues[chat_id]:
            # Play next song
            next_song = queues[chat_id][0]
            success = await play_in_vc(chat_id, next_song)
            
            if success:
                await message.reply_text(
                    f"⏭️ **Skipped!**\n\n"
                    f"🎵 **Now Playing:**\n**{next_song['title']}**"
                )
            else:
                await message.reply_text("❌ **Error playing next song!**")
        else:
            # No more songs
            await calls.leave_call(chat_id)
            currently_playing.pop(chat_id, None)
            await message.reply_text("⏭️ **Skipped!**\n📭 **No more songs in queue.**")
    
    except Exception as e:
        logger.error(f"Skip error: {e}")

@app.on_message(filters.command("stop"))
async def stop_command(client, message: Message):
    """Stop playing and leave VC"""
    try:
        chat_id = message.chat.id
        
        await calls.leave_call(chat_id)
        queues[chat_id].clear()
        currently_playing.pop(chat_id, None)
        
        await message.reply_text("⏹️ **Stopped playing!**\n\n👋 Left voice chat.")
    
    except Exception as e:
        logger.error(f"Stop error: {e}")

@app.on_message(filters.command("current"))
async def current_command(client, message: Message):
    """Show currently playing song"""
    try:
        chat_id = message.chat.id
        
        if chat_id in currently_playing:
            song = currently_playing[chat_id]
            mins = song['duration'] // 60
            secs = song['duration'] % 60
            duration = f"{mins}:{secs:02d}" if song['duration'] > 0 else "Unknown"
            
            await message.reply_text(
                f"🎵 **Currently Playing:**\n\n"
                f"**🎧 {song['title']}**\n"
                f"⏱️ Duration: `{duration}`\n"
                f"👤 Requested by: {song['requested_by']}"
            )
        else:
            await message.reply_text("❌ **Nothing is playing!**")
    
    except Exception as e:
        logger.error(f"Current error: {e}")

@calls.on_stream_end()
async def on_stream_end(client, update):
    """Auto-play next song when current ends"""
    try:
        chat_id = update.chat_id
        
        if queues[chat_id]:
            queues[chat_id].pop(0)  # Remove finished song
            
            if queues[chat_id]:
                # Play next song
                next_song = queues[chat_id][0]
                await play_in_vc(chat_id, next_song)
                logger.info(f"Auto-playing next: {next_song['title']}")
            else:
                # No more songs
                await calls.leave_call(chat_id)
                currently_playing.pop(chat_id, None)
                logger.info(f"Playlist ended in chat {chat_id}")
    
    except Exception as e:
        logger.error(f"Stream end error: {e}")

async def main():
    """Main function"""
    print("=" * 50)
    print("🎵 VOICE CHAT MUSIC BOT")
    print("=" * 50)
    
    # Validate credentials
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN missing!")
        sys.exit(1)
    
    if not API_ID or not API_HASH:
        print("❌ API_ID or API_HASH missing!")
        sys.exit(1)
    
    if not SESSION_STRING:
        print("⚠️  SESSION_STRING missing!")
        print("Bot will try to work but voice chat may fail.")
    
    print(f"✅ BOT_TOKEN: {BOT_TOKEN[:20]}...")
    print(f"✅ API_ID: {API_ID}")
    print(f"✅ SESSION_STRING: {'Set' if SESSION_STRING else 'Not set'}")
    print("=" * 50)
    
    # Start clients
    print("🚀 Starting bot...")
    await app.start()
    
    if user_client and SESSION_STRING:
        print("🚀 Starting user client...")
        await user_client.start()
    
    print("🚀 Starting PyTgCalls...")
    await calls.start()
    
    print("=" * 50)
    print("✅ BOT IS READY!")
    print("=" * 50)
    print("📱 Add bot to group as admin")
    print("🎤 Start voice chat in group") 
    print("🎵 Use /play <song name>")
    print("=" * 50)
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped!")
    except Exception as e:
        print(f"💥 Error: {e}")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

