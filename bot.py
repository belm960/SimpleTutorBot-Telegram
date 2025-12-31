import os
import sqlite3
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =========================
# Config
# =========================
TOKEN = "7621642546:AAGHA4Q7AysOAfbvnoEHjo8d-pmGv5S74aU"
DB_PATH = "tutor_bot.db"

# Tutor screening questions (edit these!)
# Format: (question, options list, correct option index)
TUTOR_TEST = [
    ("Q1) What is 12 + 8?", ["18", "20", "22"], 1),
    ("Q2) Which is a prime number?", ["21", "27", "29"], 2),
    ("Q3) Simplify: 3 * (4 + 2)", ["18", "20", "24"], 0),
]

PASS_MARK = 2  # must get >=2 correct out of 3


# =========================
# Database
# =========================
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        c = conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL,                -- 'student' or 'tutor'
            status TEXT NOT NULL,              -- student: 'active', tutor: 'pending'/'approved'/'rejected'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT,
            city TEXT,
            grade TEXT,
            subject_needed TEXT,
            mode TEXT,          -- online / in-person
            notes TEXT,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS tutors (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            phone TEXT,
            city TEXT,
            subjects TEXT,      -- comma-separated
            grades TEXT,        -- comma-separated
            experience_years INTEGER,
            mode TEXT,          -- online / in-person / both
            hourly_rate TEXT,
            bio TEXT,
            test_score INTEGER DEFAULT 0,
            FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            tutor_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()


def upsert_user(telegram_id: int, role: str, status: str):
    with db() as conn:
        conn.execute("""
        INSERT INTO users(telegram_id, role, status) VALUES(?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET role=excluded.role, status=excluded.status
        """, (telegram_id, role, status))
        conn.commit()


def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    with db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return cur.fetchone()


def save_student(telegram_id: int, data: Dict[str, Any]):
    with db() as conn:
        conn.execute("""
        INSERT INTO students(telegram_id, full_name, phone, city, grade, subject_needed, mode, notes)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET
          full_name=excluded.full_name,
          phone=excluded.phone,
          city=excluded.city,
          grade=excluded.grade,
          subject_needed=excluded.subject_needed,
          mode=excluded.mode,
          notes=excluded.notes
        """, (
            telegram_id,
            data.get("full_name"),
            data.get("phone"),
            data.get("city"),
            data.get("grade"),
            data.get("subject_needed"),
            data.get("mode"),
            data.get("notes"),
        ))
        conn.commit()


def save_tutor(telegram_id: int, data: Dict[str, Any], test_score: int, status: str):
    with db() as conn:
        conn.execute("""
        INSERT INTO tutors(telegram_id, full_name, phone, city, subjects, grades, experience_years, mode, hourly_rate, bio, test_score)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(telegram_id) DO UPDATE SET
          full_name=excluded.full_name,
          phone=excluded.phone,
          city=excluded.city,
          subjects=excluded.subjects,
          grades=excluded.grades,
          experience_years=excluded.experience_years,
          mode=excluded.mode,
          hourly_rate=excluded.hourly_rate,
          bio=excluded.bio,
          test_score=excluded.test_score
        """, (
            telegram_id,
            data.get("full_name"),
            data.get("phone"),
            data.get("city"),
            data.get("subjects"),
            data.get("grades"),
            int(data.get("experience_years") or 0),
            data.get("mode"),
            data.get("hourly_rate"),
            data.get("bio"),
            test_score
        ))
        # update user status
        conn.execute("UPDATE users SET status=? WHERE telegram_id=?", (status, telegram_id))
        conn.commit()


def search_tutors(subject: str, grade: Optional[str] = None, city: Optional[str] = None) -> List[sqlite3.Row]:
    # Basic LIKE matching; you can improve to normalized tables later.
    q = """
    SELECT u.status, t.*
    FROM tutors t
    JOIN users u ON u.telegram_id = t.telegram_id
    WHERE u.role='tutor' AND u.status='approved'
      AND lower(t.subjects) LIKE lower(?)
    """
    params: List[Any] = [f"%{subject}%"]

    if grade:
        q += " AND lower(t.grades) LIKE lower(?)"
        params.append(f"%{grade}%")
    if city:
        q += " AND lower(t.city) LIKE lower(?)"
        params.append(f"%{city}%")

    q += " ORDER BY t.experience_years DESC"

    with db() as conn:
        cur = conn.execute(q, params)
        return cur.fetchall()


def create_request(student_id: int, tutor_id: int, message: str):
    with db() as conn:
        conn.execute(
            "INSERT INTO requests(student_id, tutor_id, message) VALUES (?,?,?)",
            (student_id, tutor_id, message),
        )
        conn.commit()


# =========================
# Conversation States
# =========================
(
    CHOOSING_ROLE,
    MENU,

    # Student registration
    S_NAME, S_PHONE, S_CITY, S_GRADE, S_SUBJECT, S_MODE, S_NOTES,

    # Tutor registration
    T_NAME, T_PHONE, T_CITY, T_SUBJECTS, T_GRADES, T_EXP, T_MODE, T_RATE, T_BIO,
    T_TEST_Q,

    # Student search / request
    ST_SEARCH_SUBJECT, ST_SEARCH_GRADE, ST_SEARCH_CITY,
    ST_PICK_TUTOR, ST_WRITE_REQUEST,
) = range(24)


# =========================
# Helpers
# =========================
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


# =========================
# Handlers
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user(update.effective_user.id)
    if user:
        role = user["role"]
        await update.message.reply_text(
            f"Welcome back! You are registered as *{role}*.\nChoose an option:",
            reply_markup=main_menu_keyboard(role),
            parse_mode="Markdown"
        )
        return MENU

    await update.message.reply_text(
        "Welcome! This bot connects *students* with *tutors*.\n\nAre you registering as a Student or a Tutor?",
        reply_markup=role_keyboard(),
        parse_mode="Markdown"
    )
    return CHOOSING_ROLE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# -------------------------
# Role selection
# -------------------------
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


# -------------------------
# Student registration steps
# -------------------------
async def s_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Send your phone number (or type it).", reply_markup=phone_keyboard())
    return S_PHONE


async def s_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = (update.message.text or "").strip()
    context.user_data["phone"] = phone
    await update.message.reply_text("City?", reply_markup=ReplyKeyboardRemove())
    return S_CITY


async def s_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("Grade/Level? (e.g., Grade 10, University 1st year, etc.)")
    return S_GRADE


async def s_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["grade"] = update.message.text.strip()
    await update.message.reply_text("Which subject do you need a tutor for? (e.g., Math, English, Physics)")
    return S_SUBJECT


async def s_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subject_needed"] = update.message.text.strip()
    await update.message.reply_text("Preferred mode?", reply_markup=mode_keyboard_student())
    return S_MODE


async def s_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    mode = (update.message.text or "").strip().lower()
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


# -------------------------
# Tutor registration steps
# -------------------------
async def t_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["full_name"] = update.message.text.strip()
    await update.message.reply_text("Send your phone number (or type it).", reply_markup=phone_keyboard())
    return T_PHONE


async def t_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = (update.message.text or "").strip()
    context.user_data["phone"] = phone
    await update.message.reply_text("City?", reply_markup=ReplyKeyboardRemove())
    return T_CITY


async def t_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("Subjects you teach (comma-separated), e.g., Math, Physics, English")
    return T_SUBJECTS


async def t_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["subjects"] = update.message.text.strip()
    await update.message.reply_text("Grades/Levels you teach (comma-separated), e.g., Grade 7-10, University")
    return T_GRADES


async def t_grades(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["grades"] = update.message.text.strip()
    await update.message.reply_text("Experience years? (number)")
    return T_EXP


async def t_exp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    mode = (update.message.text or "").strip().lower()
    valid = {"online": "online", "in-person": "in-person", "in person": "in-person", "both": "both"}
    if mode not in valid:
        await update.message.reply_text("Choose Online / In-person / Both.", reply_markup=mode_keyboard_tutor())
        return T_MODE
    context.user_data["mode"] = valid[mode]
    await update.message.reply_text("Hourly rate? (e.g., 300 ETB/hour, $10/hour)")
    return T_RATE


async def t_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["hourly_rate"] = (update.message.text or "").strip()
    await update.message.reply_text("Short bio (1–3 sentences):")
    return T_BIO


async def t_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["bio"] = (update.message.text or "").strip()

    # Start test
    context.user_data["test_index"] = 0
    context.user_data["test_correct"] = 0
    await send_test_question(update, context)
    return T_TEST_Q


async def send_test_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


# -------------------------
# Menu actions
# -------------------------
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text("Please /start first.")
        return ConversationHandler.END

    choice = (update.message.text or "").strip().lower()
    role = user["role"]

    if choice in ("❌ cancel", "cancel"):
        return await cancel(update, context)

    if choice in ("👤 my profile", "my profile"):
        await show_profile(update, context, role)
        return MENU

    if role == "student" and choice in ("🔎 search tutors", "search tutors"):
        await update.message.reply_text("Search tutors: enter subject (e.g., Math):", reply_markup=ReplyKeyboardRemove())
        return ST_SEARCH_SUBJECT

    await update.message.reply_text("Choose an option from the menu.", reply_markup=main_menu_keyboard(role))
    return MENU


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


# -------------------------
# Student search + request flow
# -------------------------
async def st_search_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["search_subject"] = (update.message.text or "").strip()
    await update.message.reply_text("Optional: Enter grade filter (or type 'skip'):")
    return ST_SEARCH_GRADE


async def st_search_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    grade = (update.message.text or "").strip()
    context.user_data["search_grade"] = "" if grade.lower() == "skip" else grade
    await update.message.reply_text("Optional: Enter city filter (or type 'skip'):")
    return ST_SEARCH_CITY


async def st_search_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    # show list + let them pick by number
    lines = ["✅ Found tutors:\n"]
    for i, t in enumerate(results[:10], start=1):
        lines.append(
            f"{i}) {t['full_name']} | {t['city']} | {t['subjects']} | Exp:{t['experience_years']}y | {t['hourly_rate']}"
        )

    context.user_data["search_results"] = [dict(r) for r in results[:10]]

    await update.message.reply_text(
        "\n".join(lines) + "\n\nReply with the tutor number to send a request (e.g., 1).",
        reply_markup=ReplyKeyboardRemove()
    )
    return ST_PICK_TUTOR


async def st_pick_tutor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    )
    return ST_WRITE_REQUEST


async def st_write_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = (update.message.text or "").strip()
    student_id = update.effective_user.id
    tutor_id = int(context.user_data["picked_tutor_id"])
    tutor_name = context.user_data["picked_tutor_name"]

    create_request(student_id, tutor_id, message)

    # Notify tutor
    try:
        await context.bot.send_message(
            chat_id=tutor_id,
            text=(
                "📩 *New tutoring request!*\n"
                f"From student ID: `{student_id}`\n\n"
                f"Message:\n{message}\n\n"
                "Reply to the student directly in Telegram (open their profile using the ID), "
                "or build a /reply feature later."
            ),
            parse_mode="Markdown"
        )
    except Exception:
        # Tutor may have blocked the bot or never started it
        pass

    await update.message.reply_text(
        f"✅ Your request was sent to {tutor_name}.\nChoose an option:",
        reply_markup=main_menu_keyboard("student")
    )
    return MENU


# =========================
# Main
# =========================
def build_app() -> Application:
    if not TOKEN:
        raise RuntimeError("Missing BOT_TOKEN env var. Set it first.")

    init_db()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],

            # Student registration
            S_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_name)],
            S_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), s_phone)],
            S_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_city)],
            S_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_grade)],
            S_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_subject)],
            S_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_mode)],
            S_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_notes)],

            # Tutor registration
            T_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_name)],
            T_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), t_phone)],
            T_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_city)],
            T_SUBJECTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_subjects)],
            T_GRADES: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_grades)],
            T_EXP: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_exp)],
            T_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_mode)],
            T_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_rate)],
            T_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_bio)],
            T_TEST_Q: [MessageHandler(filters.TEXT & ~filters.COMMAND, t_test)],

            # Menu + Student actions
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu)],

            ST_SEARCH_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_subject)],
            ST_SEARCH_GRADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_grade)],
            ST_SEARCH_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_search_city)],
            ST_PICK_TUTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_pick_tutor)],
            ST_WRITE_REQUEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, st_write_request)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    return app


def main():
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
