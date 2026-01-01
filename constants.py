# --- constants.py ---
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