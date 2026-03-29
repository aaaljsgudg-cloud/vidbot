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

try:
    subprocess.run(["pip", "install", "-U", "yt_dlp"], check=True)
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    print(f"Update failed: {e}")

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
user_links = {}
user_lang = {}  # لحفظ لغة كل مستخدم

STATS_FILE = 'stats.json'
print(f"Cookie file exists: {os.path.exists('cookies.txt.txt')}")
print(f"Working directory: {os.getcwd()}")
print(f"Files in dir: {os.listdir('.')}")

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

# --- النصوص بالعربي والإنجليزي ---
TEXTS = {
    'ar': {
        'welcome': "👋 أهلاً {name}!\n\n🐂 أنا *Mini Toros* - بوت التحميل الأقوى!\n\n📥 أرسل لي أي رابط من:\n▸ يوتيوب 🎬\n▸ انستغرام 📸\n▸ تيك توك 🎵\n▸ فيسبوك 👥\n▸ تويتر/X 🐦\n▸ وأكثر من 1000 موقع! 🌐\n\n⚡ اكتب /help للمساعدة",
        'help': "📖 *كيف تستخدم البوت؟*\n\n1️⃣ أرسل رابط الفيديو\n2️⃣ اختر نوع التحميل\n3️⃣ اختر الجودة\n4️⃣ انتظر وبيوصلك الملف! ✅\n\n📌 *الأوامر:*\n/start - البداية\n/help - المساعدة\n/about - عن البوت\n/stats - الإحصائيات\n/lang - تغيير اللغة",
        'about': "🐂 *Mini Toros Bot*\n\n📌 الإصدار: 2.0\n⚡ يدعم أكثر من 1000 موقع\n🌐 يفتح المواقع بـ Chrome الحقيقي\n🎵 يحول لـ MP3 بجودة عالية\n📹 يدعم جودة حتى 4K\n\n💪 صُنع بكل احترافية!",
        'stats': "📊 *إحصائيات Mini Toros*\n\n👥 المستخدمون: {users}\n📥 التحميلات: {downloads}\n\n🕐 {time}",
        'link_received': "🔗 *تم استلام الرابط!*\nاختر نوع التحميل:",
        'choose_quality': "🎬 *اختر الجودة:*",
        'downloading': "📥 *جاري التحميل...*\n{bar}",
        'sending': "📤 *جاري الإرسال...*",
        'chrome': "🌐 *جاري فتح الموقع بـ Chrome...*",
        'success': "✅ *تم التحميل بنجاح!*\n🐂 Mini Toros Bot",
        'error_protected': "❌ الموقع محمي ومش ممكن السحب منه.",
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
        'welcome': "👋 Hello {name}!\n\n🐂 I'm *Mini Toros* - The Ultimate Download Bot!\n\n📥 Send me any link from:\n▸ YouTube 🎬\n▸ Instagram 📸\n▸ TikTok 🎵\n▸ Facebook 👥\n▸ Twitter/X 🐦\n▸ 1000+ websites! 🌐\n\n⚡ Type /help for help",
        'help': "📖 *How to use the bot?*\n\n1️⃣ Send a video link\n2️⃣ Choose download type\n3️⃣ Choose quality\n4️⃣ Wait for your file! ✅\n\n📌 *Commands:*\n/start - Start\n/help - Help\n/about - About\n/stats - Statistics\n/lang - Change language",
        'about': "🐂 *Mini Toros Bot*\n\n📌 Version: 2.0\n⚡ Supports 1000+ websites\n🌐 Opens sites with real Chrome\n🎵 Converts to high quality MP3\n📹 Supports up to 4K quality\n\n💪 Built with professionalism!",
        'stats': "📊 *Mini Toros Statistics*\n\n👥 Users: {users}\n📥 Downloads: {downloads}\n\n🕐 {time}",
        'link_received': "🔗 *Link received!*\nChoose download type:",
        'choose_quality': "🎬 *Choose quality:*",
        'downloading': "📥 *Downloading...*\n{bar}",
        'sending': "📤 *Sending...*",
        'chrome': "🌐 *Opening with Chrome...*",
        'success': "✅ *Downloaded successfully!*\n🐂 Mini Toros Bot",
        'error_protected': "❌ This site is protected and cannot be downloaded.",
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

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    add_user(chat_id)
    name = update.message.from_user.first_name

    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        t(chat_id, 'welcome', name=name),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- /help ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(update.message.chat_id, 'help'), parse_mode='Markdown')

# --- /about ---
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(t(update.message.chat_id, 'about'), parse_mode='Markdown')

# --- /stats ---
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = load_stats()
    await update.message.reply_text(
        t(update.message.chat_id, 'stats',
          users=len(stats['users']),
          downloads=stats['downloads'],
          time=datetime.now().strftime('%Y-%m-%d %H:%M')),
        parse_mode='Markdown'
    )

# --- /lang ---
async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
         InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
    ]
    await update.message.reply_text("🌐 Choose language / اختر اللغة:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Playwright ---
async def extract_video_with_playwright(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        video_urls = []

        async def handle_request(request):
            req_url = request.url
            if any(ext in req_url for ext in ['.mp4', '.m3u8', '.ts', '.webm', 'video', 'media', 'stream']):
                if req_url not in video_urls:
                    video_urls.append(req_url)

        page.on("request", handle_request)
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)
        except:
            pass
        await browser.close()
        return video_urls[0] if video_urls else None

# --- استقبال الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return

    chat_id = update.message.chat_id
    add_user(chat_id)
    user_links[chat_id] = url

    keyboard = [
        [InlineKeyboardButton(t(chat_id, 'btn_video'), callback_data="type_video"),
         InlineKeyboardButton(t(chat_id, 'btn_audio'), callback_data="type_audio")]
    ]
    await update.message.reply_text(
        t(chat_id, 'link_received'),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

# --- شريط التقدم ---
def make_progress_bar(percent):
    filled = int(percent / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent:.0f}%"

# --- callback handler ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    # تغيير اللغة
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        user_lang[chat_id] = lang
        await query.edit_message_text(t(chat_id, 'lang_changed'))
        return

    # اختيار النوع
    if data.startswith("type_"):
        choice = data.split("_")[1]
        if choice == "audio":
            await download_logic(update, context, "audio", "best")
        else:
            keyboard = [
                [InlineKeyboardButton(t(chat_id, 'btn_best'), callback_data="down_video_best")],
                [InlineKeyboardButton(t(chat_id, 'btn_1080'), callback_data="down_video_1080")],
                [InlineKeyboardButton(t(chat_id, 'btn_720'), callback_data="down_video_720")]
            ]
            await query.edit_message_text(
                t(chat_id, 'choose_quality'),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        return

    # تحميل
    if data.startswith("down_"):
        await download_logic(update, context)

# --- المحرك الرئيسي ---
async def download_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, manual_type=None, manual_quality=None):
    query = update.callback_query
    chat_id = query.message.chat_id

    if manual_type:
        media_type, quality = manual_type, manual_quality
    else:
        parts = query.data.split("_")
        media_type, quality = parts[1], parts[2]

    url = user_links.get(chat_id)
    loading_msg = await query.edit_message_text("⏳ ...")

    cookie_file = 'cookies.txt.txt' if os.path.exists('cookies.txt.txt') else ('cookies.txt' if os.path.exists('cookies.txt') else None)

    last_update = [0]
    async def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                percent = float(d.get('_percent_str', '0%').strip().replace('%', ''))
                if percent - last_update[0] >= 10:
                    last_update[0] = percent
                    bar = make_progress_bar(percent)
                    await loading_msg.edit_text(t(chat_id, 'downloading', bar=bar), parse_mode='Markdown')
            except:
                pass

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'cookiefile': cookie_file,
        'progress_hooks': [lambda d: asyncio.create_task(progress_hook(d))],
        'extractor_args': {'youtube': {'player_client': ['web', 'android']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': url,
        },
        'nocheckcertificate': True,
        'geo_bypass': True,
    }

    if media_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
    else:
        height = "1080" if quality == "1080" else ("720" if quality == "720" else "2160")
        ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best'

    success = False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        files = glob.glob(f'downloads/{chat_id}_*')
        path = files[0] if files else None

        if path and os.path.exists(path):
            success = True
            add_download()
            await loading_msg.edit_text(t(chat_id, 'sending'), parse_mode='Markdown')
            with open(path, 'rb') as f:
                caption = t(chat_id, 'success')
                if media_type == "audio":
                    await context.bot.send_audio(chat_id, f, caption=caption, parse_mode='Markdown')
                else:
                    await context.bot.send_video(chat_id, f, caption=caption, parse_mode='Markdown')
            os.remove(path)
            try: await loading_msg.delete()
            except: pass

    except Exception as e:
        logging.warning(f"yt-dlp failed: {e}")

    if not success:
        try:
            await loading_msg.edit_text(t(chat_id, 'chrome'), parse_mode='Markdown')
            video_url = await extract_video_with_playwright(url)

            if video_url:
                ydl_opts_simple = {
                    'quiet': True,
                    'outtmpl': f'downloads/{chat_id}_pw.%(ext)s',
                    'merge_output_format': 'mp4',
                    'cookiefile': cookie_file,
                }
                with yt_dlp.YoutubeDL(ydl_opts_simple) as ydl:
                    ydl.download([video_url])

                files = glob.glob(f'downloads/{chat_id}_pw*')
                path = files[0] if files else None

                if path and os.path.exists(path):
                    add_download()
                    await loading_msg.edit_text(t(chat_id, 'sending'), parse_mode='Markdown')
                    with open(path, 'rb') as f:
                        caption = t(chat_id, 'success')
                        if media_type == "audio":
                            await context.bot.send_audio(chat_id, f, caption=caption, parse_mode='Markdown')
                        else:
                            await context.bot.send_video(chat_id, f, caption=caption, parse_mode='Markdown')
                    os.remove(path)
                    try: await loading_msg.delete()
                    except: pass
                else:
                    await query.message.reply_text(t(chat_id, 'error_failed'))
            else:
                await query.message.reply_text(t(chat_id, 'error_protected'))

        except Exception as e:
            try: await loading_msg.delete()
            except: pass
            await query.message.reply_text(t(chat_id, 'error', e=str(e)))

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🐂 Mini Toros Bot انطلق بنجاح!")
    app.run_polling()
