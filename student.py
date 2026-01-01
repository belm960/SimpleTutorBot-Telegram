# --- student.py ---
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from constants import S_NAME, S_PHONE, S_CITY, S_GRADE, S_SUBJECT, S_MODE, S_NOTES, MENU, ST_SEARCH_SUBJECT, ST_SEARCH_GRADE, ST_SEARCH_CITY, ST_PICK_TUTOR, ST_WRITE_REQUEST, CHOOSING_ROLE
from keyboards import main_menu_keyboard, phone_keyboard, mode_keyboard_student
from database import save_student, search_tutors, create_request
from common import get_phone_from_db

def _is_back_to_main_menu(msg: str) -> bool:
    return (msg or "").strip().lower() in ("🏠 back to main menu", "back to main menu", "main menu")

async def s_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Send your phone number (or type it).",
        reply_markup=phone_keyboard()
    )
    return S_PHONE

async def s_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
        msg = None
    else:
        phone = (update.message.text or "").strip()
        msg = update.message.text
    context.user_data["phone"] = phone
    await update.message.reply_text("City?", reply_markup=ReplyKeyboardRemove())
    return S_CITY

async def s_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("Grade/Level? (e.g., Grade 10, University 1st year, etc.)", reply_markup=ReplyKeyboardRemove())
    return S_GRADE

async def s_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["grade"] = update.message.text.strip()
    await update.message.reply_text("Which subject do you need a tutor for? (e.g., Math, English, Physics)", reply_markup=ReplyKeyboardRemove())
    return S_SUBJECT

async def s_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject_needed"] = update.message.text.strip()
    await update.message.reply_text("Preferred mode?", reply_markup=mode_keyboard_student())
    return S_MODE

async def s_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message.text
    mode = (msg or "").strip().lower()
    if mode not in ("online", "in-person", "in person", "inperson"):
        await update.message.reply_text("Choose Online or In-person.", reply_markup=mode_keyboard_student())
        return S_MODE
    context.user_data["mode"] = "online" if mode == "online" else "in-person"
    await update.message.reply_text("Any notes? (or type 'none')", reply_markup=ReplyKeyboardRemove())
    return S_NOTES

async def s_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    notes = (update.message.text or "").strip()
    if notes.lower() == "none":
        notes = ""
    context.user_data["notes"] = notes
    save_student(update.effective_user.id, context.user_data)
    await update.message.reply_text(
        "✅ Student registration complete!\nChoose an option:",
        reply_markup=main_menu_keyboard("student")
    )
    return MENU

# Student search + request
async def st_search_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.", 
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    context.user_data["search_subject"] = (update.message.text or "").strip()
    await update.message.reply_text("Optional: Enter grade filter (or type 'skip'):", reply_markup=ReplyKeyboardMarkup(
        [["🏠 Back to main menu"]],
        resize_keyboard=True
    ))
    return ST_SEARCH_GRADE

async def st_search_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    grade = (update.message.text or "").strip()
    context.user_data["search_grade"] = "" if grade.lower() == "skip" else grade
    await update.message.reply_text("Optional: Enter city filter (or type 'skip'):", reply_markup=ReplyKeyboardMarkup(
        [["🏠 Back to main menu"]],
        resize_keyboard=True
    ))
    return ST_SEARCH_CITY

async def st_search_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    city = (update.message.text or "").strip()
    context.user_data["search_city"] = "" if city.lower() == "skip" else city
    subject = context.user_data["search_subject"]
    grade = context.user_data.get("search_grade") or None
    cityf = context.user_data.get("search_city") or None
    results = search_tutors(subject=subject, grade=grade, city=cityf)
    if not results:
        await update.message.reply_text(
            "No approved tutors found for that search.\nTry again from the menu.",
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    lines = ["✅ Found tutors:\n"]
    for i, t in enumerate(results[:10], start=1):
        lines.append(
            f"{i}) {t['full_name']} | {t['city']} | {t['subjects']} | Exp:{t['experience_years']}y | {t['hourly_rate']}"
        )
    context.user_data["search_results"] = [dict(r) for r in results[:10]]
    await update.message.reply_text(
        "\n".join(lines) + "\n\nReply with the tutor number to send a request (e.g., 1).", reply_markup=ReplyKeyboardMarkup(
            [["🏠 Back to main menu"]],
            resize_keyboard=True
        )
    )
    return ST_PICK_TUTOR

async def st_pick_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    txt = (update.message.text or "").strip()
    try:
        choice = int(txt)
    except ValueError:
        await update.message.reply_text("Please type a number (e.g., 1).")
        return ST_PICK_TUTOR
    results = context.user_data.get("search_results", [])
    if choice < 1 or choice > len(results):
        await update.message.reply_text("Number out of range. Try again.")
        return ST_PICK_TUTOR
    tutor = results[choice - 1]
    context.user_data["picked_tutor_id"] = tutor["telegram_id"]
    context.user_data["picked_tutor_name"] = tutor["full_name"]
    await update.message.reply_text(
        f"Write a message request to {tutor['full_name']} (include your availability, topic, etc.):"
    , reply_markup=ReplyKeyboardMarkup(
        [["🏠 Back to main menu"]],
        resize_keyboard=True
    ))
    return ST_WRITE_REQUEST

async def st_write_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("student")
        )
        return MENU
    message = (update.message.text or "").strip()
    student_id = update.effective_user.id
    tutor_id = int(context.user_data["picked_tutor_id"])
    tutor_name = context.user_data["picked_tutor_name"]
    create_request(student_id, tutor_id, message)
    phone = get_phone_from_db(update, "student")
    # Notify tutor
    try:
        await context.bot.send_message(
            chat_id=tutor_id,
            text=(
                "📩 *New tutoring request!*\n"
                f"From student ID: `{student_id}`\n\n"
                f"Message:\n{message}\n\n"
                f"Phone: `{phone}`\n\n"
                "Reply to the student directly in Telegram (open their profile using the ID), "
                "or build a /reply feature later."
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await update.message.reply_text(
        f"✅ Your request was sent to {tutor_name}.\nChoose an option:",
        reply_markup=main_menu_keyboard("student")
    )
    return MENU