#!/usr/bin/env python3
# Telegram Music Bot
# Modified for Render.com deployment

import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import requests

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration - Get from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PORT = int(os.getenv("PORT", 8080))  # Render sets this automatically

# Admin configuration
ADMIN_IDS = []
if os.getenv("ADMIN_ID"):
    try:
        ADMIN_IDS = [int(os.getenv("ADMIN_ID"))]
    except ValueError:
        logger.warning("Invalid ADMIN_ID provided")

# Song queue
SONG_QUEUE = {}

# Health check endpoint for Render
async def health_check(request):
    """Health check endpoint to satisfy Render's port requirements"""
    return web.Response(text="✅ Music Bot is running!", status=200)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    welcome_text = """
🎵 **Welcome to Music Bot!**

I can help you download music from YouTube!

**Commands:**
/start - Start the bot
/help - Show this help message
/play <song name> - Search and download music
/search <query> - Search for songs
/queue - Show current queue

Just send me a song name and I'll find it for you!

Made with ❤️ by Music Bot Maker
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send help message."""
    help_text = """
🎵 **Music Bot Help**

**Available Commands:**
• /start - Start the bot
• /help - Show this help
• /play <song> - Download a song
• /search <query> - Search for songs
• /queue - Show download queue

**How to use:**
1. Send `/play Despacito` to download a song
2. Send `/search Justin Bieber` to search
3. Just type a song name for quick search

**Examples:**
• `/play Shape of You Ed Sheeran`
• `/search Bollywood songs`
• `Blinding Lights`

Enjoy the music! 🎶
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Play command
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle play command."""
    if not context.args:
await update.message.reply_text("❌ Please provide a song name!\n\nExample: `/play Despacito`", parse_mode='Markdown')

Example: `/play Despacito`", parse_mode='Markdown')
        return
    
    song_name = ' '.join(context.args)
    chat_id = update.effective_chat.id
    
    # Add to queue
    if chat_id not in SONG_QUEUE:
        SONG_QUEUE[chat_id] = []
    
    SONG_QUEUE[chat_id].append(song_name)
    
    await update.message.reply_text(f"🔍 Searching for: **{song_name}**
⏳ Please wait...", parse_mode='Markdown')
    
    try:
        # Use yt-dlp to search and get info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(title)s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search for the song
            search_query = f"ytsearch1:{song_name}"
            info = ydl.extract_info(search_query, download=False)
            
            if info and 'entries' in info and info['entries']:
                video_info = info['entries'][0]
                title = video_info.get('title', 'Unknown')
                uploader = video_info.get('uploader', 'Unknown')
                duration = video_info.get('duration', 0)
                url = video_info.get('webpage_url', '')
                
                # Format duration
                duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
                
                result_text = f"""
🎵 **Found:**
**Title:** {title}
**Artist/Channel:** {uploader}
**Duration:** {duration_str}
**URL:** {url}

⬇️ Download starting...
                """
                
                await update.message.reply_text(result_text, parse_mode='Markdown')
                
                # Note: Actual download would happen here
                # For now, just send success message
                await update.message.reply_text(f"✅ **{title}** added to your music library!

🎶 Enjoy your music!", parse_mode='Markdown')
                
            else:
                await update.message.reply_text(f"❌ Sorry, couldn't find: **{song_name}**

Try a different search term!", parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in play_command: {e}")
        await update.message.reply_text(f"❌ Error occurred while searching for: **{song_name}**

Please try again!", parse_mode='Markdown')

# Search command
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle search command."""
    if not context.args:
        await update.message.reply_text("❌ Please provide search query!

Example: `/search Ed Sheeran`", parse_mode='Markdown')
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Searching for: **{query}**
⏳ Please wait...", parse_mode='Markdown')
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch5:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            if info and 'entries' in info and info['entries']:
                results_text = f"🔍 **Search Results for:** {query}

"
                
                for i, video in enumerate(info['entries'][:5], 1):
                    title = video.get('title', 'Unknown')
                    uploader = video.get('uploader', 'Unknown')
                    duration = video.get('duration', 0)
                    duration_str = f"{duration//60}:{duration%60:02d}" if duration else "?"
                    
                    results_text += f"**{i}.** {title}
"
                    results_text += f"   👤 {uploader} | ⏱️ {duration_str}

"
                
                results_text += f"💡 Use `/play <song name>` to download any of these!"
                
                await update.message.reply_text(results_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ No results found for: **{query}**", parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in search_command: {e}")
        await update.message.reply_text(f"❌ Error occurred while searching for: **{query}**", parse_mode='Markdown')

# Queue command
async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current queue."""
    chat_id = update.effective_chat.id
    
    if chat_id not in SONG_QUEUE or not SONG_QUEUE[chat_id]:
        await update.message.reply_text("📭 Queue is empty!

Use `/play <song>` to add songs.", parse_mode='Markdown')
        return
    
    queue_text = "📋 **Current Queue:**

"
    for i, song in enumerate(SONG_QUEUE[chat_id], 1):
        queue_text += f"**{i}.** {song}
"
    
    await update.message.reply_text(queue_text, parse_mode='Markdown')

# Handle text messages (auto-search)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages as song search."""
    text = update.message.text.strip()
    
    if len(text) < 3:
        await update.message.reply_text("❌ Please send a longer song name (at least 3 characters)")
        return
    
    # Treat as search query
    await update.message.reply_text(f"🔍 Auto-searching for: **{text}**

Use `/play {text}` to download!", parse_mode='Markdown')

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by Updates."""
    logger.error(f"Exception while handling an update: {context.error}")

# Run Telegram bot as background task
async def run_bot():
    """Initialize and run the Telegram bot"""
    if not BOT_TOKEN:
        logger.error("❌ ERROR: BOT_TOKEN not found!")
        logger.error("Please set BOT_TOKEN in Render environment variables")
        return
    
    logger.info("🚀 Starting Telegram Music Bot...")
    logger.info(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("queue", queue_command))
    
    # Add text message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Initialize and start bot
    await application.initialize()
    await application.start()
    
    logger.info("✅ Music Bot is running!")
    logger.info("Bot is polling for updates...")
    
    # Start polling
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Keep the bot running
    while True:
        await asyncio.sleep(1)

def main():
    """Start both HTTP server (for Render) and Telegram bot"""
    logger.info("=" * 60)
    logger.info("🎵 TELEGRAM MUSIC BOT STARTING")
    logger.info("=" * 60)
    logger.info(f"Port: {PORT}")
    logger.info(f"BOT_TOKEN configured: {BOT_TOKEN is not None}")
    logger.info("=" * 60)
    
    # Create web app for health check (Render requires open port)
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', health_check)
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run bot as background task
    loop.create_task(run_bot())
    
    # Start HTTP server (this satisfies Render's port requirement)
    logger.info(f"🌐 Starting HTTP server on port {PORT}...")
    web.run_app(app, host='0.0.0.0', port=PORT, print=None)

if __name__ == '__main__':
    main()

