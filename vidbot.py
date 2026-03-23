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

# ─── Read BOT_TOKEN ───────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    try:
        with open("BOT_TOKEN", "r") as f:
            TOKEN = f.read().strip()
    except FileNotFoundError:
        raise ValueError("❌ BOT_TOKEN missing in environment or BOT_TOKEN file")

MAX_SIZE = 50 * 1024 * 1024  # 50MB

# ─── In-Memory Storage ────────────────────────────────────
db = {"users": {}, "downloads": 0}

# ─── Language helper ─────────────────────────────────────
def get_lang(update: Update) -> str:
    code = update.effective_user.language_code or ""
    if code.startswith("ar"): return "ar"
    if code.startswith("tr"): return "tr"
    return "en"

# ─── Translations (keep all previous T dict) ──────────────
T = { ... }  # انسخ كامل T من النسخة السابقة كما هي

def t(key: str, lang: str) -> str:
    return T.get(key, {}).get(lang, T.get(key, {}).get("en", ""))

# ─── Helpers (كما هي بدون تعديل) ───────────────────────
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

# ─── Chat analyzer (كما هي) ─────────────────────────────
def analyze_chat(path: str, lang: str) -> str:
    ...  # انسخ الدالة كما هي

# ─── Command Handlers (كما هي) ─────────────────────────
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
    ...  # انسخ الدالة كما هي

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...  # انسخ الدالة كما هي

async def do_download(url: str, choice: str, message, user_id: str, lang: str):
    ...  # انسخ الدالة كما هي

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...  # انسخ الدالة كما هي

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ...  # انسخ الدالة كما هي

# ─── Main ────────────────────────────────────────────────
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

if __name__ == "__main__":
    main()
