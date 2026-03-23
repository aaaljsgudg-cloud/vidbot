import os
import re
import yt_dlp
import requests
import zipfile
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

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

T = {
    "start": {
        "ar": (
            "👋 أهلاً بك في *AIO 10.0*\n\n"
            "🤖 *ما يقدر يسويه البوت:*\n\n"
            "1️⃣ *تحميل فيديوهات* من:\n"
            "   • يوتيوب، تيك توك، انستغرام، فيسبوك\n"
            "   • أرسل الرابط واختر 🎬 فيديو أو 🎵 صوت\n\n"
            "2️⃣ *تحليل دردشات واتساب:*\n"
            "   • أرسل ملف .txt أو .zip\n"
            "   • سيعطيك عدد الرسائل وأكثر شخص كلام\n\n"
            "3️⃣ *الأوامر المتاحة:*\n"
            "   /help – المساعدة\n"
            "   /history – آخر 10 تحميلات\n"
            "   /stats – إحصائيات عامة\n\n"
            "🚀 ابدأ الآن بإرسال رابط أو ملف!"
        ),
        "en": (
            "👋 Welcome to *AIO 10.0*\n\n"
            "🤖 *What this bot can do:*\n\n"
            "1️⃣ *Download videos* from:\n"
            "   • YouTube, TikTok, Instagram, Facebook\n"
            "   • Send a link and choose 🎬 Video or 🎵 Audio\n\n"
            "2️⃣ *Analyze WhatsApp chats:*\n"
            "   • Send a .txt or .zip file\n"
            "   • Get message count and most active person\n\n"
            "3️⃣ *Available commands:*\n"
            "   /help – Help\n"
            "   /history – Last 10 downloads\n"
            "   /stats – Global stats\n\n"
            "🚀 Start now by sending a link or file!"
        ),
        "tr": (
            "👋 *AIO 10.0*'a hoş geldiniz\n\n"
            "🤖 *Bot neler yapabilir:*\n\n"
            "1️⃣ *Video indir:*\n"
            "   • YouTube, TikTok, Instagram, Facebook\n"
            "   • Link gönderin ve 🎬 Video veya 🎵 Ses seçin\n\n"
            "2️⃣ *WhatsApp sohbeti analiz et:*\n"
            "   • .txt veya .zip dosyası gönderin\n"
            "   • Mesaj sayısı ve en aktif kişiyi öğrenin\n\n"
            "3️⃣ *Mevcut komutlar:*\n"
            "   /help – Yardım\n"
            "   /history – Son 10 indirme\n"
            "   /stats – Genel istatistikler\n\n"
            "🚀 Şimdi bir link veya dosya göndererek başlayın!"
        ),
    },
    "help": {
        "ar": "📜 *الأوامر المتاحة:*\n/start – البداية\n/help – المساعدة\n/stats – إحصائيات عامة\n/history – آخر 10 تحميلات\n\n🔗 أرسل رابط من يوتيوب، تيك توك، انستغرام، فيسبوك\n📁 أو أرسل ملف .txt أو .zip لتحليل دردشة واتساب",
        "en": "📜 *Available Commands:*\n/start – Start\n/help – Help\n/stats – Global stats\n/history – Last 10 downloads\n\n🔗 Send a link from YouTube, TikTok, Instagram, Facebook\n📁 Or send a .txt/.zip to analyze a WhatsApp chat",
        "tr": "📜 *Mevcut Komutlar:*\n/start – Başlat\n/help – Yardım\n/stats – Genel istatistikler\n/history – Son 10 indirme\n\n🔗 YouTube, TikTok, Instagram, Facebook linki gönderin\n📁 WhatsApp sohbetini analiz etmek için .txt/.zip gönderin"
    },
    "choose": {
        "ar": "🎯 اختر نوع التحميل:",
        "en": "🎯 Choose download type:",
        "tr": "🎯 İndirme türünü seçin:"
    },
    "downloading": {
        "ar": "⏳ جاري التحميل...",
        "en": "⏳ Downloading...",
        "tr": "⏳ İndiriliyor..."
    },
    "uploading": {
        "ar": "📤 الملف كبير، جاري الرفع...",
        "en": "📤 File too large, uploading...",
        "tr": "📤 Dosya büyük, yükleniyor..."
    },
    "done": {
        "ar": "✅ تم التحميل!",
        "en": "✅ Downloaded!",
        "tr": "✅ İndirildi!"
    },
    "invalid": {
        "ar": "❌ أرسل رابط صحيح أو ملف .txt/.zip",
        "en": "❌ Send a valid link or .txt/.zip file",
        "tr": "❌ Geçerli bir link veya .txt/.zip dosyası gönderin"
    },
    "no_url": {
        "ar": "❌ أرسل الرابط مرة أخرى",
        "en": "❌ Please send the link again",
        "tr": "❌ Lütfen linki tekrar gönderin"
    },
    "empty_history": {
        "ar": "📭 سجلك فارغ",
        "en": "📭 Your history is empty",
        "tr": "📭 Geçmişiniz boş"
    },
    "analyzing": {
        "ar": "🔍 جاري تحليل الملف...",
        "en": "🔍 Analyzing file...",
        "tr": "🔍 Dosya analiz ediliyor..."
    },
    "no_txt": {
        "ar": "❌ لم يتم العثور على ملف .txt في الـ ZIP",
        "en": "❌ No .txt file found in ZIP",
        "tr": "❌ ZIP içinde .txt dosyası bulunamadı"
    }
}

def t(key: str, lang: str) -> str:
    return T.get(key, {}).get(lang, T.get(key, {}).get("en", ""))

def clean_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:60]

def upload_file(filepath: str) -> str:
    with open(filepath, 'rb') as f:
        res = requests.post('https://0x0.st', files={'file': f}, timeout=60)
    return res.text.strip()

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
                if not line:
                    continue
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
        return f"Error reading file: {e}"

    if not users:
        return "❌ No messages found" if lang == "en" else "❌ لم يتم العثور على رسائل" if lang == "ar" else "❌ Mesaj bulunamadı"

    top_user = max(users, key=users.get)
    top_count = users[top_user]
    unique = len(users)
    top5 = sorted(users.items(), key=lambda x: x[1], reverse=True)[:5]
    top5_text = "\n".join([f"  {i+1}. {n}: {c}" for i, (n, c) in enumerate(top5)])

    if lang == "ar":
        return (f"📊 *تحليل الدردشة*\n\n"
                f"📨 إجمالي الرسائل: `{total}`\n"
                f"👥 عدد المشاركين: `{unique}`\n"
                f"🏆 الأكثر نشاطاً: *{top_user}* ({top_count} رسالة)\n\n"
                f"🔝 *أكثر 5 مشاركين:*\n{top5_text}")
    elif lang == "tr":
        return (f"📊 *Sohbet Analizi*\n\n"
                f"📨 Toplam mesaj: `{total}`\n"
                f"👥 Katılımcı sayısı: `{unique}`\n"
                f"🏆 En aktif: *{top_user}* ({top_count} mesaj)\n\n"
                f"🔝 *En aktif 5 kişi:*\n{top5_text}")
    else:
        return (f"📊 *Chat Analysis*\n\n"
                f"📨 Total messages: `{total}`\n"
                f"👥 Participants: `{unique}`\n"
                f"🏆 Most active: *{top_user}* ({top_count} messages)\n\n"
                f"🔝 *Top 5 participants:*\n{top5_text}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    ensure_user(str(update.effective_user.id))
    await update.message.reply_text(t("start", lang), parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    await update.message.reply_text(t("help", lang), parse_mode="Markdown")

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
        await update.message.reply_text(t("empty_history", lang))
        return
    last10 = hist[-10:][::-1]
    lines = "\n".join([f"{i+1}. {title}" for i, title in enumerate(last10)])
    if lang == "ar":
        header = "📋 *آخر 10 تحميلات:*\n\n"
    elif lang == "tr":
        header = "📋 *Son 10 indirme:*\n\n"
    else:
        header = "📋 *Last 10 downloads:*\n\n"
    await update.message.reply_text(header + lines, parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    text = update.message.text.strip()
    if text.startswith("http"):
        context.user_data["url"] = text
        keyboard = [[
            InlineKeyboardButton("🎬 Video", callback_data="video"),
            InlineKeyboardButton("🎵 Audio", callback_data="audio"),
        ]]
        await update.message.reply_text(
            t("choose", lang),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(t("invalid", lang))

async def do_download(url: str, choice: str, message, user_id: str, lang: str):
    status = await message.reply_text(t("downloading", lang))
    filename = None
    try:
        ydl_opts = {
            "outtmpl": "/tmp/%(title)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "format": "bestvideo+bestaudio/best" if choice == "video" else "bestaudio/best",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            title = clean_filename(info.get("title", "file"))

        size = os.path.getsize(filename)

        if size <= MAX_SIZE:
            with open(filename, "rb") as f:
                if choice == "video":
                    await message.reply_video(f, caption=f"🎬 {title}")
                else:
                    await message.reply_audio(f, caption=f"🎵 {title}")
        else:
            await status.edit_text(t("uploading", lang))
            link = upload_file(filename)
            await message.reply_text(f"🔗 {title}\n{link}")

        save_history(user_id, title)

        try:
            await status.delete()
        except:
            pass

    except Exception as e:
        err = str(e)[:200]
        try:
            await status.edit_text(f"❌ {err}")
        except:
            await message.reply_text(f"❌ {err}")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = get_lang(update)
    user_id = str(query.from_user.id)
    url = context.user_data.get("url")
    if not url:
        await query.message.reply_text(t("no_url", lang))
        return
    context.user_data.pop("url", None)
    await do_download(url, query.data, query.message, user_id, lang)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update)
    doc = update.message.document
    fname = doc.file_name.lower()

    if not (fname.endswith(".txt") or fname.endswith(".zip")):
        await update.message.reply_text(t("invalid", lang))
        return

    status = await update.message.reply_text(t("analyzing", lang))
    file = await doc.get_file()

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, doc.file_name)
        await file.download_to_drive(path)

        results = []

        if fname.endswith(".zip"):
            try:
                with zipfile.ZipFile(path) as z:
                    z.extractall(tmp)
                txt_files = [f for f in os.listdir(tmp) if f.endswith(".txt")]
                if not txt_files:
                    await status.edit_text(t("no_txt", lang))
                    return
                for tf in txt_files:
                    res = analyze_chat(os.path.join(tmp, tf), lang)
                    results.append(f"📄 *{tf}*\n{res}")
            except zipfile.BadZipFile:
                await status.edit_text("❌ Invalid ZIP file")
                return
        else:
            res = analyze_chat(path, lang)
            results.append(res)

        try:
            await status.delete()
        except:
            pass

        for result in results:
            await update.message.reply_text(result, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_choice))
    print("🚀 AIO 10.0 Running...")
    app.run_polling(drop_pending_updates=True)
