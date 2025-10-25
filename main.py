
import os
import sys
import asyncio
import logging
from collections import defaultdict
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
import yt_dlp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= CONFIGURATION =============
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING", "")
PORT = int(os.getenv("PORT", 8080))

# Validate environment variables
if not all([BOT_TOKEN, API_ID, API_HASH]):
    logger.error("❌ Missing BOT_TOKEN, API_ID, or API_HASH!")
    sys.exit(1)

if not SESSION_STRING or len(SESSION_STRING) < 200:
    logger.error("❌ SESSION_STRING is missing or invalid!")
    logger.error("Generate it using generate_session.py script")
    sys.exit(1)

logger.info("✅ All credentials loaded successfully")

# ============= INITIALIZE CLIENTS =============
try:
    # Bot client
    app = Client(
        "musicbot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )
    
    # User client (for voice chat access)
    user = Client(
        "assistant",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )
    
    logger.info("✅ Pyrogram clients initialized")
    
except Exception as e:
    logger.error(f"❌ Failed to initialize clients: {e}")
    sys.exit(1)

# ============= IMPORT PYTGCALLS =============
try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types import MediaStream, AudioQuality
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        AlreadyJoinedError,
        GroupCallNotFound
    )
    
    # Initialize PyTgCalls with user client
    calls = PyTgCalls(user)
    logger.info("✅ PyTgCalls initialized successfully")
    
except ImportError as e:
    logger.error(f"❌ py-tgcalls import failed: {e}")
    logger.error("Install with: pip install py-tgcalls==2.0.0")
    sys.exit(1)

# ============= DATA STRUCTURES =============
queues = defaultdict(list)  # Chat-wise song queues
playing = {}  # Currently playing songs

# ============= HELPER FUNCTIONS =============

async def get_youtube_url(query: str):
    """Search YouTube and extract audio stream URL"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search on YouTube
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                
                # Find best audio format
                audio_url = None
                for fmt in video.get('formats', []):
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        audio_url = fmt['url']
                        break
                
                # Fallback to video URL
                if not audio_url:
                    audio_url = video.get('url')
                
                return {
                    'url': audio_url,
                    'title': video.get('title', query),
                    'duration': video.get('duration', 0),
                    'thumbnail': video.get('thumbnail', '')
                }
        
        return None
        
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return None

async def start_playback(chat_id: int, track: dict):
    """Start playing audio in voice chat"""
    try:
        # Create media stream
        stream = MediaStream(
            track['url'],
            audio_parameters=AudioQuality.HIGH
        )
        
        # Start playing
        await calls.play(chat_id, stream)
        playing[chat_id] = track
        logger.info(f"▶️ Now playing in {chat_id}: {track['title']}")
        return True
        
    except AlreadyJoinedError:
        # Already in call, change stream
        logger.info(f"Already in call {chat_id}, changing stream...")
        await calls.change_stream(chat_id, stream)
        playing[chat_id] = track
        return True
        
    except NoActiveGroupCall:
        logger.error(f"❌ No active voice chat in {chat_id}")
        return False
        
    except GroupCallNotFound:
        logger.error(f"❌ Group call not found in {chat_id}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Playback error in {chat_id}: {e}")
        return False

async def check_admin(chat_id: int, user_id: int) -> bool:
    """Check if user is admin"""
    try:
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in [
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER
        ]
    except:
        return False

def format_duration(seconds: int) -> str:
    """Format duration in minutes:seconds"""
    if seconds <= 0:
        return "Live"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

# ============= EVENT HANDLERS =============

@calls.on_stream_end()
async def handle_stream_end(client, update):
    """Auto-play next song when current ends"""
    try:
        chat_id = update.chat_id
        logger.info(f"⏸️ Stream ended in {chat_id}")
        
        if chat_id in queues and queues[chat_id]:
            # Remove current song
            queues[chat_id].pop(0)
            
            if queues[chat_id]:
                # Play next song
                next_track = queues[chat_id][0]
                success = await start_playback(chat_id, next_track)
                
                if success:
                    logger.info(f"▶️ Auto-playing next: {next_track['title']}")
            else:
                # Queue empty, leave call
                try:
                    await calls.leave_call(chat_id)
                    playing.pop(chat_id, None)
                    logger.info(f"📭 Queue finished in {chat_id}, left call")
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Stream end handler error: {e}")

# ============= BOT COMMANDS =============

@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Start command - show welcome message"""
    await message.reply_text(
        "🎵 **Voice Chat Music Bot**\n\n"
        "**Available Commands:**\n"
        "• `/play <song name>` - Play a song\n"
        "• `/queue` - Show current queue\n"
        "• `/skip` - Skip current song\n"
        "• `/stop` - Stop and clear queue\n"
        "• `/pause` - Pause playback\n"
        "• `/resume` - Resume playback\n\n"
        "**Setup Instructions:**\n"
        "1. Add bot to your group\n"
        "2. Make bot admin with voice chat permissions\n"
        "3. Start voice chat in group\n"
        "4. Use `/play` command to start"
    )

@app.on_message(filters.command("play") & filters.group)
async def play_command(client, message: Message):
    """Play command - search and play song"""
    try:
        chat_id = message.chat.id
        
        # Check if song name provided
        if len(message.command) < 2:
            await message.reply_text(
                "❌ Please provide a song name!\n"
                "Usage: `/play <song name>`"
            )
            return
        
        # Get song query
        query = message.text.split(None, 1)[1]
        msg = await message.reply_text(f"🔍 **Searching:** {query}...")
        
        # Search YouTube
        track = await get_youtube_url(query)
        
        if not track:
            await msg.edit_text("❌ Song not found! Try a different name.")
            return
        
        # Add requester info
        track['by'] = message.from_user.mention if message.from_user else "Unknown"
        track['user_id'] = message.from_user.id if message.from_user else 0
        
        # Add to queue
        queues[chat_id].append(track)
        position = len(queues[chat_id])
        
        if position == 1:
            # First song - start playing
            await msg.edit_text("🎵 Joining voice chat...")
            
            success = await start_playback(chat_id, track)
            
            if success:
                duration = format_duration(track['duration'])
                await msg.edit_text(
                    f"🎵 **Now Playing**\n\n"
                    f"**Title:** {track['title']}\n"
                    f"**Duration:** {duration}\n"
                    f"**Requested by:** {track['by']}"
                )
            else:
                await msg.edit_text(
                    "❌ **Failed to join voice chat!**\n\n"
                    "**Please check:**\n"
                    "• Voice chat is started in group\n"
                    "• Bot is admin with voice chat permissions\n"
                    "• User assistant is not banned from group"
                )
                queues[chat_id].clear()
        else:
            # Added to queue
            await msg.edit_text(
                f"✅ **Added to Queue**\n\n"
                f"**Title:** {track['title']}\n"
                f"**Position:** #{position}\n"
                f"**Requested by:** {track['by']}"
            )
            
    except Exception as e:
        logger.error(f"Play command error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@app.on_message(filters.command("queue") & filters.group)
async def queue_command(client, message: Message):
    """Show current queue"""
    try:
        chat_id = message.chat.id
        queue = queues.get(chat_id, [])
        
        if not queue:
            await message.reply_text("📭 Queue is empty!")
            return
        
        text = f"📋 **Queue ({len(queue)} songs)**\n\n"
        
        for i, track in enumerate(queue[:10], 1):
            status = "▶️" if i == 1 else f"{i}."
            duration = format_duration(track['duration'])
            text += f"{status} **{track['title']}**\n"
            text += f"   Duration: {duration} | By: {track['by']}\n\n"
        
        if len(queue) > 10:
            text += f"...and {len(queue) - 10} more songs"
        
        await message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Queue command error: {e}")
        await message.reply_text("❌ Error showing queue")

@app.on_message(filters.command("skip") & filters.group)
async def skip_command(client, message: Message):
    """Skip current song"""
    try:
        chat_id = message.chat.id
        
        # Check if anything is playing
        if not queues[chat_id]:
            await message.reply_text("❌ Nothing is playing!")
            return
        
        # Check if user is admin
        if not await check_admin(chat_id, message.from_user.id):
            await message.reply_text("❌ Only admins can skip songs!")
            return
        
        # Remove current song
        queues[chat_id].pop(0)
        
        if queues[chat_id]:
            # Play next song
            next_track = queues[chat_id][0]
            success = await start_playback(chat_id, next_track)
            
            if success:
                await message.reply_text(
                    f"⏭️ **Skipped!**\n\n"
                    f"**Now playing:** {next_track['title']}"
                )
            else:
                await message.reply_text("❌ Failed to play next song")
        else:
            # Queue empty
            await calls.leave_call(chat_id)
            playing.pop(chat_id, None)
            await message.reply_text("⏭️ Skipped! Queue is now empty.")
            
    except Exception as e:
        logger.error(f"Skip command error: {e}")
        await message.reply_text("❌ Error skipping song")

@app.on_message(filters.command("stop") & filters.group)
async def stop_command(client, message: Message):
    """Stop playback and clear queue"""
    try:
        chat_id = message.chat.id
        
        # Check if user is admin
        if not await check_admin(chat_id, message.from_user.id):
            await message.reply_text("❌ Only admins can stop playback!")
            return
        
        # Leave call and clear queue
        await calls.leave_call(chat_id)
        queues[chat_id].clear()
        playing.pop(chat_id, None)
        
        await message.reply_text("⏹️ Stopped playback and cleared queue!")
        
    except Exception as e:
        logger.error(f"Stop command error: {e}")
        await message.reply_text("❌ Error stopping playback")

@app.on_message(filters.command("pause") & filters.group)
async def pause_command(client, message: Message):
    """Pause playback"""
    try:
        chat_id = message.chat.id
        
        # Check if user is admin
        if not await check_admin(chat_id, message.from_user.id):
            await message.reply_text("❌ Only admins can pause!")
            return
        
        await calls.pause_stream(chat_id)
        await message.reply_text("⏸️ Paused!")
        
    except Exception as e:
        await message.reply_text("❌ Nothing is playing")

@app.on_message(filters.command("resume") & filters.group)
async def resume_command(client, message: Message):
    """Resume playback"""
    try:
        chat_id = message.chat.id
        
        # Check if user is admin
        if not await check_admin(chat_id, message.from_user.id):
            await message.reply_text("❌ Only admins can resume!")
            return
        
        await calls.resume_stream(chat_id)
        await message.reply_text("▶️ Resumed!")
        
    except Exception as e:
        await message.reply_text("❌ Nothing is paused")

# ============= WEB SERVER (FOR RENDER) =============

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text="Music Bot is Running!", status=200)

async def start_web_server():
    """Start web server for Render deployment"""
    app_web = web.Application()
    app_web.router.add_get('/', health_check)
    app_web.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app_web)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"✅ Web server started on port {PORT}")
    return runner

# ============= MAIN FUNCTION =============

async def main():
    """Main function to start the bot"""
    logger.info("🚀 Starting Telegram Voice Chat Music Bot...")
    
    try:
        # Start web server
        await start_web_server()
        await asyncio.sleep(1)
        
        # Start bot client
        await app.start()
        logger.info("✅ Bot client started")
        
        # Start user client
        await user.start()
        logger.info("✅ User client started")
        
        # Start PyTgCalls
        await calls.start()
        logger.info("✅ PyTgCalls started")
        
        logger.info("=" * 60)
        logger.info("🎵 BOT IS READY!")
        logger.info("Send /start to the bot in a group to begin")
        logger.info("=" * 60)
        
        # Keep running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise
    finally:
        # Cleanup
        try:
            await calls.stop()
            await user.stop()
            await app.stop()
            logger.info("✅ Bot stopped gracefully")
        except:
            pass

# ============= ENTRY POINT =============

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
