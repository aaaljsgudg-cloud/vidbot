import os
import yt_dlp
import logging
import subprocess
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# تحديث yt-dlp تلقائياً عند تشغيل السيرفر
try:
    subprocess.run(["pip", "install", "-U", "yt_dlp"], check=True)
except Exception as e:
    print(f"Update failed: {e}")

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = os.getenv("TOKEN")
user_links = {}

# --- دالة الأنيميشن ---
async def loading_animation(message):
    frames = ["⏳ جاري التحميل.", "⏳ جاري التحميل..", "⏳ جاري التحميل...", "🚀 جاري المعالجة..."]
    i = 0
    while True:
        try:
            await message.edit_text(frames[i % len(frames)])
            i += 1
            await asyncio.sleep(1)
        except:
            break

# --- استقبال الرسائل ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if not url.startswith("http"):
        return

    user_links[update.message.chat_id] = url
    keyboard = [
        [InlineKeyboardButton("🎥 فيديو", callback_data="type_video"),
         InlineKeyboardButton("🎵 أغنية فقط", callback_data="type_audio")]
    ]
    await update.message.reply_text("أهلاً يا مانيجر، اختر نوع التحميل:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- اختيار الجودة ---
async def choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[1]

    if choice == "audio":
        await download_logic(update, context, "audio", "best")
    else:
        keyboard = [
            [InlineKeyboardButton("🔥 أفضل جودة", callback_data="down_video_best")],
            [InlineKeyboardButton("📺 1080p", callback_data="down_video_1080")],
            [InlineKeyboardButton("📱 720p", callback_data="down_video_720")]
        ]
        await query.edit_message_text("اختر الجودة المطلوبة للفيديو:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- التحميل وفصل البيانات ---
async def download_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, manual_type=None, manual_quality=None):
    query = update.callback_query
    chat_id = query.message.chat_id
    
    # تحديد النوع والجودة
    if manual_type:
        media_type, quality = manual_type, manual_quality
    else:
        data = query.data.split("_")
        media_type, quality = data[1], data[2]

    url = user_links.get(chat_id)

    # إرسال رسالة تحميل متحركة
    loading_msg = await query.edit_message_text("⏳ جاري التحميل...")
    task = asyncio.create_task(loading_animation(loading_msg))

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'downloads/{chat_id}_%(id)s.%(ext)s',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'retries': 3
    }

    if media_type == "audio":
        ydl_opts['format'] = 'bestaudio/best'
    else:
        height = "1080" if quality == "1080" else ("720" if quality == "720" else "2160")
        ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # --- ميزة تيك توك الصور ---
            if 'tiktok' in url and ('entries' in info or info.get('formats') is None or not info.get('url')):
                await loading_msg.edit_text("📸 اكتشفت ألبوم صور تيك توك.. جاري المعالجة...")
                entries = info.get('entries', [info])
                images = [item['url'] for item in entries if 'url' in item]
                
                if images:
                    media = [InputMediaPhoto(img) for img in images[:10]]
                    await context.bot.send_media_group(chat_id, media)
                
                audio_url = info.get('url') or (entries[0].get('url') if entries else None)
                if audio_url:
                    await context.bot.send_audio(chat_id, audio_url, caption="🎵 الأغنية الأصلية (تيك توك)")
                
                task.cancel()
                await loading_msg.delete()
                return

            # --- التحميل العادي ---
            await loading_msg.edit_text("🚀 جاري التحميل من السيرفر...")
            info_full = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info_full)
            
            task.cancel()
            try: await loading_msg.delete()
            except: pass

            if os.path.exists(path):
                with open(path, 'rb') as f:
                    if media_type == "audio":
                        await context.bot.send_audio(chat_id, f, caption="تم تحميل الأغنية بنجاح ✅")
                    else:
                        await context.bot.send_video(chat_id, f, caption="تم تحميل الفيديو بنجاح ✅")
                os.remove(path)
            else:
                await query.message.reply_text("❌ لم يتم العثور على الملف بعد التحميل.")

    except Exception as e:
        task.cancel()
        try: await loading_msg.delete()
        except: pass
        logging.error(f"Error: {e}")
        await query.message.reply_text(f"❌ عذراً مانيجر، صار خطأ بالسيستم: {str(e)}")

# --- تشغيل البوت ---
if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(choose_quality, pattern="^type_"))
    app.add_handler(CallbackQueryHandler(download_logic, pattern="^down_"))
    
    print("🚀 الوحش Monster+ شغال على Railway...")
    app.run_polling()
