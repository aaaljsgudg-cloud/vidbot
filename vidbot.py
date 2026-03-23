import os
import re
import yt_dlp
import requests
import zipfile
import tempfile
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# إعداد السجلات لمراقبة ريلواي
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN missing")

MAX_SIZE = 50 * 1024 * 1024

db = {
    "users": {},
    "downloads": 0
}

def get_lang(update: Update) -> str:
    code = update.effective_user.language_code or ""
    if code.startswith("ar"): return "ar"
    if code.startswith("tr"): return "tr"
    return "en"

# قاموس اللغات المحدث لضمان ظهور النصوص كاملة
T = {
    "choose": {"ar": "🎯 اختر نوع التحميل:", "en": "🎯 Choose download type:", "tr": "🎯 İndirme türünü seçin:"},
    "downloading": {"ar": "⏳ جاري التحميل...", "en": "⏳ Downloading...", "tr": "⏳ İndiriliyor..."},
    "uploading": {"ar": "📤 الملف كبير، جاري الرفع...", "en": "📤 File too large, uploading...", "tr": "📤 Dosya büyük, yükleniyor..."},
    "done": {"ar": "✅ تم التحميل!", "en": "✅ Downloaded!", "tr": "✅ İndirildi!"},
    "invalid": {"ar": "❌ أرسل رابط صحيح أو ملف .txt/.zip", "en": "❌ Send a valid link or .txt/.zip file", "tr": "❌ Geçerli bir link أو .txt/.zip gönderin"},
    "no_url": {"ar": "❌ أرسل الرابط مرة أخرى", "en": "❌ Please send the link again", "tr": "❌ Lütfen linki tekrar gönderin"},
    "empty_history": {"ar": "📭 سجلك فارغ", "en": "📭 Your history is empty", "tr": "📭 Geçmişiniz boş"},
    "analyzing": {"ar": "🔍 جاري تحليل الملف...", "en": "🔍 Analyzing file...", "tr": "🔍 Dosya analiz ediliyor..."},
    "no_txt": {"ar": "❌ لم يتم العثور على ملف .txt في الـ ZIP", "en": "❌ No .txt file found in ZIP", "tr": "❌ ZIP içinde .txt dosyası bulunamadı"}
}

def t(key: str, lang: str) -> str:
    return T.get(key, {}).get(lang, T.get(key, {}).get("en", ""))

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:60]

def upload_file(filepath: str) -> str:
    try:
        with open(filepath, 'rb') as f:
            res = requests.post('https://0x0.st', files={'file': f}, timeout=60)
        return res.text.strip()
    except:
        return "❌ Upload Error"

def ensure_user(user_id: str):
    if user_id not in db["users"]:
        db["users"][user_id] = {"history": []}

def save_history(user_id: str, title: str):
    ensure_user(user_id)
    db["users"][user_id]["history"].append(title)
    if len(db["users"][user_id]["history"]) > 50:
        db["users"][user_id]["history"].pop(0)
    db["downloads"] += 1

def analyze_chat(path: str, lang: str) -> str:
    total = 0
    users = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                match = re.search(r'] (.+?):', line)
                if match:
                    name = match.group(1).strip()
                    users[name] = users.get(name, 0) + 1
                    total += 1
                elif ":" in line:
                    name = line.split(":")[0].strip()
                    users[name] = users.get(name, 0) + 1
                    total += 1
    except Exception as e:
        return f"Error: {e}"

    if not users: return "❌ No messages"
    top_user = max(users, key=users.get)
    top_count = users[top_user]
    top5 = sorted(users.items(), key=lambda x: x[1], reverse=True)[:5]
    top5_text = "\n".join([f"  {i+1}. {n}: {c}" for i, (n, c) in enumerate(top5)])

    return f"📊 *Analysis*\n\n📨 Total: `{total}`\n🏆 Top: *{top_user}*\n\n🔝 *Top 5:*\n{top5_text}"

# دالة start محسنة لضمان عرض النص الترحيبي الكامل
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    ensure_user(str(update.effective_user.id))
    
    messages = {
        "ar": (
            "👋 أهلاً بك في *AIO 10.0*\n\n"
            "🤖 *وظائف البوت:*\n"
            "1️⃣ *تحميل فيديوهات* (يوتيوب، تيك توك، إلخ)\n"
            "2️⃣ *تحليل واتساب* (أرسل ملف .txt)\n\n"
            "🚀 ابدأ الآن بإرسال رابط أو ملف!"
        ),
        "en": (
            "👋 Welcome to *AIO 10.0*\n\n"
            "1️⃣ *Download videos* (YT, TikTok, etc)\n"
            "2️⃣ *Analyze WhatsApp* (Send .txt file)\n\n"
            "🚀 Send a link or file to start!"
        ),
        "tr": (
            "👋 *AIO 10.0*'a hoş geldiniz\n\n"
            "1️⃣ *Video indir* (YT, TikTok, vb.)\n"
            "2️⃣ *WhatsApp analizi* (.txt dosyası gönder)\n\n"
            "🚀 Başlamak için bir link veya dosya gönderin!"
        )
    }
    await update.message.reply_text(messages.get(lang, messages["en"]), parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    msg = "📜 /start - /stats - /history"
    await update.message.reply_text(msg)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"📈 Stats:\n👤 Users: {len(db['users'])}\n📥 Downloads: {db['downloads']}"
    await update.message.reply_text(msg)

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    hist = db["users"].get(user_id, {}).get("history", [])
    if not hist:
        await update.message.reply_text("📭 Empty")
        return
    await update.message.reply_text("\n".join(hist[-10:]))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton("🎬 Video", callback_data="video"), 
                     InlineKeyboardButton("🎵 Audio", callback_data="audio")]]
        await update.message.reply_text("🎯 Choice:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("❌ Send link or file")

async def do_download(url: str, choice: str, message, user_id: str, lang: str):
    status = await message.reply_text("⏳ ...")
    filename = None
    try:
        ydl_opts = {
            "outtmpl": f"{tempfile.gettempdir()}/%(title)s.%(ext)s",
            "quiet": True,
            "format": "bestvideo+bestaudio/best" if choice == "video" else "bestaudio/best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = clean_filename(info.get("title", "file"))

        if os.path.getsize(filename) <= MAX_SIZE:
            with open(filename, "rb") as f:
                if choice == "video": await message.reply_video(f, caption=title)
                else: await message.reply_audio(f, caption=title)
        else:
            await message.reply_text(f"🔗 {upload_file(filename)}")
        
        save_history(user_id, title)
        await status.delete()
    except Exception as e:
        await message.reply_text(f"❌ {str(e)[:50]}")
    finally:
        if filename and os.path.exists(filename): os.remove(filename)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url = context.user_data.get("url")
    if url:
        await do_download(url, query.data, query.message, str(query.from_user.id), "en")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    status = await update.message.reply_text("🔍 Analyzing...")
    file = await doc.get_file()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, doc.file_name)
        await file.download_to_drive(path)
        await update.message.reply_text(analyze_chat(path, "ar"), parse_mode="Markdown")
        await status.delete()

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_choice))
    app.run_polling()

if __name__ == "__main__":
    main()
