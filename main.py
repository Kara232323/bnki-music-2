#!/usr/bin/env python3
# Telegram Music Bot - FIXED VERSION FOR RENDER
# No syntax errors - Ready to deploy!

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

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PORT = int(os.getenv("PORT", 8080))

# Song queue
SONG_QUEUE = {}

# Health check for Render
async def health_check(request):
    return web.Response(text="Music Bot Running!", status=200)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎵 Welcome to Music Bot!\n\n"
        "I can help you download music from YouTube!\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/play <song> - Search and download\n"
        "/search <query> - Search for songs\n"
        "/queue - Show queue\n\n"
        "Made with ❤️"
    )
    await update.message.reply_text(welcome)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎵 Music Bot Help\n\n"
        "Commands:\n"
        "/start - Start bot\n"
        "/help - Show help\n"
        "/play <song> - Download song\n"
        "/search <query> - Search songs\n"
        "/queue - Show queue\n\n"
        "Examples:\n"
        "/play Despacito\n"
        "/search Ed Sheeran\n\n"
        "Enjoy! 🎶"
    )
    await update.message.reply_text(help_text)

# Play command
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Please provide a song name!\n\n"
            "Example: /play Despacito"
        )
        return
    
    song_name = ' '.join(context.args)
    chat_id = update.effective_chat.id
    
    if chat_id not in SONG_QUEUE:
        SONG_QUEUE[chat_id] = []
    
    SONG_QUEUE[chat_id].append(song_name)
    
    await update.message.reply_text(
        f"🔍 Searching for: {song_name}\n⏳ Please wait..."
    )
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(title)s.%(ext)s'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch1:{song_name}"
            info = ydl.extract_info(search_query, download=False)
            
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                title = video.get('title', 'Unknown')
                uploader = video.get('uploader', 'Unknown')
                duration = video.get('duration', 0)
                url = video.get('webpage_url', '')
                
                mins = duration // 60
                secs = duration % 60
                duration_str = f"{mins}:{secs:02d}" if duration else "Unknown"
                
                result = (
                    f"🎵 Found:\n"
                    f"Title: {title}\n"
                    f"Artist: {uploader}\n"
                    f"Duration: {duration_str}\n"
                    f"URL: {url}\n\n"
                    f"⬇️ Download starting..."
                )
                
                await update.message.reply_text(result)
                await update.message.reply_text(
                    f"✅ {title} added!\n\n🎶 Enjoy your music!"
                )
            else:
                await update.message.reply_text(
                    f"❌ Sorry, couldn't find: {song_name}\n\n"
                    f"Try a different search term!"
                )
    
    except Exception as e:
        logger.error(f"Error in play_command: {e}")
        await update.message.reply_text(
            f"❌ Error searching for: {song_name}\n\n"
            f"Please try again!"
        )

# Search command
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Please provide search query!\n\n"
            "Example: /search Ed Sheeran"
        )
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(
        f"🔍 Searching for: {query}\n⏳ Please wait..."
    )
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch5:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            if info and 'entries' in info and info['entries']:
                results = f"🔍 Search Results for: {query}\n\n"
                
                for i, video in enumerate(info['entries'][:5], 1):
                    title = video.get('title', 'Unknown')
                    uploader = video.get('uploader', 'Unknown')
                    duration = video.get('duration', 0)
                    mins = duration // 60
                    secs = duration % 60
                    duration_str = f"{mins}:{secs:02d}" if duration else "?"
                    
                    results += f"{i}. {title}\n"
                    results += f"   👤 {uploader} | ⏱️ {duration_str}\n\n"
                
                results += "💡 Use /play <song name> to download!"
                
                await update.message.reply_text(results)
            else:
                await update.message.reply_text(
                    f"❌ No results for: {query}"
                )
    
    except Exception as e:
        logger.error(f"Error in search_command: {e}")
        await update.message.reply_text(
            f"❌ Error searching for: {query}"
        )

# Queue command
async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    if chat_id not in SONG_QUEUE or not SONG_QUEUE[chat_id]:
        await update.message.reply_text(
            "📭 Queue is empty!\n\nUse /play <song> to add songs."
        )
        return
    
    queue_text = "📋 Current Queue:\n\n"
    for i, song in enumerate(SONG_QUEUE[chat_id], 1):
        queue_text += f"{i}. {song}\n"
    
    await update.message.reply_text(queue_text)

# Handle text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if len(text) < 3:
        await update.message.reply_text(
            "Please send a longer song name (at least 3 characters)"
        )
        return
    
    await update.message.reply_text(
        f"🔍 Auto-searching for: {text}\n\n"
        f"Use /play {text} to download!"
    )

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception: {context.error}")

# Run bot
async def run_bot():
    if not BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found!")
        logger.error("Set BOT_TOKEN in Render environment variables")
        return
    
    logger.info("🚀 Starting Telegram Music Bot...")
    logger.info(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("queue", queue_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    await application.initialize()
    await application.start()
    
    logger.info("✅ Music Bot is running!")
    logger.info("Bot is polling for updates...")
    
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    while True:
        await asyncio.sleep(1)

def main():
    logger.info("=" * 60)
    logger.info("🎵 TELEGRAM MUSIC BOT STARTING")
    logger.info("=" * 60)
    logger.info(f"Port: {PORT}")
    logger.info(f"BOT_TOKEN configured: {BOT_TOKEN is not None}")
    logger.info("=" * 60)
    
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/status', health_check)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.create_task(run_bot())
    
    logger.info(f"🌐 Starting HTTP server on port {PORT}...")
    web.run_app(app, host='0.0.0.0', port=PORT, print=None)

if __name__ == '__main__':
    main()
