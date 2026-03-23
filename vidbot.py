import os
import re
import yt_dlp
import requests
import asyncio
import subprocess
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

# 👑 قراءة التوكن من متغير البيئة
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ متغير البيئة BOT_TOKEN غير موجود! ضع التوكن قبل التشغيل.")

MAX_SIZE = 50 * 1024 * 1024  # 50MB
queue = asyncio.Queue()  # Queue ذكي لإدارة أكثر من مستخدم
history = {}  # مكتبة لكل مستخدم

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:60]

def upload_file(filepath):
    with open(filepath, 'rb') as f:
        response = requests.put(f'https://transfer.sh/{os.path.basename(filepath)}', data=f)
    return response.text.strip()

def compress_video(filepath):
    compressed = filepath.replace(".mp4", "_compressed.mp4")
    cmd = ["ffmpeg", "-i", filepath, "-vcodec", "libx264", "-crf", "28", "-preset", "fast", compressed]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return compressed if os.path.exists(compressed) else filepath

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    history[user_id] = history.get(user_id, [])
    await update.message.reply_text(
        "🚀 VidFetch 9.0 – النسخة الوحشية\n\n"
        "أرسل رابط فيديو أو قائمة روابط (Bulk) وسيتم تحميلها بدقة مطلقة 😏"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = update.message.text.strip().splitlines()
    valid_urls = [u for u in urls if u.startswith("http")]
    if not valid_urls:
        await update.message.reply_text("❌ أرسل رابط صحيح واحد على الأقل")
        return
    context.user_data["urls"] = valid_urls
    keyboard = [[
        InlineKeyboardButton("🎬 فيديو", callback_data="video"),
        InlineKeyboardButton("🎵 صوت فقط", callback_data="audio")
    ]]
    await update.message.reply_text("اختر نوع التحميل لكل رابط:", reply_markup=InlineKeyboardMarkup(keyboard))

async def process_download(url, choice, message, user_id):
    loading_msg = await message.reply_text(f"⏳ جاري التحميل: {url}")
    try:
        ydl_opts = {"outtmpl": "/tmp/%(title)s.%(ext)s", "quiet": True, "noplaylist": True}
        ydl_opts["format"] = "bestvideo+bestaudio/best" if choice=="video" else "bestaudio/best"

        for attempt in range(3):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    title = clean_filename(info.get("title", "file"))
                    ext = info.get("ext", "mp4" if choice=="video" else "m4a")
                break
            except Exception as e:
                if attempt < 2:
                    await loading_msg.edit_text(f"⚡ خطأ، إعادة المحاولة {attempt+2} لـ {url}")
                    continue
                else:
                    raise e

        filesize = os.path.getsize(filename)
        if filesize > MAX_SIZE and choice == "video":
            await loading_msg.edit_text(f"📦 ضغط الفيديو الكبير: {title}")
            filename = compress_video(filename)
            filesize = os.path.getsize(filename)

        if filesize <= MAX_SIZE:
            with open(filename, "rb") as f:
                if choice == "video":
                    await message.reply_video(f, caption=f"🎬 {title}")
                else:
                    await message.reply_audio(f, caption=f"🎵 {title}")
        else:
            await loading_msg.edit_text(f"📤 رفع الفيديو الكبير: {title}")
            link = upload_file(filename)
            await message.reply_text(f"✅ رابط التحميل:\n{link}")

        # حفظ في مكتبة المستخدم
        history[user_id].append({"title": title, "url": url, "type": choice, "date": datetime.now().isoformat()})

        try: await loading_msg.delete()
        except: pass
        if os.path.exists(filename): os.remove(filename)

    except Exception as e:
        error_msg = str(e)[:300]
        print(f"ERROR: {error_msg}")
        await loading_msg.edit_text(f"❌ حدث خطأ: {error_msg}")

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    urls = context.user_data.get("urls")
    context.user_data.pop("urls", None)
    user_id = query.from_user.id

    if not urls:
        await query.edit_message_text("❌ أرسل الرابط مرة أخرى")
        return

    for url in urls:
        await queue.put((url, query.data, query.message, user_id))

    while not queue.empty():
        item = await queue.get()
        await process_download(*item)
        queue.task_done()

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_choice))
    print("🚀 VidFetch 9.0 يعمل... النسخة الوحشية النهائية")
    app.run_polling()

if __name__ == "__main__":
    main()
