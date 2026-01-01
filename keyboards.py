# --- keyboards.py ---
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton

def main_menu_keyboard(user_role: str) -> ReplyKeyboardMarkup:
    if user_role == "student":
        buttons = [
            ["🔎 Search Tutors"],
            ["👤 My Profile"],
            ["❌ Cancel"],
        ]
    else:
        buttons = [
            ["👤 My Profile"],
            ["❌ Cancel"],
        ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def yesno_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Yes", "No"]], resize_keyboard=True)

def mode_keyboard_student() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Online"], ["In-person"]], resize_keyboard=True)

def mode_keyboard_tutor() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Online"], ["In-person"], ["Both"]], resize_keyboard=True)

def role_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Student"], ["Tutor"]], resize_keyboard=True)

def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Share phone number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )