import os
import yt_dlp
import logging
import subprocess
import asyncio
import glob
import json
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, ContextTypes, filters

# تثبيت المكتبات المطلوبة تلقائيًا
try:
    subprocess.run(["pip", "install", "-U", "yt_dlp"], check=True)
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Update failed: {e}")

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
user_links = {}
user_lang = {}

STATS_FILE = 'stats.json'

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {"users": [], "downloads": 0}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f)

def add_user(user_id):
    stats = load_stats()
    if user_id not in stats["users"]:
        stats["users"].append(user_id)
    save_stats(stats)

def add_download():
    stats = load_stats()
    stats["downloads"] += 1
    save_stats(stats)

# النصوص (عربي/إنجليزي)
TEXTS = {
    'ar': {
        'welcome': "👋 أهلاً {name}!\n\n🐂 أنا *Mini Toros* - بوت التحميل الأقوى!\n\n📥 أرسل لي أي رابط من:\n▸ يوتيوب 🎬\n▸ انستغرام 📸\n▸ تيك توك 🎵\n▸ فيسبوك 👥\n▸ تويتر/X 🐦\n▸ وأكثر من 1000 موقع! 🌐\n\n⚡ اكتب /help للمساعدة",
        'help': "📖 *كيف تستخدم البوت؟*\n\n1️⃣ أرسل رابط الفيديو\n2️⃣ اختر نوع التحميل\n3️⃣ اختر الجودة\n4️⃣ انتظر وبيوصلك الملف! ✅",
        'about': "🐂 *Mini Toros Bot*\n\n📌 الإصدار: 2.0\n⚡ يدعم أكثر من 1000 موقع\n🌐 يفتح المواقع بـ Chrome الحقيقي\n🎵 يحول لـ MP3 بجودة عالية\n📹 يدعم جودة حتى 4K",
        'stats': "📊 *إحصائيات Mini Toros*\n\n👥 المستخدمون: {users}\n📥 التحميلات: {downloads}\n\n🕐 {time}",
        'link_received': "🔗 *تم استلام الرابط!*\nاختر نوع التحميل:",
        'choose_quality': "🎬 *اختر الجودة:*",
        'downloading': "📥 *جاري التحميل...*\n{bar}",
        'sending': "📤 *جاري الإرسال...*",
        'chrome': "🌐 *جاري فتح الموقع بـ Chrome...*",
        'success': "✅ *تم التحميل بنجاح!*",
        'error_failed': "❌ ما قدرت أحمل الفيديو.",
        'error': "❌ خطأ: {e}",
        'btn_video': "🎥 فيديو",
        'btn_audio': "🎵 أغنية فقط",
        'btn_best': "🔥 أفضل جودة (4K)",
        'btn_1080': "📺 1080p",
        'btn_720': "📱 720p",
        'lang_changed': "✅ تم تغيير اللغة إلى العربية!",
    },
    'en': {
        'welcome': "👋 Hello {name}!\n\n🐂 I'm *Mini Toros* - The Ultimate Download Bot!",
        'help': "📖 *How to use the bot?*\n\n1️⃣ Send a video link\n2️⃣ Choose download type\n3️⃣ Choose quality\n4️⃣ Wait for your file! ✅",
        'about': "🐂 *Mini Toros Bot*\n\n📌 Version: 2.0\n⚡ Supports 1000+ websites\n🌐 Opens sites with real Chrome\n🎵 Converts to high quality MP3\n📹 Supports up to 4K quality",
        'stats': "📊 *Mini Toros Statistics*\n\n👥 Users: {users}\n📥 Downloads: {downloads}\n\n🕐 {time}",
        'link_received': "🔗 *Link received!*\nChoose download type:",
        'choose_quality': "🎬 *Choose quality:*",
        'downloading': "📥 *Downloading...*\n{bar}",
        'sending': "📤 *Sending...*",
        'chrome': "🌐 *Opening with Chrome...*",
        'success': "✅ *Downloaded successfully!*",
        'error_failed': "❌ Failed to download the video.",
        'error': "❌ Error: {e}",
        'btn_video': "🎥 Video",
        'btn_audio': "🎵 Audio only",
        'btn_best': "🔥 Best quality (4K)",
        'btn_1080': "📺 1080p",
        'btn_720': "📱 720p",
        'lang_changed': "✅ Language changed to English!",
    }
}

def t(chat_id, key, **kwargs):
    lang = user_lang.get(chat_id, 'ar')
    text = TEXTS[lang].get(key, '')
    return text.format(**kwargs) if kwargs else text

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_user(chat_id)
    name = update.message.from_user.first_name
    keyboard = [[InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
                 InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]]
    await update.message.reply_text(t(chat_id, 'welcome', name=name),
                                    parse_mode='Markdown',
                                    reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(update.effective_chat.id, 'help'), parse_mode='Markdown')

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(update.effective_chat.id, 'about'), parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    await update.message.reply_text(
        t(update.effective_chat.id, 'stats',
          users=len(stats['users']),
          downloads=stats['downloads'],
          time=datetime.now().strftime('%Y-%m-%d %H:%M')),
        parse_mode='Markdown'
    )

async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
                 InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]]
    await update.message.reply_text("🌐 Choose language / اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))

# استقبال الروابط
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return
    chat_id = update.effective_chat.id
    add_user(chat_id)
    user_links[chat_id] = url
    keyboard = [[InlineKeyboardButton(t(chat_id, 'btn_video'), callback_data="type_video"),
                 InlineKeyboardButton(t(chat_id, 'btn_audio'), callback_data="type_audio")]]
    await update.message.reply_text(t(chat_id, 'link_received'),
                                    reply_markup=InlineKeyboardMarkup(keyboard),
                                    parse_mode='Markdown')

# شريط التقدم
def make_progress_bar(percent):
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent:.0f}%"

# تحميل الفيديو
async def download_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, manual_type=None, manual_quality=None):
    query = update.callback_query
    chat_id = update.effective_chat.id

    if manual_type:
        media_type, quality = manual_type, manual_quality
    else:
        parts = query.data.split("_")
        media_type, quality = parts[1], parts[2]

    url = user_links.get(chat_id)
    loading_msg = await query.edit_message_text("⏳ ...")

    # التعامل مع cookies.txt أو cookies.txt.txt
    cookie_file = None
    for fname in ["cookies.txt", "cookies.txt.txt"]:
        if os.path.exists(fname):
            cookie_file = fname
            break

    last_update = [0]
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                percent = float(d.get('_percent_str', '0%').strip().replace('%', '
