#!/usr/bin/env python3
import os
import sys
import asyncio
import logging
from collections import defaultdict
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import ChatAdminRequired, UserAlreadyParticipant
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError
import yt_dlp
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")
if not BOT_TOKEN or not API_ID or not API_HASH:
    logger.error("Missing required environment variables: BOT_TOKEN, API_ID, or API_HASH")
    sys.exit(1)
app = Client("musicbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user = Client("assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING) if SESSION_STRING else None
calls = PyTgCalls(user if user else app)
queues = defaultdict(list)
playing = {}
paused = set()
async def get_link(query: str):
    """Extract audio stream URL from YouTube search or direct link."""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'geo_bypass': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if query.startswith(('http://', 'https://')):
                info = ydl.extract_info(query, download=False)
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                if info and 'entries' in info and info['entries']:
                    info = info['entries'][0]
            
            if not info:
                return None
            
            url = info.get('url')
            if not url and 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        url = fmt['url']
                        break
            
            if url:
                return {
                    'title': info.get('title', query),
                    'duration': info.get('duration', 0),
                    'url': url,
                    'thumbnail': info.get('thumbnail', ''),
                }
        
        return None
    except Exception as e:
        logger.error(f"Error extracting link: {e}")
        return None
async def play_song(chat_id: int, song: dict):
    """Start playing a song in the voice chat."""
    stream = None
    try:
        stream = AudioPiped(song['url'], audio_parameters=HighQualityAudio())
        await calls.play(chat_id, stream)
        playing[chat_id] = song
        if chat_id in paused:
            paused.remove(chat_id)
        logger.info(f"Now playing in {chat_id}: {song['title']}")
        return True
    except NoActiveGroupCall:
        logger.error(f"No active voice chat in {chat_id}")
        return False
    except AlreadyJoinedError:
        logger.info(f"Already in voice chat {chat_id}, changing stream")
        if stream:
            await calls.change_stream(chat_id, stream)
            playing[chat_id] = song
        return True
    except Exception as e:
        logger.error(f"Error playing song: {e}")
        return False
def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    if seconds <= 0:
        return "Unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
@app.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    """Start command with bot introduction."""
    welcome_text = """
🎵 **Welcome to Voice Chat Music Bot!**
**Available Commands:**
/play <song name or URL> - Play a song
/pause - Pause the current song
/resume - Resume playback
/skip - Skip to next song
/stop - Stop playback and clear queue
/queue - Show current queue
/nowplaying - Show current song info
**Setup Instructions:**
1. Add me to your group
2. Make me an admin with voice chat permissions
3. Start a voice chat in your group
4. Use /play to start playing music!
**Supported:**
✅ YouTube search
✅ Direct YouTube links
✅ Queue management
✅ Multi-chat support
"""
    await message.reply_text(welcome_text)
@app.on_message(filters.command("play"))
async def play_cmd(client, message: Message):
    """Play command to add songs to queue and start playback."""
    try:
        if message.chat.type == "private":
            await message.reply_text("❌ This command works only in groups!")
            return
        
        if len(message.command) < 2:
            await message.reply_text("❌ Usage: `/play <song name or URL>`")
            return
        
        query = message.text.split(None, 1)[1]
        chat_id = message.chat.id
        
        status_msg = await message.reply_text(f"🔍 Searching: `{query}`...")
        
        song = await get_link(query)
        if not song:
            await status_msg.edit_text("❌ Song not found! Try a different search term.")
            return
        
        song['requested_by'] = message.from_user.mention if message.from_user.mention else message.from_user.first_name
        queues[chat_id].append(song)
        position = len(queues[chat_id])
        
        if position == 1:
            await status_msg.edit_text("🎧 Joining voice chat...")
            success = await play_song(chat_id, song)
            
            if success:
                duration = format_duration(song['duration'])
                await status_msg.edit_text(
                    f"▶️ **Now Playing:**\n"
                    f"🎵 {song['title']}\n"
                    f"⏱ Duration: {duration}\n"
                    f"👤 Requested by: {song['requested_by']}"
                )
            else:
                await status_msg.edit_text(
                    "❌ **Failed to join voice chat!**\n\n"
                    "**Please ensure:**\n"
                    "• Voice chat is started in the group\n"
                    "• Bot is an admin with voice chat permissions\n"
                    "• SESSION_STRING is configured (for userbot mode)"
                )
                queues[chat_id].clear()
        else:
            duration = format_duration(song['duration'])
            await status_msg.edit_text(
                f"✅ **Added to queue!**\n"
                f"🎵 {song['title']}\n"
                f"⏱ Duration: {duration}\n"
                f"📍 Position: #{position}\n"
                f"👤 Requested by: {song['requested_by']}"
            )
    except Exception as e:
        logger.error(f"Error in play command: {e}", exc_info=True)
        await message.reply_text(f"❌ An error occurred: {str(e)}")
@app.on_message(filters.command("pause"))
async def pause_cmd(client, message: Message):
    """Pause the current playback."""
    try:
        chat_id = message.chat.id
        if chat_id not in playing:
            await message.reply_text("❌ Nothing is playing right now!")
            return
        
        if chat_id in paused:
            await message.reply_text("⏸ Already paused!")
            return
        
        await calls.pause_stream(chat_id)
        paused.add(chat_id)
        await message.reply_text("⏸ **Paused!**")
    except Exception as e:
        logger.error(f"Error in pause command: {e}")
        await message.reply_text("❌ Failed to pause!")
@app.on_message(filters.command("resume"))
async def resume_cmd(client, message: Message):
    """Resume the paused playback."""
    try:
        chat_id = message.chat.id
        if chat_id not in playing:
            await message.reply_text("❌ Nothing is playing right now!")
            return
        
        if chat_id not in paused:
            await message.reply_text("▶️ Already playing!")
            return
        
        await calls.resume_stream(chat_id)
        paused.remove(chat_id)
        await message.reply_text("▶️ **Resumed!**")
    except Exception as e:
        logger.error(f"Error in resume command: {e}")
        await message.reply_text("❌ Failed to resume!")
@app.on_message(filters.command("skip"))
async def skip_cmd(client, message: Message):
    """Skip to the next song in queue."""
    try:
        chat_id = message.chat.id
        if not queues[chat_id]:
            await message.reply_text("❌ Nothing is playing!")
            return
        
        current_song = queues[chat_id][0]['title']
        queues[chat_id].pop(0)
        
        if queues[chat_id]:
            await play_song(chat_id, queues[chat_id][0])
            await message.reply_text(
                f"⏭ **Skipped!**\n\n"
                f"▶️ Now playing: {queues[chat_id][0]['title']}"
            )
        else:
            await calls.leave_call(chat_id)
            playing.pop(chat_id, None)
            paused.discard(chat_id)
            await message.reply_text("⏭ **Skipped!** No more songs in queue.")
    except Exception as e:
        logger.error(f"Error in skip command: {e}")
        await message.reply_text("❌ Failed to skip!")
@app.on_message(filters.command("stop"))
async def stop_cmd(client, message: Message):
    """Stop playback and clear the queue."""
    try:
        chat_id = message.chat.id
        await calls.leave_call(chat_id)
        queues[chat_id].clear()
        playing.pop(chat_id, None)
        paused.discard(chat_id)
        await message.reply_text("⏹ **Stopped!** Queue cleared.")
    except Exception as e:
        logger.error(f"Error in stop command: {e}")
        await message.reply_text("❌ Failed to stop!")
@app.on_message(filters.command("queue"))
async def queue_cmd(client, message: Message):
    """Display the current queue."""
    try:
        queue = queues.get(message.chat.id, [])
        if not queue:
            await message.reply_text("📭 Queue is empty!")
            return
        
        queue_text = f"📋 **Current Queue ({len(queue)} songs):**\n\n"
        
        for idx, song in enumerate(queue[:10], 1):
            duration = format_duration(song['duration'])
            status = "▶️" if idx == 1 else f"{idx}."
            queue_text += f"{status} {song['title']} ({duration})\n"
        
        if len(queue) > 10:
            queue_text += f"\n... and {len(queue) - 10} more songs"
        
        await message.reply_text(queue_text)
    except Exception as e:
        logger.error(f"Error in queue command: {e}")
        await message.reply_text("❌ Failed to fetch queue!")
@app.on_message(filters.command("nowplaying"))
async def nowplaying_cmd(client, message: Message):
    """Show currently playing song information."""
    try:
        chat_id = message.chat.id
        if chat_id not in playing:
            await message.reply_text("❌ Nothing is playing right now!")
            return
        
        song = playing[chat_id]
        duration = format_duration(song['duration'])
        status = "⏸ Paused" if chat_id in paused else "▶️ Playing"
        
        await message.reply_text(
            f"{status}\n\n"
            f"🎵 **{song['title']}**\n"
            f"⏱ Duration: {duration}\n"
            f"👤 Requested by: {song['requested_by']}"
        )
    except Exception as e:
        logger.error(f"Error in nowplaying command: {e}")
        await message.reply_text("❌ Failed to fetch current song info!")
@calls.on_stream_end()
async def on_stream_end(client, update):
    """Handle when a song finishes playing."""
    try:
        chat_id = update.chat_id
        logger.info(f"Stream ended in chat {chat_id}")
        
        if queues[chat_id]:
            queues[chat_id].pop(0)
            
            if queues[chat_id]:
                await play_song(chat_id, queues[chat_id][0])
                logger.info(f"Auto-playing next song: {queues[chat_id][0]['title']}")
            else:
                await calls.leave_call(chat_id)
                playing.pop(chat_id, None)
                paused.discard(chat_id)
                logger.info(f"Queue finished in chat {chat_id}")
    except Exception as e:
        logger.error(f"Error in stream end handler: {e}")
async def main():
    """Main function to start the bot."""
    logger.info("🤖 Starting Voice Chat Music Bot...")
    
    if not SESSION_STRING:
        logger.warning("⚠️ SESSION_STRING not configured! Bot will use its own account for voice chat.")
        logger.warning("⚠️ This may not work in all groups. Consider using a userbot session.")
    
    app_started = False
    user_started = False
    calls_started = False
    
    try:
        await app.start()
        app_started = True
        logger.info("✅ Bot client started")
        
        if user and SESSION_STRING:
            await user.start()
            user_started = True
            logger.info("✅ Userbot client started")
        
        await calls.start()
        calls_started = True
        logger.info("✅ PyTgCalls started")
        
        me = await app.get_me()
        logger.info(f"🎵 Bot running as @{me.username}")
        logger.info("🚀 Bot is ready! Send /start to begin.")
        
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}", exc_info=True)
    finally:
        try:
            if calls_started:
                await calls.stop()
                logger.info("PyTgCalls stopped")
        except Exception as e:
            logger.error(f"Error stopping PyTgCalls: {e}")
        
        try:
            if user_started and user:
                await user.stop()
                logger.info("Userbot client stopped")
        except Exception as e:
            logger.error(f"Error stopping userbot: {e}")
        
        try:
            if app_started:
                await app.stop()
                logger.info("Bot client stopped")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")
        
        logger.info("Shutdown complete")
if __name__ == "__main__":
    asyncio.run(main())
