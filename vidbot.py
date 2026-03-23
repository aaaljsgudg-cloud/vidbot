import os
import re
import json
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

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN missing")

MAX_SIZE = 50 * 1024 * 1024
DATA_FILE = "db.json"

# تحميل البيانات إذا موجودة
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
else:
    db = {"users": {}, "downloads": 0}

def save_db():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_lang(update: Update) -> str:
    user = update.effective_user
    code = user.language_code or ""
    if code.startswith("ar"): return "ar"
    if code.startswith("tr"): return "tr"
    return "en"

T = {
    "choose": {"ar": "🎯 اختر نوع التحميل:", "en": "🎯 Choose download type:", "tr": "🎯 İndirme türünü seçin:"},
    "downloading": {"ar": "⏳ جاري التحميل... انتظر قليلاً يا مدير", "en": "⏳ Downloading... please wait", "tr": "⏳ İndiriliyor... lütfen bekleyin"},
    "uploading": {"ar": "📤 الملف كبير، جاري الرفع للسحاب...", "en": "📤 File too large, uploading...", "tr": "📤 Dosya büyük, yükleniyor..."},
    "invalid": {"ar": "❌ أرسل رابط صحيح أو ملف .txt/.zip", "en": "❌ Send a valid link or .txt/.zip file", "tr": "❌ Geçerli bir link veya .txt/.zip gönderin"},
    "analyzing": {"ar": "🔍 جاري تحليل ملف الواتساب...", "en": "🔍 Analyzing WhatsApp file...", "tr": "🔍 WhatsApp dosyası analiz ediliyor..."}
}

def t(key: str, lang: str) -> str:
    return T.get(key, {}).get(lang, T.get(key, {}).get("en", ""))

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:60]

def ensure_user(user_id: str):
    if user_id not in db["users"]:
        db["users"][user_id] = {"history": []}
        save_db()

def save_history(user_id: str, title: str):
    ensure_user(user_id)
    db["users"][user_id]["history"].append(title)
    if len(db["users"][user_id]["history"]) > 50:
        db["users"][user_id]["history"].pop(0)
    db["downloads"] += 1
    save_db()

def analyze_chat(path: str, lang: str) -> str:
    total = 0
    users = {}
    for enc in ['utf-8', 'utf-16', 'cp1252', 'latin-1']:
        try:
            with open(path, "r", encoding=enc) as f:
                lines = f.readlines()
            break
        except: continue
    else: return "❌ Error reading file encoding"

    for line in lines:
        line = line.strip()
        if not line: continue
        match = re.search(r'] (.+?):', line) or (re.search(r'-(.+?):', line))
        if match:
            name = match.group(1).strip()
            users[name] = users.get(name, 0) + 1
            total += 1

    if not users: return "❌ No messages found"
    top_user = max(users, key=users.get)
    top5 = sorted(users.items(), key=lambda x: x[1], reverse=True)[:5]
    top5_text = "\n".join([f"  {i+1}. {n}: {c}" for i, (n, c) in enumerate(top5)])

    if lang == "ar":
        return f"📊 *تحليل الدردشة*\n\n📨 الإجمالي: `{total}`\n🏆 الأنشط: *{top_user}*\n\n🔝 *أعلى 5:*\n{top5_text}"
    return f"📊 *Analysis*\n\n📨 Total: `{total}`\n🏆 Most Active: *{top_user}*\n\n🔝 *Top 5:*\n{top5_text}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    user_id = str(update.effective_user.id)
    ensure_user(user_id)
    msgs = {
        "ar": "👋 أهلاً بك يا مدير علي في *AIO 10.0*\n\n🚀 أرسل رابط فيديو للتحميل أو ملف واتساب للتحليل!",
        "en": "👋 Welcome to *AIO 10.0*\n\n🚀 Send a video link to download or a WhatsApp file to analyze!",
        "tr": "👋 *AIO 10.0*'a hoş geldiniz\n\n🚀 İndirmek için bir video linki veya analiz için bir WhatsApp dosyası gönderin!"
    }
    await update.message.reply_text(msgs.get(lang, msgs["en"]), parse_mode="Markdown")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    total_users = len(db["users"])
    total_downloads = db["downloads"]
    if lang == "ar":
        msg = f"📈 *إحصائيات AIO 10.0*\n\n👤 المستخدمين: `{total_users}`\n📥 التحميلات: `{total_downloads}`"
    elif lang == "tr":
        msg = f"📈 *AIO 10.0 İstatistikleri*\n\n👤 Kullanıcılar: `{total_users}`\n📥 İndirmeler: `{total_downloads}`"
    else:
        msg = f"📈 *AIO 10.0 Stats*\n\n👤 Users: `{total_users}`\n📥 Downloads: `{total_downloads}`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    user_id = str(update.effective_user.id)
    ensure_user(user_id)
    hist = db["users"][user_id]["history"]
    if not hist:
        await update.message.reply_text("📭 سجل التحميلات فارغ")
        return
    last10 = hist[-10:][::-1]
    lines = "\n".join([f"{i+1}. {title}" for i, title in enumerate(last10)])
    await update.message.reply_text(f"📋 *آخر 10 تحميلات:*\n\n{lines}", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    text = update.message.text.strip()
    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[InlineKeyboardButton("🎬 Video", callback_data="video"), 
                     InlineKeyboardButton("🎵 Audio", callback_data="audio")]]
        await update.message.reply_text(t("choose", lang), reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(t("invalid", lang))

async def do_download(url: str, choice: str, message, user_id: str, lang: str):
    status = await message.reply_text(t("downloading", lang))
    filename = None
    try:
        ydl_opts = {"outtmpl": f"{tempfile.gettempdir()}/%(title)s.%(ext)s", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = clean_filename(info.get("title", "file"))

        with open(filename, "rb") as f:
            if choice == "video": await message.reply_video(f, caption=title)
            else: await message.reply_audio(f, caption=title)

        save_history(user_id, title)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"❌ Error: {str(e)[:50]}")
    finally:
        if filename and os.path.exists(filename): os.remove(filename)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    url = context.user_data.get("url")
    if not url: 
        await query.message.reply_text("❌ لم يتم العثور على رابط")
        return
    context.user_data.pop("url", None)
    await do_download(url, query.data, query.message, str(query.from_user.id), lang)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    doc = update.message.document
    status = await update.message.reply_text(t("analyzing", lang))
    file = await doc.get_file()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, doc.file_name)
        await file.download_to_drive(path)
        await update.message.reply_text(analyze_chat(path, lang), parse_mode="Markdown")
        await status.delete()

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_choice))
    print("🚀 AIO 10.0 Running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
