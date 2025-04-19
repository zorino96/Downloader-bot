from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import os
import re
import logging
from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs
import asyncio

# دانانی لۆگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# تۆکینی بۆتەکە
TOKEN = "7239426464:AAEqWwuQbcZ7fY3qT325rI8FzLUDJzlJBSo"

# هەندێک پاتێرن بۆ ناسینەوەی لینکەکان
URL_PATTERN = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
YOUTUBE_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/(?:watch\?v=)?([^\s&]+)')
INSTAGRAM_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/([^\s/]+)')
TWITTER_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+')
FACEBOOK_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?facebook\.com/(?:\w+/videos/\d+|watch/\?v=\d+)')
SNAPCHAT_PATTERN = re.compile(r'(?:https?://)?(?:www\.)?snapchat\.com/(?:add|discover)/[^\s]+')

# ئاستانسی بۆتی تەلەگرام
bot = Bot(token=TOKEN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هەنگاوی سەرەتایی کاتێک بەکارهێنەر /start دادەگرێت"""
    await update.message.reply_text(
        'سڵاو! من بۆتێکم بۆ داونلۆدکردنی ڤیدیۆ لە یوتیوب، ئینستاگرام، تویتەر، فەیسبووک و سناپچات.\n'
        'تەنها لینکی ڤیدیۆکە بنێرە، من بۆت داونلۆد دەکەم!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """وەڵامدانەوەی فەرمانی /help"""
    await update.message.reply_text(
        'ڕێنمایی بەکارهێنان:\n'
        '1. تەنها لینکی ڤیدیۆکە بنێرە\n'
        '2. چاوەڕێ بکە تا ڤیدیۆکە داونلۆد دەبێت\n'
        '3. ڤیدیۆکە بۆت دەنێردرێت!'
    )

def extract_url(text):
    """دەرهێنانی لینک لە نێو تێکستدا"""
    match = URL_PATTERN.search(text)
    if match:
        return match.group(0)
    return None

async def download_from_url(url):
    """داونلۆدکردنی ڤیدیۆ لە لینکەوە بە بەکارهێنانی yt-dlp"""
    # لەسەر Vercel، دەبێت فایلەکان لە /tmp هەڵبگرین
    output_template = '/tmp/downloaded_video.%(ext)s'
    
    ydl_opts = {
        'format': 'best[filesize<50M]/best', # باشترین کوالیتی کەمتر لە 50MB
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            return f'/tmp/downloaded_video.{ext}'
    except Exception as e:
        logging.error(f"هەڵە لە yt-dlp: {str(e)}")
        raise

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """وەرگرتنی لینک و داونلۆدکردنی ڤیدیۆ"""
    url = extract_url(update.message.text)
    
    if not url:
        await update.message.reply_text("تکایە لینکێکی دروست بنێرە")
        return
    
    # پێش داونلۆدکردن، پەیامێک بنێرە
    await update.message.reply_text("لە پرۆسەی داونلۆدکردندایە، تکایە چاوەڕێ بکە...")
    
    try:
        file_path = await download_from_url(url)
        
        # ناردنی ڤیدیۆکە
        await send_video(update, context, file_path)
        
        # پاکردنەوەی فایل دوای ناردن
        if os.path.exists(file_path):
            os.remove(file_path)
        
    except Exception as e:
        logging.error(f"هەڵە لە کاتی داونلۆدکردن: {str(e)}")
        await update.message.reply_text(f"ببورە، کێشەیەک هەیە لە داونلۆدکردنی ڤیدیۆکە: {str(e)}")

async def send_video(update, context, file_path):
    """ناردنی ڤیدیۆکە بۆ بەکارهێنەر"""
    if not os.path.exists(file_path):
        await update.message.reply_text("ببورە، نەتوانرا ڤیدیۆکە بدۆزرێتەوە.")
        return
        
    file_size = os.path.getsize(file_path)
    
    # ئەگەر قەبارەکەی گەورەتر بوو لە 50MB، ئاگاداری بدە
    if file_size > 50 * 1024 * 1024:
        await update.message.reply_text(
            "ڤیدیۆکە زۆر گەورەیە بۆ ناردن لە تەلەگرام (زیاتر لە 50MB)."
        )
        return
    
    try:
        with open(file_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption="ڤیدیۆکە بە سەرکەوتوویی داونلۆد کرا!",
                supports_streaming=True
            )
    except Exception as e:
        logging.error(f"هەڵە لە کاتی ناردنی ڤیدیۆ: {str(e)}")
        await update.message.reply_text(f"هەڵەیەک ڕوویدا لە کاتی ناردنی ڤیدیۆکە: {str(e)}")

# دروستکردنی ئەپلیکەیشن
application = Application.builder().token(TOKEN).build()

# زیادکردنی هەندڵەرەکان
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

# ڕێگەی webhook بۆ وەرگرتنی ئاپدەیتەکان لە تەلەگرامەوە
async def process_update(update_data):
    update = Update.de_json(update_data, bot)
    await application.process_update(update)

# کڵاسی هەندڵەری داواکاری HTTP بۆ Vercel
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write('پێشوازی لە بۆتی داونلۆدکردنی ڤیدیۆ!'.encode())
        return
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        update_data = json.loads(post_data.decode())
        
        # بەکارهێنانی asyncio بۆ جێبەجێکردنی پرۆسێسی ئاپدەیت بە نەهێڵی
        asyncio.run(process_update(update_data))
        
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write('OK'.encode())
        return
