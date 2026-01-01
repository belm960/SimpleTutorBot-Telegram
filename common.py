# --- common.py ---
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from constants import *
from keyboards import *
from database import db, get_user
from typing import Optional

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, role: str):
    tid = update.effective_user.id
    with db() as conn:
        if role == "student":
            row = conn.execute("SELECT * FROM students WHERE telegram_id=?", (tid,)).fetchone()
            if not row:
                await update.message.reply_text("No student profile found.")
                return
            msg = (
                "👤 *Student Profile*\n"
                f"- Name: {row['full_name']}\n"
                f"- Phone: {row['phone']}\n"
                f"- City: {row['city']}\n"
                f"- Grade: {row['grade']}\n"
                f"- Subject: {row['subject_needed']}\n"
                f"- Mode: {row['mode']}\n"
                f"- Notes: {row['notes'] or '-'}"
            )
        else:
            u = conn.execute("SELECT * FROM users WHERE telegram_id=?", (tid,)).fetchone()
            row = conn.execute("SELECT * FROM tutors WHERE telegram_id=?", (tid,)).fetchone()
            if not row:
                await update.message.reply_text("No tutor profile found.")
                return
            msg = (
                "👤 *Tutor Profile*\n"
                f"- Status: {u['status']}\n"
                f"- Name: {row['full_name']}\n"
                f"- Phone: {row['phone']}\n"
                f"- City: {row['city']}\n"
                f"- Subjects: {row['subjects']}\n"
                f"- Grades: {row['grades']}\n"
                f"- Experience: {row['experience_years']} years\n"
                f"- Mode: {row['mode']}\n"
                f"- Rate: {row['hourly_rate']}\n"
                f"- Bio: {row['bio']}\n"
                f"- Test score: {row['test_score']}/{len(TUTOR_TEST)}"
            )
    await update.message.reply_text(msg, parse_mode="Markdown")
    
def get_phone_from_db(update, role: str) -> Optional[str]:
    telegram_id = update.effective_user.id
    with db() as conn:
        if role == "student":
            row = conn.execute("SELECT * FROM students WHERE telegram_id=?", (telegram_id,)).fetchone()
            if row:
                return row["phone"]
        else:
            row = conn.execute("SELECT * FROM tutors WHERE telegram_id=?", (telegram_id,)).fetchone()
            if row:
                return row["phone"]
    return None


