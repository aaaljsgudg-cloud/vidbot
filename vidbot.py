import os, json, asyncio, glob, logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, CommandHandler, ContextTypes, filters

# إعدادات التسجيل - Logging
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
user_links = {}

# دالة التحميل الأساسية - Core Download Function
def download_func(url, opts):
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"): return
    
    chat_id = update.message.chat_id
    user_links[chat_id] = url # حفظ الرابط

    keyboard = [[
        InlineKeyboardButton("🎥 Video", callback_data="down_video"),
        InlineKeyboardButton("🎵 Audio", callback_data="down_audio")
    ]]
    await update.message.reply_text("🔗 Link Received! Choose type:", reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    url = user_links.get(chat_id)
    
    if not url: return

    # إعدادات yt-dlp الذكية
    ydl_opts = {
        'outtmpl': f'downloads/{chat_id}.%(ext)s',
        'quiet': True,
    }

    if query.data == "down_audio":
        ydl_opts.update({'format': 'bestaudio', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]})
    
    await query.edit_message_text("📥 Processing... Please wait.")
    
    # تنفيذ التحميل في Thread منفصل عشان ما يعلق البوت
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, download_func, url, ydl_opts)
        
        # البحث عن الملف وإرساله
        files = glob.glob(f'downloads/{chat_id}.*')
        if files:
            await context.bot.send_document(chat_id=chat_id, document=open(files[0], 'rb'))
            os.remove(files[0])
            await query.delete_message()
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(callback_handler))
    print("🐂 Mini Toros is Alive!")
    app.run_polling()
