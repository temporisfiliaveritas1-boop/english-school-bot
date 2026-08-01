# bot.py — главный файл, объединяет онбординг + Speaking Club
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import CommandStart, Command, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, GROUP_ID, ADMIN_ID, ADMIN_IDS
from keyboards import (
    main_menu_kb, back_kb,
    clubs_kb, club_detail_kb, confirm_kb,
    admin_menu_kb, cancel_kb
)
from messages import WELCOME_MSG, RULES_MSG, SCHEDULE_MSG, CONTACTS_MSG
from database import Database
import sheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


# ══════════════════════════════════════════════
# FSM — создание Speaking Club (для админа)
# ══════════════════════════════════════════════
class CreateClub(StatesGroup):
    date = State()
    time = State()
    topic = State()
    level = State()
    meet_link = State()


class Broadcast(StatesGroup):
    text = State()


class WeeklyTopic(StatesGroup):
    text = State()


class DeleteClub(StatesGroup):
    club_id = State()


class NotifyClub(StatesGroup):
    club_id = State()

# ══════════════════════════════════════════════
# ОНБОРДИНГ
# ══════════════════════════════════════════════

@dp.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def new_member(event: ChatMemberUpdated):
    """Новый участник вступил в группу"""
    if event.chat.id != GROUP_ID:
        return
    user = event.new_chat_member.user
    if user.is_bot:
        return

    db.add_student(user.id, user.username or "", user.full_name)
    sheets.add_student(user.id, user.username or "", user.full_name)

    await bot.send_message(
        ADMIN_ID,
        f"🆕 Новый ученик: {user.full_name} (@{user.username})\n"
        f"ID: {user.id} | Всего: {db.count_students()}"
    )

    try:
        await bot.send_message(
            user.id,
            WELCOME_MSG.format(name=user.first_name),
            reply_markup=main_menu_kb()
        )
    except Exception:
        await bot.send_message(
            GROUP_ID,
            f"👋 {user.mention_html()}, добро пожаловать! "
            f"Напиши мне в личку — расскажу всё о курсе 👉 /start",
            parse_mode="HTML"
        )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    """/start — запуск бота"""
    args = message.text.split()
    if len(args) > 1:
        await process_referral(message.from_user.id, args[1])

    db.add_student(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name
    )
    await message.answer(
        WELCOME_MSG.format(name=message.from_user.first_name),
        reply_markup=main_menu_kb()
    )


@dp.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery):
    await callback.message.edit_text(
        WELCOME_MSG.format(name=callback.from_user.first_name),
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "rules")
async def show_rules(callback: CallbackQuery):
    await callback.message.edit_text(RULES_MSG, parse_mode="Markdown", reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "schedule")
async def show_schedule(callback: CallbackQuery):
    await callback.message.edit_text(SCHEDULE_MSG, parse_mode="Markdown", reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    await callback.message.edit_text(CONTACTS_MSG, parse_mode="Markdown", reply_markup=back_kb())
    await callback.answer()
    
@dp.callback_query(F.data == "join_group")
async def join_group(callback: CallbackQuery):
    await callback.message.edit_text(
        "👥 *Groups*\n\n"
        "To join a group, write to our manager:\n"
        "@Tosha_petrolay\n\n"
        "She will find the right group for your level and schedule!",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "individual")
async def individual_lessons(callback: CallbackQuery):
    await callback.message.edit_text(
        "👤 *Individuals*\n\n"
        "Want to study one on one with a teacher?\n"
        "Write to our manager:\n"
        "@Tosha_petrolay\n\n"
        "She will find the perfect teacher for your goals and level!",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )
    await callback.answer()

# ══════════════════════════════════════════════
# SPEAKING CLUB — ученик
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "show_clubs")
async def show_clubs(callback: CallbackQuery):
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.message.edit_text(
            "😔 Пока нет доступных Speaking Club.\nСледи за анонсами в группе!",
            reply_markup=back_kb()
        )
    else:
        await callback.message.edit_text(
            "🎤 Выбери Speaking Club:",
            reply_markup=clubs_kb(clubs)
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("club_"))
async def show_club_detail(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    club = db.get_club(club_id)
    if not club:
        await callback.answer("Клуб не найден", show_alert=True)
        return

    spots_left = club["max_spots"] - club["registered"]
    already = db.is_registered(callback.from_user.id, club_id)

    text = (
        f"🎤 *Speaking Club*\n\n"
        f"📅 Дата: {club['date']}\n"
        f"🕐 Время: {club['time']}\n"
        f"💬 Тема: {club['topic']}\n"
        f"📊 Уровень: {club['level']}\n"
        f"👥 Мест осталось: {spots_left} из {club['max_spots']}"
    )
    if already:
        text += "\n\n✅ Ты уже записана на этот клуб!"

    await callback.message.edit_text(
        text, parse_mode="Markdown",
        reply_markup=club_detail_kb(club_id, spots_left, already)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("register_"))
async def register_confirm(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    club = db.get_club(club_id)
    await callback.message.edit_text(
        f"Подтверди запись:\n\n"
        f"📅 {club['date']} в {club['time']}\n"
        f"💬 Тема: {club['topic']}\n"
        f"📊 Уровень: {club['level']}",
        reply_markup=confirm_kb(club_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_"))
async def register_done(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    user = callback.from_user

    if db.get_spots_left(club_id) <= 0:
        await callback.answer("😔 Места закончились!", show_alert=True)
        return
    if db.is_registered(user.id, club_id):
        await callback.answer("Ты уже записана!", show_alert=True)
        return

    db.register(user.id, user.username or "", user.full_name, club_id)
    club = db.get_club(club_id)
    registered = db.get_registered_count(club_id)
    sheets.add_registration(user.id, user.username or "", user.full_name, club_id, club["date"], club["time"], club["topic"])


    await callback.message.edit_text(
        f"🎉 Отлично, ты записана!\n\n"
        f"📅 {club['date']} в {club['time']}\n"
        f"💬 Тема: {club['topic']}\n"
        f"📊 Уровень: {club['level']}\n\n"
        f"⏰ Я пришлю тебе напоминание и ссылку на Google Meet.\n"
        f"Если захочешь отменить — напиши /cancel_{club_id}",
        reply_markup=back_kb()
    )
    await bot.send_message(
        ADMIN_ID,
        f"🆕 Запись на Speaking Club!\n"
        f"👤 {user.full_name} (@{user.username})\n"
        f"📅 {club['date']} {club['time']} — {club['topic']}\n"
        f"👥 Записано: {registered}/{club['max_spots']}"
    )
    await callback.answer()


@dp.callback_query(F.data.in_({"already", "no_spots"}))
async def stub_callbacks(callback: CallbackQuery):
    await callback.answer()


@dp.message(F.text.startswith("/cancel_"))
async def cancel_registration(message: Message):
    try:
        club_id = int(message.text.split("_")[1])
        db.unregister(message.from_user.id, club_id)
        await message.answer("❌ Запись отменена. Ждём тебя на следующем клубе!")
    except Exception:
        await message.answer("Не удалось отменить запись.")


# ══════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ
# ══════════════════════════════════════════════

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⚙️ Панель управления:", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_create")
async def admin_create_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("📅 Введи дату клуба\nНапример: 20 июня 2025", reply_markup=cancel_kb())
    await state.set_state(CreateClub.date)
    await callback.answer()


@dp.message(CreateClub.date)
async def get_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("🕐 Введи время\nНапример: 19:00 МСК")
    await state.set_state(CreateClub.time)


@dp.message(CreateClub.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("💬 Введи тему клуба\nНапример: Travel & Holidays")
    await state.set_state(CreateClub.topic)


@dp.message(CreateClub.topic)
async def get_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("📊 Введи уровень\nНапример: A1 / A2 / A1+A2")
    await state.set_state(CreateClub.level)


@dp.message(CreateClub.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("🔗 Введи ссылку на Google Meet")
    await state.set_state(CreateClub.meet_link)


@dp.message(CreateClub.meet_link)
async def get_meet_link(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    club_id = db.create_club(
        date=data["date"], time=data["time"],
        topic=data["topic"], level=data["level"],
        meet_link=message.text, max_spots=8
    )
    sheets.add_club(club_id, data["date"], data["time"], data["topic"], data["level"])

    announce = (
        f"🎤 *Новый Speaking Club!*\n\n"
        f"📅 Дата: {data['date']}\n"
        f"🕐 Время: {data['time']}\n"
        f"💬 Тема: {data['topic']}\n"
        f"📊 Уровень: {data['level']}\n"
        f"👥 Мест: 8\n\n"
        f"Напиши боту /start и нажми 🎤 Speaking Club чтобы записаться!"
    )
    await bot.send_message(GROUP_ID, announce, parse_mode="Markdown")
    await message.answer(f"✅ Клуб создан! Анонс отправлен в группу.\nID клуба: {club_id}")


@dp.callback_query(F.data == "admin_list")
async def admin_list_clubs(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.message.answer("Нет активных клубов")
        return

    for c in clubs:
        registered = db.get_registered_count(c["id"])
        members = db.get_club_members(c["id"])
        text = (
            f"📅 {c['date']} {c['time']}\n"
            f"💬 {c['topic']} ({c['level']})\n"
            f"👥 {registered}/{c['max_spots']} записано\n"
        )
        if members:
            text += "\nУчастники:\n"
            for _, username, full_name in members:
                uname = f"@{username}" if username else full_name
                text += f"• {full_name} ({uname})\n"
        await callback.message.answer(text)


@dp.callback_query(F.data == "admin_notify")
async def admin_notify(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("Нет активных клубов", show_alert=True)
        return

    text = "🔔 *Выбери клуб для напоминания:*\n\nВведи номер клуба:\n\n"
    for c in clubs:
        registered = db.get_registered_count(c["id"])
        text += f"*{c['id']}* — {c['date']} {c['time']} | {c['topic']} ({c['level']}) | 👥 {registered} чел.\n"

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=cancel_kb())
    await state.set_state(NotifyClub.club_id)
    await callback.answer()


@dp.message(NotifyClub.club_id)
async def admin_notify_send(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Клуб не найден. Попробуй ещё раз.")
            return

        members = db.get_club_members(club_id)
        if not members:
            await state.clear()
            await message.answer("На этот клуб никто не записан.", reply_markup=admin_menu_kb())
            return

        await state.clear()
        sent = 0
        names = []

        for user_id, username, full_name in members:
            try:
                await bot.send_message(
                    user_id,
                    f"⏰ Напоминание!\n\n"
                    f"Скоро начинается Speaking Club!\n"
                    f"📅 {club['date']} в {club['time']}\n"
                    f"💬 Тема: {club['topic']}\n"
                    f"📊 Уровень: {club['level']}\n\n"
                    f"🔗 Ссылка: {club['meet_link']}"
                )
                sent += 1
                uname = f"@{username}" if username else full_name
                names.append(f"• {full_name} ({uname})")
            except Exception:
                pass

        members_text = "\n".join(names)
        await message.answer(
            f"✅ Напоминания отправлены!\n\n"
            f"📅 {club['date']} {club['time']} — {club['topic']}\n"
            f"👥 Отправлено: {sent} чел.\n\n"
            f"Кому:\n{members_text}",
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("Введи только цифру — номер клуба.")


@dp.callback_query(F.data == "admin_students")
async def admin_students(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    students = db.get_all_students()
    text = f"👥 *Все ученики ({len(students)} чел.):*\n\n"
    for user_id, username, full_name in students:
        uname = f"@{username}" if username else "нет username"
        text += f"• {full_name} ({uname})\n"
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "cancel_state")
async def cancel_state(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Отменено.", reply_markup=admin_menu_kb())
    await callback.answer()


# ══════════════════════════════════════════════
# 1. УДАЛИТЬ КЛУБ + уведомить участников
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_delete_club")
async def admin_delete_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("Нет активных клубов", show_alert=True)
        return

    text = "❌ *Выбери клуб для отмены:*\n\nВведи номер клуба:\n\n"
    for c in clubs:
        text += f"*{c['id']}* — {c['date']} {c['time']} | {c['topic']} ({c['level']})\n"

    await callback.message.answer(text, parse_mode="Markdown", reply_markup=cancel_kb())
    await state.set_state(DeleteClub.club_id)
    await callback.answer()


@dp.message(DeleteClub.club_id)
async def admin_delete_confirm(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Клуб не найден. Попробуй ещё раз или нажми Отмена.")
            return

        members = db.get_club_members(club_id)
        db.deactivate_club(club_id)
        await state.clear()

        # Уведомляем всех записавшихся
        notified = 0
        for user_id, _, full_name in members:
            try:
                await bot.send_message(
                    user_id,
                    f"😔 *Speaking Club отменён*\n\n"
                    f"📅 {club['date']} в {club['time']}\n"
                    f"💬 Тема: {club['topic']}\n\n"
                    f"Следи за новыми анонсами в группе!",
                    parse_mode="Markdown"
                )
                notified += 1
            except Exception:
                pass

        await message.answer(
            f"✅ Клуб отменён.\n"
            f"Уведомлено участников: {notified}",
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("Введи только цифру — номер клуба.")


# ══════════════════════════════════════════════
# 2. РАССЫЛКА ВСЕМ УЧЕНИКАМ
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "📢 *Рассылка всем ученикам*\n\n"
        "Напиши текст сообщения — он уйдёт всем кто когда-либо писал боту.\n"
        "Можно использовать *жирный* и _курсив_.",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(Broadcast.text)
    await callback.answer()


@dp.message(Broadcast.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    await state.clear()
    students = db.get_all_students()
    sent = 0
    failed = 0

    await message.answer(f"⏳ Отправляю {len(students)} ученикам...")

    for user_id, _, _ in students:
        try:
            await bot.send_message(user_id, message.text, parse_mode="Markdown")
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"Отправлено: {sent}\n"
        f"Не доставлено: {failed} (заблокировали бота)",
        reply_markup=admin_menu_kb()
    )


# ══════════════════════════════════════════════
# 3. ЕЖЕНЕДЕЛЬНАЯ ТЕМА ЧАТА
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_weekly_topic")
async def admin_weekly_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "📝 *Новая тема недели*\n\n"
        "Напиши текст темы — он будет опубликован в группе.\n\n"
        "Можно включить:\n"
        "• Тему для обсуждения\n"
        "• Новые слова\n"
        "• Задание для практики",
        parse_mode="Markdown",
        reply_markup=cancel_kb()
    )
    await state.set_state(WeeklyTopic.text)
    await callback.answer()


@dp.message(WeeklyTopic.text)
async def admin_weekly_send(message: Message, state: FSMContext):
    await state.clear()
    await bot.send_message(GROUP_ID, message.text, parse_mode="Markdown")
    await message.answer("✅ Тема недели опубликована в группе!", reply_markup=admin_menu_kb())


# ══════════════════════════════════════════════
# 4. СТАТИСТИКА
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    stats = db.get_stats()
    text = (
        f"📊 *Статистика школы*\n\n"
        f"👥 Всего учеников: *{stats['students']}*\n"
        f"🎤 Активных клубов: *{stats['active_clubs']}*\n"
        f"📝 Всего записей на клубы: *{stats['total_registrations']}*\n"
        f"🔗 Рефералов: *{stats['referrals']}*\n"
    )
    await callback.message.answer(text, parse_mode="Markdown", reply_markup=admin_menu_kb())
    await callback.answer()


# ══════════════════════════════════════════════
# 5. ЗАВЕРШИТЬ КЛУБ
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_close_clubs")
async def admin_close_clubs(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("Нет активных клубов", show_alert=True)
        return

    closed = 0
    for club in clubs:
        db.deactivate_club(club["id"])
        closed += 1

    await callback.message.answer(
        f"✅ Завершено клубов: {closed}\n"
        f"Они больше не показываются ученикам.",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()


# ══════════════════════════════════════════════
# Запуск
# ══════════════════════════════════════════════
async def main():
    db.init()
    logger.info("English School Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
