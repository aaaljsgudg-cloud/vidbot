import os
import re
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

TELEGRAM_TOKEN = "8247994492:AAFZ3hbN-dk508hYTAxJmGqooMdcRIMOB4Q"

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 مرحبًا بك في بوت تحميل الفيديوهات\n\n"
        "🎯 أرسل رابط من:\n"
        "• يوتيوب\n• تيك توك\n• إنستغرام\n• فيسبوك\n\n"
        "وسيتم تجهيز خيارات التحميل لك ⚡"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text("❌ الرجاء إرسال رابط صحيح")
        return

    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("🎬 تحميل فيديو", callback_data="video"),
            InlineKeyboardButton("🎵 تحميل صوت", callback_data="audio"),
        ]
    ]

    await update.message.reply_text(
        "⚙️ اختر نوع التحميل:\n🎬 فيديو كامل\n🎵 صوت فقط (أغنية)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    context.user_data.pop("url", None)

    if not url:
        await query.edit_message_text("❌ انتهت الجلسة، أرسل الرابط مرة أخرى")
        return

    loading_msg = await query.message.reply_text("⏳ جاري التحميل...")

    try:
        if query.data == "video":
            ydl_opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": "%(title)s.%(ext)s",
                "quiet": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = clean_filename(info.get("title", "video"))
                ext = info.get("ext", "mp4")

            filename = f"{title}.{ext}"

            with open(filename, "rb") as f:
                await query.message.reply_video(f, caption=f"🎬 {title}")

        elif query.data == "audio":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "%(title)s.%(ext)s",
                "quiet": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = clean_filename(info.get("title", "audio"))
                ext = info.get("ext", "m4a")

            filename = f"{title}.{ext}"

            with open(filename, "rb") as f:
                await query.message.reply_audio(f, caption=f"🎵 {title}")

        try:
            await loading_msg.delete()
            await query.message.delete()
        except:
            pass

        os.remove(filename)

    except Exception as e:
        print(f"ERROR: {e}")
        await query.message.reply_text("❌ حدث خطأ أثناء التحميل")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).read_timeout(120).write_timeout(120).connect_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(handle_choice))
    print("🚀 VidFetch Bot يعمل...")
    app.run_polling()

if __name__ == "__main__":
    main()