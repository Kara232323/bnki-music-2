#!/usr/bin/env python3
# Telegram Music Bot - ASYNCIO FIXED VERSION

import os
import asyncio
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))
SONG_QUEUE = {}

# Health check
async def health_check(request):
    return web.Response(text="Music Bot Running!", status=200)

# Bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎵 Welcome to Music Bot!\n\n"
        "Commands:\n"
        "/start - Start\n"
        "/help - Help\n"
        "/play <song> - Play song\n"
        "/search <query> - Search\n"
        "/queue - Show queue\n\n"
        "Made with ❤️"
    )
    await update.message.reply_text(welcome)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Music Bot Help\n\n"
        "/start - Start bot\n"
        "/help - Show help\n"
        "/play <song> - Download\n"
        "/search <query> - Search\n"
        "/queue - Show queue"
    )

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a song name!\n\nExample: /play Despacito")
        return
    
    song_name = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Searching: {song_name}\n⏳ Wait...")
    
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{song_name}", download=False)
            if info and 'entries' in info and info['entries']:
                video = info['entries'][0]
                title = video.get('title', 'Unknown')
                await update.message.reply_text(f"✅ Found: {title}\n\n🎶 Enjoy!")
            else:
                await update.message.reply_text(f"❌ Not found: {song_name}")
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Error searching: {song_name}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Provide query!\n\nExample: /search Ed Sheeran")
        return
    
    query = ' '.join(context.args)
    await update.message.reply_text(f"🔍 Searching: {query}")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📭 Queue is empty!")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# Initialize bot
async def init_bot():
    if not BOT_TOKEN:
        logger.error("ERROR: BOT_TOKEN not found!")
        return None
    
    logger.info("🚀 Initializing bot...")
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_error_handler(error_handler)
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("✅ Bot is running!")
    return app

# Main function
async def main_async():
    logger.info("=" * 60)
    logger.info("🎵 TELEGRAM MUSIC BOT")
    logger.info("=" * 60)
    logger.info(f"Port: {PORT}")
    logger.info("=" * 60)
    
    # Start bot
    bot_app = await init_bot()
    if not bot_app:
        logger.error("Failed to initialize bot")
        return
    
    # Create web server
    web_app = web.Application()
    web_app.router.add_get('/', health_check)
    web_app.router.add_get('/health', health_check)
    
    # Start web server
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 Web server running on port {PORT}")
    logger.info("✅ All services started!")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await bot_app.stop()
        await bot_app.shutdown()
        await runner.cleanup()

def main():
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == '__main__':
    main()
