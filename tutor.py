# --- tutor.py ---
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from constants import T_NAME, T_PHONE, T_CITY, T_SUBJECTS, T_GRADES, T_EXP, T_MODE, T_RATE, T_BIO, T_TEST_Q, MENU, PASS_MARK, TUTOR_TEST
from keyboards import phone_keyboard, mode_keyboard_tutor, main_menu_keyboard
from database import save_tutor

def _is_back_to_main_menu(msg: str) -> bool:
    return (msg or "").strip().lower() in ("🏠 back to main menu", "back to main menu", "main menu")

async def t_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Send your phone number (or type it).", reply_markup=phone_keyboard())
    return T_PHONE

async def t_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
        msg = None
    else:
        phone = (update.message.text or "").strip()
        msg = update.message.text
    if _is_back_to_main_menu(msg):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["phone"] = phone
    await update.message.reply_text("City?", reply_markup=ReplyKeyboardRemove())
    return T_CITY

async def t_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("Subjects you teach (comma-separated), e.g., Math, Physics, English")
    return T_SUBJECTS

async def t_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["subjects"] = update.message.text.strip()
    await update.message.reply_text("Grades/Levels you teach (comma-separated), e.g., Grade 7-10, University")
    return T_GRADES

async def t_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["grades"] = update.message.text.strip()
    await update.message.reply_text("Experience years? (number)")
    return T_EXP

async def t_exp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    text = (update.message.text or "").strip()
    try:
        years = int(text)
        if years < 0 or years > 80:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Please enter a valid number of years (e.g., 2).")
        return T_EXP
    context.user_data["experience_years"] = years
    await update.message.reply_text("Mode you offer?", reply_markup=mode_keyboard_tutor())
    return T_MODE

async def t_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    mode = (update.message.text or "").strip().lower()
    valid = {"online": "online", "in-person": "in-person", "in person": "in-person", "both": "both"}
    if mode not in valid:
        await update.message.reply_text("Choose Online / In-person / Both.", reply_markup=mode_keyboard_tutor())
        return T_MODE
    context.user_data["mode"] = valid[mode]
    await update.message.reply_text("Hourly rate? (e.g., 300 ETB/hour, $10/hour)")
    return T_RATE

async def t_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["hourly_rate"] = (update.message.text or "").strip()
    await update.message.reply_text("Short bio (1–3 sentences):")
    return T_BIO

async def t_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    context.user_data["bio"] = (update.message.text or "").strip()
    # Start test
    context.user_data["test_index"] = 0
    context.user_data["test_correct"] = 0
    await send_test_question(update, context)
    return T_TEST_Q

async def send_test_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _is_back_to_main_menu(update.message.text):
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=main_menu_keyboard("tutor")
        )
        return MENU
    idx = context.user_data["test_index"]
    q, options, _ = TUTOR_TEST[idx]
    kb = ReplyKeyboardMarkup([[o] for o in options], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(q, reply_markup=kb)

async def t_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    idx = context.user_data["test_index"]
    q, options, correct_idx = TUTOR_TEST[idx]
    answer = (update.message.text or "").strip()
    if answer not in options:
        await update.message.reply_text("Please choose one of the options on the keyboard.")
        await send_test_question(update, context)
        return T_TEST_Q
    if options.index(answer) == correct_idx:
        context.user_data["test_correct"] += 1
    context.user_data["test_index"] += 1
    if context.user_data["test_index"] >= len(TUTOR_TEST):
        score = context.user_data["test_correct"]
        status = "approved" if score >= PASS_MARK else "rejected"
        save_tutor(update.effective_user.id, context.user_data, test_score=score, status=status)
        if status == "approved":
            await update.message.reply_text(
                f"✅ Test complete! Score: {score}/{len(TUTOR_TEST)}.\nYou are *APPROVED* as a tutor.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard("tutor")
            )
        else:
            await update.message.reply_text(
                f"❌ Test complete. Score: {score}/{len(TUTOR_TEST)}.\nYou need at least {PASS_MARK} correct.\nStatus: *REJECTED*.\n\nYou can contact admin to retry later.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard("tutor")
            )
        return MENU
    # next question
    await send_test_question(update, context)
    return T_TEST_Q