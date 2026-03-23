import os
import re
import yt_dlp
import requests
import zipfile
import tempfile
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN missing")

DATA_FILE = "data.json"

# تحميل البيانات
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {"users": {}, "downloads": 0}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_lang(update):
    lang = update.effective_user.language_code
    if lang:
        if lang.startswith("ar"):
            return "ar"
        elif lang.startswith("tr"):
            return "tr"
    return "en"

MESSAGES = {
    "start": {
        "ar": "🚀 بوت AIO\nاستخدم /help",
        "en": "🚀 AIO Bot\nUse /help",
        "tr": "🚀 AIO Bot\n/help kullan"
    },
    "help": {
        "ar": "📜 الأوامر:\n/start\n/help\n/stats\n/history",
        "en": "📜 Commands:\n/start\n/help\n/stats\n/history",
        "tr": "📜 Komutlar:\n/start\n/help\n/stats\n/history"
    },
    "choose": {
        "ar": "اختر:",
        "en": "Choose:",
        "tr": "Seç:"
    },
    "invalid": {
        "ar": "❌ أرسل رابط أو ملف صحيح",
        "en": "❌ Send valid link or file",
        "tr": "❌ Geçerli bir link veya dosya gönder"
    },
    "downloading": {
        "ar": "⏳ جاري التحميل...",
        "en": "⏳ Downloading...",
        "tr": "⏳ İndiriliyor..."
    }
}

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:60]

def upload_file(filepath):
    with open(filepath, 'rb') as f:
        res = requests.put(f'https://transfer.sh/{os.path.basename(filepath)}', data=f)
    return res.text.strip()

def analyze_chat(path, lang):
    total = 0
    users = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                total += 1
                name = line.split(":")[0]
                users[name] = users.get(name, 0) + 1

    top = max(users, key=users.get) if users else "Unknown"

    if lang == "ar":
        return f"عدد الرسائل: {total}\nالأكثر: {top}"
    elif lang == "tr":
        return f"Mesaj sayısı: {total}\nEn çok: {top}"
    else:
        return f"Messages: {total}\nTop: {top}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    user_id = str(update.effective_user.id)

    if user_id not in data["users"]:
        data["users"][user_id] = []
        save_data()

    await update.message.reply_text(MESSAGES["start"][lang])

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    await update.message.reply_text(MESSAGES["help"][lang])

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    total_users = len(data["users"])
    downloads = data["downloads"]

    if lang == "ar":
        msg = f"المستخدمين: {total_users}\nالتحميلات: {downloads}"
    elif lang == "tr":
        msg = f"Kullanıcılar: {total_users}\nİndirmeler: {downloads}"
    else:
        msg = f"Users: {total_users}\nDownloads: {downloads}"

    await update.message.reply_text(msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = get_lang(update)

    hist = data["users"].get(user_id, [])
    if not hist:
        await update.message.reply_text("فارغ" if lang=="ar" else "Empty" if lang=="en" else "Boş")
        return

    text = "\n".join(hist[-10:])
    await update.message.reply_text(text)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    text = update.message.text.strip()

    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[
            InlineKeyboardButton("🎬 Video", callback_data="video"),
            InlineKeyboardButton("🎵 Audio", callback_data="audio"),
        ]]
        await update.message.reply_text(MESSAGES["choose"][lang], reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(MESSAGES["invalid"][lang])

async def download(url, choice, message, user_id):
    lang = get_lang(message)
    msg = await message.reply_text(MESSAGES["downloading"][lang])

    try:
        ydl_opts = {
            "outtmpl": "/tmp/%(title)s.%(ext)s",
            "quiet": True,
            "format": "bestvideo+bestaudio/best" if choice=="video" else "bestaudio/best"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = clean_filename(info.get("title","file"))

        size = os.path.getsize(filename)

        if size < 50*1024*1024:
            with open(filename,"rb") as f:
                if choice=="video":
                    await message.reply_video(f)
                else:
                    await message.reply_audio(f)
        else:
            link = upload_file(filename)
            await message.reply_text(link)

        os.remove(filename)

        # حفظ البيانات
        data["downloads"] += 1
        data["users"][user_id].append(title)
        save_data()

        await msg.delete()

    except Exception as e:
        await msg.edit_text(str(e)[:200])

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    url = context.user_data.get("url")

    if not url:
        await query.message.reply_text("Send again")
        return

    await download(url, query.data, query.message, user_id)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    file = await update.message.document.get_file()

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, update.message.document.file_name)
        await file.download_to_drive(path)

        if path.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                z.extractall(tmp)
                for f in os.listdir(tmp):
                    if f.endswith(".txt"):
                        res = analyze_chat(os.path.join(tmp,f), lang)
                        await update.message.reply_text(res)
                        return
        elif path.endswith(".txt"):
            res = analyze_chat(path, lang)
            await update.message.reply_text(res)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("history", history))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_choice))

    print("AIO 10.0 Running with TR support...")
    app.run_polling()

if __name__ == "__main__":
    main()
