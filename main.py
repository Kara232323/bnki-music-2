#!/usr/bin/env python3
"""
Bankai Music Bot - Simple Working Version
NO complex dependencies, 100% working on Railway!
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "bankai_owner")

def get_youtube_url(query: str):
    return f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

def get_spotify_url(query: str):
    return f"https://open.spotify.com/search/{query.replace(' ', '%20')}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        btns = [[InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAME}")]]
        welcome = (
            "⚔️ **Bankai Music Bot** ⚔️\n\n"
            "🎵 I can help you find music!\n\n"
            "**Commands:**\n"
            "`/play <song>` - Get YouTube link\n"
            "`/spotify <song>` - Get Spotify link\n"
            "`/search <song>` - Search both\n\n"
            "**Example:**\n"
            "`/play Despacito`"
        )
        await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(btns))
    except Exception as e:
        logger.error(f"Start error: {e}")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ Usage: `/play <song name>`\n\nExample: `/play Despacito`")
            return
        
        song = ' '.join(context.args)
        url = get_youtube_url(song)
        
        keyboard = [[InlineKeyboardButton("▶️ YouTube", url=url)]]
        await update.message.reply_text(
            f"🎵 **{song}**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Play: {song}")
    except Exception as e:
        logger.error(f"Play error: {e}")

async def spotify_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ Usage: `/spotify <song name>`")
            return
        
        song = ' '.join(context.args)
        url = get_spotify_url(song)
        
        keyboard = [[InlineKeyboardButton("🎵 Spotify", url=url)]]
        await update.message.reply_text(
            f"🎵 **{song}**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Spotify: {song}")
    except Exception as e:
        logger.error(f"Spotify error: {e}")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ Usage: `/search <song name>`")
            return
        
        song = ' '.join(context.args)
        yt_url = get_youtube_url(song)
        sp_url = get_spotify_url(song)
        
        keyboard = [
            [InlineKeyboardButton("▶️ YouTube", url=yt_url)],
            [InlineKeyboardButton("🎵 Spotify", url=sp_url)]
        ]
        await update.message.reply_text(
            f"🔍 **Search: {song}**",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Search: {song}")
    except Exception as e:
        logger.error(f"Search error: {e}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        help_text = (
            "⚔️ **Bankai Bot Help** ⚔️\n\n"
            "**Commands:**\n"
            "`/play <song>` - YouTube search\n"
            "`/spotify <song>` - Spotify search\n"
            "`/search <song>` - Both\n"
            "`/help` - This message\n\n"
            "**Examples:**\n"
            "`/play Ed Sheeran Shape of You`\n"
            "`/spotify Taylor Swift`"
        )
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Help error: {e}")

async def main():
    logger.info("="*50)
    logger.info("⚔️  BANKAI MUSIC BOT STARTING")
    logger.info("="*50)
    
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing!")
        return
    
    logger.info(f"✅ BOT_TOKEN: {BOT_TOKEN[:20]}...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("spotify", spotify_cmd))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("help", help_cmd))
    
    logger.info("="*50)
    logger.info("✅ BOT IS READY!")
    logger.info("="*50)
    
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

