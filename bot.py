# --- bot.py (main entry point) ---
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from constants import *
from keyboards import *
from database import init_db, get_user, upsert_user
from student import (
    s_name, s_phone, s_city, s_grade, s_subject, s_mode, s_notes,
    st_search_subject, st_search_grade, st_search_city,
    st_pick_tutor, st_write_request
)
from tutor import (
    t_name, t_phone, t_city, t_subjects, t_grades, t_exp, t_mode, t_rate, t_bio, t_test
)
from common import show_profile

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

MAIN_MENU_COMMANDS = ("🏠 back to main menu", "back to main menu", "main menu")

def menu_keyboard(role):
    """Return the menu keyboard for this role, without adding 'Back to main menu' button at main MENU."""
    kb = main_menu_keyboard(role)
    return kb  # Do NOT add 'Back to main menu' at the main menu

def menu_keyboard_with_back(role):
    """Returns the main menu keyboard with 'Back to main menu' appended, for use in submenus only."""
    kb = main_menu_keyboard(role)
    btn = "🏠 Back to main menu"
    if isinstance(kb, ReplyKeyboardMarkup) and hasattr(kb, "keyboard"):
        flattened = []
        for row in kb.keyboard:
            if isinstance(row, (list, tuple)):
                flattened.extend(list(row))
            else:
                flattened.append(row)
        if btn not in flattened:
            new_keyboard = list(kb.keyboard)
            new_keyboard.append([btn])
            return ReplyKeyboardMarkup(
                new_keyboard,
                resize_keyboard=getattr(kb, "resize_keyboard", True),
                one_time_keyboard=getattr(kb, "one_time_keyboard", False),
                selective=getattr(kb, "selective", False),
                input_field_placeholder=getattr(kb, "input_field_placeholder", None),
                is_persistent=getattr(kb, "is_persistent", None),
            )
    return kb

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user(update.effective_user.id)
    if user:
        role = user["role"]
        await update.message.reply_text(
            f"Welcome back! You are registered as *{role}*.\nChoose an option:",
            reply_markup=menu_keyboard(role),
            parse_mode="Markdown"
        )
        return MENU
    await update.message.reply_text(
        "Welcome! This bot connects *students* with *tutors*.\n\nAre you registering as a Student or a Tutor?",
        reply_markup=role_keyboard(),
        parse_mode="Markdown"
    )
    return CHOOSING_ROLE

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip().lower()
    if text not in ("student", "tutor"):
        await update.message.reply_text("Please choose: Student or Tutor.", reply_markup=role_keyboard())
        return CHOOSING_ROLE

    role = "student" if text == "student" else "tutor"
    context.user_data["role"] = role

    if role == "student":
        upsert_user(update.effective_user.id, "student", "active")
        await update.message.reply_text("Student registration: What is your full name?", reply_markup=ReplyKeyboardRemove())
        return S_NAME
    else:
        upsert_user(update.effective_user.id, "tutor", "pending")
        await update.message.reply_text("Tutor registration: What is your full name?", reply_markup=ReplyKeyboardRemove())
        return T_NAME

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return ConversationHandler.END

    choice = (update.message.text or "").strip().lower()
    role = user["role"]

    # Check if user wants to go back to main menu from anywhere
    if choice in MAIN_MENU_COMMANDS or choice in ("🏠 back to main menu", "back to main menu", "main menu"):
        # This allows "main menu" to work from anywhere including MENU state itself
        await update.message.reply_text(
            "Returning to main menu.",
            reply_markup=menu_keyboard(role)
        )
        return MENU

    if choice in ("👤 my profile", "my profile"):
        await show_profile(update, context, role)
        return MENU

    if role == "student" and choice in ("🔎 search tutors", "search tutors"):
        await update.message.reply_text(
            "Search tutors: enter subject (e.g., Math):",
            reply_markup=ReplyKeyboardMarkup(
                [["🏠 Back to main menu"]],
                resize_keyboard=True
            )
        )
        return ST_SEARCH_SUBJECT

    await update.message.reply_text("Choose an option from the menu.", reply_markup=menu_keyboard(role))
    return MENU

def add_back_to_main_menu_handler():
    """This handler sends the user to the main menu, regardless of the current state."""
    async def back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = get_user(update.effective_user.id)
        role = user["role"] if user else "student"
        await update.message.reply_text(
            "Returning to main menu.", 
            reply_markup=menu_keyboard(role)
        )
        return MENU

    return MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex("(?i)(^🏠 back to main menu$|^back to main menu$|^main menu$)"),
        back_handler
    )

def build_app() -> Application:
    from constants import TOKEN
    if not TOKEN:
        raise RuntimeError("Missing BOT_TOKEN env var. Set it first.")
    init_db()
    app = Application.builder().token(TOKEN).build()
    # Compose all state handlers, appending the universal "back to main menu" handler to each, including MENU state
    state_handlers = {
        CHOOSING_ROLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role),
            add_back_to_main_menu_handler()
        ],
        # Student registration
        S_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_name),
            add_back_to_main_menu_handler()
        ],
        S_PHONE: [
            MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), s_phone),
            add_back_to_main_menu_handler()
        ],
        S_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_city),
            add_back_to_main_menu_handler()
        ],
        S_GRADE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_grade),
            add_back_to_main_menu_handler()
        ],
        S_SUBJECT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_subject),
            add_back_to_main_menu_handler()
        ],
        S_MODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_mode),
            add_back_to_main_menu_handler()
        ],
        S_NOTES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, s_notes),
            add_back_to_main_menu_handler()
        ],
        # Tutor registration
        T_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_name),
            add_back_to_main_menu_handler()
        ],
        T_PHONE: [
            MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), t_phone),
            add_back_to_main_menu_handler()
        ],
        T_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_city),
            add_back_to_main_menu_handler()
        ],
        T_SUBJECTS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_subjects),
            add_back_to_main_menu_handler()
        ],
        T_GRADES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_grades),
            add_back_to_main_menu_handler()
        ],
        T_EXP: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_exp),
            add_back_to_main_menu_handler()
        ],
        T_MODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_mode),
            add_back_to_main_menu_handler()
        ],
        T_RATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_rate),
            add_back_to_main_menu_handler()
        ],
        T_BIO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_bio),
            add_back_to_main_menu_handler()
        ],
        T_TEST_Q: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, t_test),
            add_back_to_main_menu_handler()
        ],
        # Menu + Student actions
        MENU: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, menu),
            add_back_to_main_menu_handler()
        ],
        ST_SEARCH_SUBJECT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_subject),
            add_back_to_main_menu_handler()
        ],
        ST_SEARCH_GRADE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_grade),
            add_back_to_main_menu_handler()
        ],
        ST_SEARCH_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_city),
            add_back_to_main_menu_handler()
        ],
        ST_PICK_TUTOR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, st_pick_tutor),
            add_back_to_main_menu_handler()
        ],
        ST_WRITE_REQUEST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, st_write_request),
            add_back_to_main_menu_handler()
        ],
    }
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states=state_handlers,
        fallbacks=[],  # No cancel fallback
        allow_reentry=True,
    )
    app.add_handler(conv)
    return app

def main():
    app = build_app()
    app.run_polling()

if __name__ == "__main__":
    main()
