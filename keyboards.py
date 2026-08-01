# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── Онбординг ──
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Rules", callback_data="rules"),
            InlineKeyboardButton(text="📅 Schedule", callback_data="schedule"),
        ],
        [
            InlineKeyboardButton(text="🎤 Speaking Club", callback_data="show_clubs"),
        ],
        [
            InlineKeyboardButton(text="📚 Lessons", callback_data="lessons"),
        ],
        [
            InlineKeyboardButton(text="💬 Contact us", callback_data="contacts"),
        ],
    ])


def main_menu_with_register_kb() -> InlineKeyboardMarkup:
    """Меню со кнопкой регистрации — показывается только один раз при старте"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✍️ Register as a student", callback_data="register_student"),
        ],
        [
            InlineKeyboardButton(text="📋 Rules", callback_data="rules"),
            InlineKeyboardButton(text="📅 Schedule", callback_data="schedule"),
        ],
        [
            InlineKeyboardButton(text="🎤 Speaking Club", callback_data="show_clubs"),
        ],
        [
            InlineKeyboardButton(text="👥 Group Lessons", callback_data="join_group"),
            InlineKeyboardButton(text="👤 Individual Lessons", callback_data="individual"),
        ],
        [
            InlineKeyboardButton(text="💬 Contact us", callback_data="contacts"),
        ],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Back to menu", callback_data="back")]
    ])


def consent_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I agree to data processing", callback_data="consent_agree")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="back")],
    ])


def how_found_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Advertisement", callback_data="found_ad")],
        [InlineKeyboardButton(text="👥 Friends", callback_data="found_friends")],
        [InlineKeyboardButton(text="👩‍🏫 Teacher", callback_data="found_teacher")],
        [InlineKeyboardButton(text="✏️ Other (write)", callback_data="found_other")],
    ])


# ── Speaking Club ──
def clubs_kb(clubs: list) -> InlineKeyboardMarkup:
    buttons = []
    for club in clubs:
        spots_left = club["max_spots"] - club["registered"]
        label = f"📅 {club['date']} {club['time']} | {club['topic']} ({club['level']}) | 👥 {spots_left} spots"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"club_{club['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to menu", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def club_detail_kb(club_id: int, spots_left: int, already: bool) -> InlineKeyboardMarkup:
    buttons = []
    if already:
        buttons.append([InlineKeyboardButton(text="✅ You're already registered", callback_data="already")])
    elif spots_left > 0:
        buttons.append([InlineKeyboardButton(text="📝 Register", callback_data=f"register_{club_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="😔 No spots left", callback_data="no_spots")])
    buttons.append([InlineKeyboardButton(text="◀️ Back to clubs", callback_data="show_clubs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb(club_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, register me!", callback_data=f"confirm_{club_id}")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data=f"club_{club_id}")],
    ])


# ── Админ ──
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Speaking Club", callback_data="admin_create")],
        [InlineKeyboardButton(text="📋 Clubs & participants", callback_data="admin_list")],
        [InlineKeyboardButton(text="🔔 Send reminders", callback_data="admin_notify")],
        [InlineKeyboardButton(text="👥 Student list", callback_data="admin_students")],
        [InlineKeyboardButton(text="📋 Student profiles", callback_data="admin_profiles")],
        [InlineKeyboardButton(text="❌ Cancel club", callback_data="admin_delete_club")],
        [InlineKeyboardButton(text="📢 Broadcast to all students", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📝 New weekly topic", callback_data="admin_weekly_topic")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="✅ Close all clubs", callback_data="admin_close_clubs")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_state")]
    ])
