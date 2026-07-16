# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# ── Онбординг ──
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Правила", callback_data="rules"),
            InlineKeyboardButton(text="📅 Расписание", callback_data="schedule"),
        ],
        [
            InlineKeyboardButton(text="🎤 Speaking Club", callback_data="show_clubs"),
            InlineKeyboardButton(text="🔗 Пригласить друга", callback_data="referral"),
        ],
        [
            InlineKeyboardButton(text="💬 Связаться с куратором", callback_data="contacts"),
        ],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back")]
    ])


# ── Speaking Club ──
def clubs_kb(clubs: list) -> InlineKeyboardMarkup:
    buttons = []
    for club in clubs:
        spots_left = club["max_spots"] - club["registered"]
        label = f"📅 {club['date']} {club['time']} | {club['topic']} ({club['level']}) | 👥 {spots_left} мест"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"club_{club['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def club_detail_kb(club_id: int, spots_left: int, already: bool) -> InlineKeyboardMarkup:
    buttons = []
    if already:
        buttons.append([InlineKeyboardButton(text="✅ Ты уже записана", callback_data="already")])
    elif spots_left > 0:
        buttons.append([InlineKeyboardButton(text="📝 Записаться", callback_data=f"register_{club_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="😔 Мест нет", callback_data="no_spots")])
    buttons.append([InlineKeyboardButton(text="◀️ К списку клубов", callback_data="show_clubs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb(club_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, записаться!", callback_data=f"confirm_{club_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"club_{club_id}")],
    ])


# ── Админ ──
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать Speaking Club", callback_data="admin_create")],
        [InlineKeyboardButton(text="📋 Список клубов и участников", callback_data="admin_list")],
        [InlineKeyboardButton(text="🔔 Разослать напоминания", callback_data="admin_notify")],
        [InlineKeyboardButton(text="👥 Список учеников", callback_data="admin_students")],
        [InlineKeyboardButton(text="❌ Удалить клуб", callback_data="admin_delete_club")],
        [InlineKeyboardButton(text="📢 Рассылка всем ученикам", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📝 Новая тема недели", callback_data="admin_weekly_topic")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="✅ Завершить все клубы", callback_data="admin_close_clubs")],
    ])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_state")]
    ])
