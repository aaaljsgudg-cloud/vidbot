import os
import logging
import random
import asyncio
import json
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

logging.basicConfig(level=logging.INFO)

# التوكن تجريبي
TOKEN = "8382996504:AAHs7nzULae06ASGSKWK88e7meakc9yfdNU"

# ملف لتخزين بيانات المستخدمين
DATA_FILE = "user_stats.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(USER_STATS, f)

USER_STATS = load_data()
mistakes = {}

# قاعدة بيانات الدروس
LESSONS = {
    "Beginner": [
        {"title": "Present Simple", "explanation": "We use present simple for habits.", 
         "example": "I play football every day.", "quiz": "He ___ football.", 
         "options": ["play", "plays", "playing"], "answer": "plays"}
    ],
    "Intermediate": [
        {"title": "Past Continuous", "explanation": "We use past continuous for actions in progress in the past.", 
         "example": "I was reading when he called.", "quiz": "They ___ TV at 8pm.", 
         "options": ["watch", "were watching", "watched"], "answer": "were watching"}
    ],
    "Advanced": [
        {"title": "Conditional Sentences", "explanation": "If + Present Simple → Future Simple.", 
         "example": "If it rains, I will stay home.", "quiz": "If he ___ hard, he will succeed.", 
         "options": ["study", "studies", "studied"], "answer": "studies"},
        {"title": "Passive Voice", "explanation": "Object + be + past participle.", 
         "example": "The cake was eaten by John.", "quiz": "The book ___ by the teacher.", 
         "options": ["was explained", "explained", "is explain"], "answer": "was explained"}
    ],
    "Expert": [
        {"title": "Reported Speech", "explanation": "We change tense when reporting speech.", 
         "example": "He said he was tired.", "quiz": "She said she ___ happy.", 
         "options": ["is", "was", "were"], "answer": "was"},
        {"title": "Mixed Conditionals", "explanation": "If + Past Perfect → Would + Present.", 
         "example": "If I had studied, I would be successful.", "quiz": "If he had worked, he ___ rich.", 
         "options": ["would be", "was", "is"], "answer": "would be"}
    ],
    "Master": [
        {"title": "Causative Form", "explanation": "Have/Get something done.", 
         "example": "I had my car washed.", "quiz": "He ___ his hair cut.", 
         "options": ["had", "has", "having"], "answer": "had"}
    ]
}

BADGES = {
    100: "🥉 Bronze",
    200: "🥈 Silver",
    300: "🥇 Gold",
    400: "👑 Master"
}

# --- دالة النطق الصوتي ---
async def send_voice_note(chat_id, text, context):
    try:
        tts = gTTS(text=text, lang='en', slow=False)
        filename = f"voice_{chat_id}.mp3"
        tts.save(filename)
        with open(filename, 'rb') as audio:
            await context.bot.send_voice(chat_id=chat_id, voice=audio, caption=f"🎧 Pronunciation: {text}")
        os.remove(filename)
    except Exception as e:
        logging.error(f"TTS Error: {e}")

# --- رسالة الترحيب /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    USER_STATS.setdefault(chat_id, {"lessons_done": 0, "correct": 0, "wrong": 0, "xp": 0, "level": "Beginner", "badge": ""})
    save_data()
    text = "🎓 Welcome to English Academy!\n🚀 نظام جبار لتعلم الإنجليزية.\n\nاختر المستوى:"
    keyboard = [
        [InlineKeyboardButton("🔰 Beginner", callback_data="level_Beginner")],
        [InlineKeyboardButton("⚡ Intermediate", callback_data="level_Intermediate")],
        [InlineKeyboardButton("🏆 Advanced", callback_data="level_Advanced")],
        [InlineKeyboardButton("👑 Expert", callback_data="level_Expert")],
        [InlineKeyboardButton("🌌 Master", callback_data="level_Master")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="stats")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- اختيار درس ---
async def choose_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    level = query.data.split("_")[1]
    lesson = random.choice(LESSONS[level])
    context.user_data['lesson'] = lesson
    response = f"📘 Lesson: *{lesson['title']}*\n\n{lesson['explanation']}\n💡 Example: {lesson['example']}"
    keyboard = [[InlineKeyboardButton("📝 Quiz", callback_data="quiz")]]
    await query.edit_message_text(response, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# --- اختبار ---
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lesson = context.user_data['lesson']
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans_{opt}")] for opt in lesson['options']]
    await query.edit_message_text(f"🎯 Quiz:\n{lesson['quiz']}", reply_markup=InlineKeyboardMarkup(keyboard))

# --- معالجة الإجابة ---
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    user_answer = query.data.replace("ans_", "")
    lesson = context.user_data['lesson']
    if user_answer == lesson['answer']:
        USER_STATS[chat_id]["correct"] += 1
        USER_STATS[chat_id]["xp"] += 10
        result = f"✅ Correct! +10 XP\n💡 Example: {lesson['example']}"
    else:
        USER_STATS[chat_id]["wrong"] += 1
        result = f"❌ Wrong. Correct answer: {lesson['answer']}\n💡 Example: {lesson['example']}"
        if chat_id not in mistakes:
            mistakes[chat_id] = []
        mistakes[chat_id].append((lesson['title'], lesson['answer']))

    USER_STATS[chat_id]["lessons_done"] += 1

    # ترقية المستوى حسب XP + Badges
    xp = USER_STATS[chat_id]["xp"]
    for threshold, badge in BADGES.items():
        if xp >= threshold:
            USER_STATS[chat_id]["badge"] = badge

    if xp >= 100 and USER_STATS[chat_id]["level"] == "Beginner":
        USER_STATS[chat_id]["level"] = "Intermediate"
        result += "\n🎉 Congratulations! You are now Intermediate!"
    elif xp >= 200 and USER_STATS[chat_id]["level"] == "Intermediate":
        USER_STATS[chat_id]["level"] = "Advanced"
        result += "\n🚀 Amazing! You are now Advanced!"
    elif xp >= 400 and USER_STATS[chat_id]["level"] == "Advanced":
        USER_STATS[chat_id]["level"] = "Expert"
        result += "\n👑 Incredible! You are now Expert!"
    elif xp >= 600 and USER_STATS[chat_id]["level"] == "Expert":
        USER_STATS[chat_id]["level"] = "Master"
        result += "\n🌌 Legendary! You are now Master!"

    save_data()
    keyboard = [[InlineKeyboardButton("🔰 Back to Levels", callback_data="back")]]
    await query.edit_message_text(result, reply_markup=InlineKeyboardMarkup(keyboard))

# --- إحصائيات ---
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    stats = USER_STATS.get(chat_id, {"lessons_done": 0, "correct": 0, "wrong": 0, "xp": 0, "level": "Beginner", "badge": ""})
    response = (
        f"📊 إحصائياتك:\n\n"
        f"📘 دروس منجزة: {stats['lessons_done']}\n"
        f"✅ صحيحة: {stats['correct']}\n"
        f"❌ خاطئة: {stats['wrong']}\n"
        f"⭐ XP: {stats['xp']}\n"
        f"🏆 المستوى الحالي: {stats['level']}\n"
        f"🎖 Badge: {stats['badge']}"
    )
    await query.edit_message_text(response)

# --- العودة للمستويات ---
async def back_to_levels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

# --- callback handler ---
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("level_"):
        await choose_lesson(update, context)
    elif data == "quiz":
        await start_quiz(update, context)
    elif data.startswith("ans_"):
        await handle_answer(update, context)
    elif data == "stats":
        await show_stats(update, context)
    elif data == "back":
        await back_to_levels(update, context)

# --- استقبال الرسائل العادية ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    await send_voice_note(chat_id, text, context)

# --- تشغيل البوت ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 English Academy Bot is running!")
    app.run_polling()
