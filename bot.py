# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import CommandStart, Command, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, GROUP_ID, ADMIN_ID, ADMIN_IDS
from config import SPEAKING_CLUB_THREAD_ID, CHATTING_THREAD_ID, UPDATES_THREAD_ID
from keyboards import (
    main_menu_kb, main_menu_with_register_kb, back_kb,
    clubs_kb, club_detail_kb, confirm_kb,
    admin_menu_kb, cancel_kb,
    consent_kb, how_found_kb
)
from messages import WELCOME_MSG, WELCOME_NEW_MSG, RULES_MSG, SCHEDULE_MSG, CONTACTS_MSG, REGISTER_START_MSG
from database import Database
import sheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()


# ══════════════════════════════════════════════
# FSM состояния
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


class StudentRegister(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    email = State()
    how_found = State()
    how_found_other = State()
    consent = State()


# ══════════════════════════════════════════════
# ОНБОРДИНГ
# ══════════════════════════════════════════════

@dp.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def new_member(event: ChatMemberUpdated):
    if event.chat.id != GROUP_ID:
        return
    user = event.new_chat_member.user
    if user.is_bot:
        return

    db.add_student(user.id, user.username or "", user.full_name)
    sheets.add_student(user.id, user.username or "", user.full_name)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 New student: {user.full_name} (@{user.username})\n"
                f"ID: {user.id} | Total: {db.count_students()}"
            )
        except Exception:
            pass

    try:
        await bot.send_message(
            user.id,
            WELCOME_NEW_MSG.format(name=user.first_name),
            reply_markup=main_menu_with_register_kb()
        )
    except Exception:
        await bot.send_message(
            GROUP_ID,
            f"👋 {user.mention_html()}, welcome! "
            f"Write to me in private 👉 /start",
            parse_mode="HTML"
        )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != "private":
        bot_info = await bot.get_me()
        await message.reply(f"👋 Hi! Write to me in private 👉 @{bot_info.username}")
        return

    db.add_student(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name
    )
    sheets.add_student(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name
    )

    # Если ученик ещё не заполнял анкету — показываем кнопку регистрации
    has_profile = db.has_profile(message.from_user.id)
    if has_profile:
        await message.answer(
            WELCOME_MSG.format(name=message.from_user.first_name),
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer(
            WELCOME_NEW_MSG.format(name=message.from_user.first_name),
            reply_markup=main_menu_with_register_kb()
        )


# ── Навигация ──
@dp.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    has_profile = db.has_profile(callback.from_user.id)
    if has_profile:
        await callback.message.edit_text(
            WELCOME_MSG.format(name=callback.from_user.first_name),
            reply_markup=main_menu_kb()
        )
    else:
        await callback.message.edit_text(
            WELCOME_NEW_MSG.format(name=callback.from_user.first_name),
            reply_markup=main_menu_with_register_kb()
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


@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 *Lessons*\n\n"
        "We offer group and individual lessons!\n\n"
        "Interested? Write to our manager:\n"
        "@Tosha_petrolay\n\n"
        "She will help you choose the right format and schedule!",
        parse_mode="Markdown",
        reply_markup=back_kb()
    )
    await callback.answer()


# ══════════════════════════════════════════════
# РЕГИСТРАЦИЯ УЧЕНИКА
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "register_student")
async def register_student_start(callback: CallbackQuery, state: FSMContext):
    if db.has_profile(callback.from_user.id):
        await callback.answer("You have already registered!", show_alert=True)
        return
    await callback.message.edit_text(REGISTER_START_MSG, parse_mode="Markdown")
    await state.set_state(StudentRegister.first_name)
    await callback.answer()


@dp.message(StudentRegister.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("Great! Now enter your *last name*:", parse_mode="Markdown")
    await state.set_state(StudentRegister.last_name)


@dp.message(StudentRegister.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await message.answer("Your *phone number* (e.g. +7 999 123 45 67):", parse_mode="Markdown")
    await state.set_state(StudentRegister.phone)


@dp.message(StudentRegister.phone)
async def reg_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("Your *email address*:", parse_mode="Markdown")
    await state.set_state(StudentRegister.email)


@dp.message(StudentRegister.email)
async def reg_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer(
        "How did you hear about us?",
        reply_markup=how_found_kb()
    )
    await state.set_state(StudentRegister.how_found)


@dp.callback_query(StudentRegister.how_found, F.data.startswith("found_"))
async def reg_how_found(callback: CallbackQuery, state: FSMContext):
    options = {
        "found_ad": "Advertisement",
        "found_friends": "Friends",
        "found_teacher": "Teacher",
        "found_other": None
    }
    choice = options.get(callback.data)
    if choice is None:
        await callback.message.edit_text("Please write how you heard about us:")
        await state.set_state(StudentRegister.how_found_other)
    else:
        await state.update_data(how_found=choice)
        await show_consent(callback.message, state)
    await callback.answer()


@dp.message(StudentRegister.how_found_other)
async def reg_how_found_other(message: Message, state: FSMContext):
    await state.update_data(how_found=message.text.strip())
    await show_consent(message, state)


async def show_consent(message_or_obj, state: FSMContext):
    text = (
        "Almost done! 🎉\n\n"
        "By clicking *I agree*, you consent to the processing of your personal data "
        "(name, phone, email) for the purpose of organizing English classes.\n\n"
        "Your data will not be shared with third parties."
    )
    if hasattr(message_or_obj, 'edit_text'):
        await message_or_obj.edit_text(text, parse_mode="Markdown", reply_markup=consent_kb())
    else:
        await message_or_obj.answer(text, parse_mode="Markdown", reply_markup=consent_kb())
    await state.set_state(StudentRegister.consent)


@dp.callback_query(StudentRegister.consent, F.data == "consent_agree")
async def reg_consent(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    user = callback.from_user
    db.add_profile(
        user_id=user.id,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        how_found=data.get("how_found", "")
    )
    sheets.update_student_profile(
        user_id=user.id,
        first_name=data.get("first_name", ""),
        last_name=data.get("last_name", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        how_found=data.get("how_found", "")
    )

    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📋 New student profile!\n\n"
                f"👤 {data.get('first_name')} {data.get('last_name')}\n"
                f"📱 {data.get('phone')}\n"
                f"📧 {data.get('email')}\n"
                f"📢 Found us via: {data.get('how_found')}\n"
                f"TG: @{user.username or user.full_name}"
            )
        except Exception:
            pass

    await callback.message.edit_text(
        "🎉 *Registration complete!*\n\n"
        "Welcome to our English Club! Now you have access to all features.",
        parse_mode="Markdown",
        reply_markup=main_menu_kb()
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
            "😔 No Speaking Clubs available right now.\nFollow the announcements in the group!",
            reply_markup=back_kb()
        )
    else:
        await callback.message.edit_text(
            "🎤 Choose a Speaking Club:",
            reply_markup=clubs_kb(clubs)
        )
    await callback.answer()


@dp.callback_query(F.data.startswith("club_"))
async def show_club_detail(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    club = db.get_club(club_id)
    if not club:
        await callback.answer("Club not found", show_alert=True)
        return

    spots_left = club["max_spots"] - club["registered"]
    already = db.is_registered(callback.from_user.id, club_id)

    text = (
        f"🎤 Speaking Club\n\n"
        f"📅 Date: {club['date']}\n"
        f"🕐 Time: {club['time']}\n"
        f"💬 Topic: {club['topic']}\n"
        f"📊 Level: {club['level']}\n"
        f"👥 Spots left: {spots_left} of {club['max_spots']}"
    )
    if already:
        text += "\n\n✅ You are already registered for this club!"

    await callback.message.edit_text(
        text,
        reply_markup=club_detail_kb(club_id, spots_left, already)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("register_") & ~F.data.startswith("register_student"))
async def register_confirm(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    club = db.get_club(club_id)
    await callback.message.edit_text(
        f"Confirm registration:\n\n"
        f"📅 {club['date']} at {club['time']}\n"
        f"💬 Topic: {club['topic']}\n"
        f"📊 Level: {club['level']}",
        reply_markup=confirm_kb(club_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_"))
async def register_done(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    user = callback.from_user

    if db.get_spots_left(club_id) <= 0:
        await callback.answer("😔 No spots left!", show_alert=True)
        return
    if db.is_registered(user.id, club_id):
        await callback.answer("You are already registered!", show_alert=True)
        return

    db.register(user.id, user.username or "", user.full_name, club_id)
    club = db.get_club(club_id)
    registered = db.get_registered_count(club_id)
    sheets.add_registration(
        user.id, user.username or "", user.full_name,
        club_id, club["date"], club["time"], club["topic"]
    )

    await callback.message.edit_text(
        f"🎉 You're registered!\n\n"
        f"📅 {club['date']} at {club['time']}\n"
        f"💬 Topic: {club['topic']}\n"
        f"📊 Level: {club['level']}\n\n"
        f"⏰ We'll send you a reminder with the Google Meet link before the club.\n"
        f"To cancel: /cancel_{club_id}",
        reply_markup=back_kb()
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 New Speaking Club registration!\n"
                f"👤 {user.full_name} (@{user.username})\n"
                f"📅 {club['date']} {club['time']} — {club['topic']}\n"
                f"👥 Registered: {registered}/{club['max_spots']}"
            )
        except Exception:
            pass
    await callback.answer()


@dp.callback_query(F.data.in_({"already", "no_spots"}))
async def stub_callbacks(callback: CallbackQuery):
    await callback.answer()


@dp.message(F.text.startswith("/cancel_"))
async def cancel_registration(message: Message):
    try:
        club_id = int(message.text.split("_")[1])
        db.unregister(message.from_user.id, club_id)
        await message.answer("❌ Registration cancelled. See you at the next club!")
    except Exception:
        await message.answer("Could not cancel registration.")


# ══════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ
# ══════════════════════════════════════════════

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⚙️ Admin panel:", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_create")
async def admin_create_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("📅 Enter club date\nExample: June 20, 2025", reply_markup=cancel_kb())
    await state.set_state(CreateClub.date)
    await callback.answer()


@dp.message(CreateClub.date)
async def get_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("🕐 Enter time\nExample: 7:00 PM MSK")
    await state.set_state(CreateClub.time)


@dp.message(CreateClub.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("💬 Enter club topic\nExample: Travel & Holidays")
    await state.set_state(CreateClub.topic)


@dp.message(CreateClub.topic)
async def get_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("📊 Enter level\nExample: A1 / A2 / A1+A2")
    await state.set_state(CreateClub.level)


@dp.message(CreateClub.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("🔗 Enter Google Meet link")
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
        f"🎤 New Speaking Club!\n\n"
        f"📅 Date: {data['date']}\n"
        f"🕐 Time: {data['time']}\n"
        f"💬 Topic: {data['topic']}\n"
        f"📊 Level: {data['level']}\n"
        f"👥 Spots: 8\n\n"
        f"Write to the bot /start and tap 🎤 Speaking Club to register!"
    )
    # Анонс в топик Speaking Clubs
    await bot.send_message(
        GROUP_ID, announce,
        message_thread_id=SPEAKING_CLUB_THREAD_ID
    )
    await message.answer(f"✅ Club created! Announcement sent to Speaking Clubs topic.\nClub ID: {club_id}")


@dp.callback_query(F.data == "admin_list")
async def admin_list_clubs(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.message.answer("No active clubs")
        return

    for c in clubs:
        registered = db.get_registered_count(c["id"])
        members = db.get_club_members(c["id"])
        text = (
            f"📅 {c['date']} {c['time']}\n"
            f"💬 {c['topic']} ({c['level']})\n"
            f"👥 {registered}/{c['max_spots']} registered\n"
        )
        if members:
            text += "\nParticipants:\n"
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
        await callback.answer("No active clubs", show_alert=True)
        return

    text = "🔔 Choose club for reminder:\n\nEnter club number:\n\n"
    for c in clubs:
        registered = db.get_registered_count(c["id"])
        text += f"{c['id']} — {c['date']} {c['time']} | {c['topic']} ({c['level']}) | 👥 {registered}\n"

    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(NotifyClub.club_id)
    await callback.answer()


@dp.message(NotifyClub.club_id)
async def admin_notify_send(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Club not found. Try again.")
            return

        members = db.get_club_members(club_id)
        if not members:
            await state.clear()
            await message.answer("No one registered for this club.", reply_markup=admin_menu_kb())
            return

        await state.clear()
        sent = 0
        names = []

        for user_id, username, full_name in members:
            try:
                await bot.send_message(
                    user_id,
                    f"⏰ Reminder!\n\n"
                    f"Speaking Club starts soon!\n"
                    f"📅 {club['date']} at {club['time']}\n"
                    f"💬 Topic: {club['topic']}\n"
                    f"📊 Level: {club['level']}\n\n"
                    f"🔗 Link: {club['meet_link']}"
                )
                sent += 1
                uname = f"@{username}" if username else full_name
                names.append(f"• {full_name} ({uname})")
            except Exception:
                pass

        members_text = "\n".join(names)
        await message.answer(
            f"✅ Reminders sent!\n\n"
            f"📅 {club['date']} {club['time']} — {club['topic']}\n"
            f"👥 Sent to: {sent}\n\n"
            f"Who received:\n{members_text}",
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("Enter only a number — club ID.")


@dp.callback_query(F.data == "admin_students")
async def admin_students(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    students = db.get_all_students()
    if not students:
        await callback.message.answer("No students yet.")
        return
    text = f"👥 All students ({len(students)}):\n\n"
    for user_id, username, full_name in students:
        uname = f"@{username}" if username else "no username"
        text += f"• {full_name} ({uname})\n"
    await callback.message.answer(text)


@dp.callback_query(F.data == "admin_profiles")
async def admin_profiles(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    profiles = db.get_all_profiles()
    if not profiles:
        await callback.message.answer("No student profiles yet.")
        return
    text = f"📋 Student profiles ({len(profiles)}):\n\n"
    for p in profiles:
        text += f"• {p[1]} {p[2]} | {p[3]} | {p[4]} | {p[5]}\n"
    await callback.message.answer(text)


@dp.callback_query(F.data == "cancel_state")
async def cancel_state(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Cancelled.", reply_markup=admin_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "admin_delete_club")
async def admin_delete_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("No active clubs", show_alert=True)
        return

    text = "❌ Choose club to cancel:\n\nEnter club number:\n\n"
    for c in clubs:
        text += f"{c['id']} — {c['date']} {c['time']} | {c['topic']} ({c['level']})\n"

    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(DeleteClub.club_id)
    await callback.answer()


@dp.message(DeleteClub.club_id)
async def admin_delete_confirm(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Club not found. Try again or press Cancel.")
            return

        members = db.get_club_members(club_id)
        db.deactivate_club(club_id)
        await state.clear()

        notified = 0
        for user_id, _, full_name in members:
            try:
                await bot.send_message(
                    user_id,
                    f"😔 Speaking Club cancelled\n\n"
                    f"📅 {club['date']} at {club['time']}\n"
                    f"💬 Topic: {club['topic']}\n\n"
                    f"Follow new announcements in the group!"
                )
                notified += 1
            except Exception:
                pass

        await message.answer(
            f"✅ Club cancelled.\n"
            f"Notified participants: {notified}",
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("Enter only a number — club ID.")


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "📢 Broadcast to all students\n\n"
        "Write your message — it will be sent to everyone who ever wrote to the bot.",
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

    await message.answer(f"⏳ Sending to {len(students)} students...")

    for user_id, _, _ in students:
        try:
            await bot.send_message(user_id, message.text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Broadcast complete!\n"
        f"Sent: {sent}\n"
        f"Failed: {failed}",
        reply_markup=admin_menu_kb()
    )


@dp.callback_query(F.data == "admin_weekly_topic")
async def admin_weekly_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "📝 New weekly topic\n\n"
        "Write the topic text — it will be posted in the Chatting topic.\n\n"
        "You can include:\n"
        "• Discussion topic\n"
        "• New vocabulary\n"
        "• Practice task",
        reply_markup=cancel_kb()
    )
    await state.set_state(WeeklyTopic.text)
    await callback.answer()


@dp.message(WeeklyTopic.text)
async def admin_weekly_send(message: Message, state: FSMContext):
    await state.clear()
    # Отправляем в топик Chatting
    await bot.send_message(
        GROUP_ID, message.text,
        message_thread_id=CHATTING_THREAD_ID
    )
    await message.answer("✅ Weekly topic posted in Chatting!", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    stats = db.get_stats()
    text = (
        f"📊 School Statistics\n\n"
        f"👥 Total students (bot): {stats['students']}\n"
        f"📋 Registered profiles: {stats['profiles']}\n"
        f"🎤 Active clubs: {stats['active_clubs']}\n"
        f"📝 Total club registrations: {stats['total_registrations']}\n"
    )
    await callback.message.answer(text, reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_close_clubs")
async def admin_close_clubs(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("No active clubs", show_alert=True)
        return

    closed = 0
    for club in clubs:
        db.deactivate_club(club["id"])
        closed += 1

    await callback.message.answer(
        f"✅ Closed {closed} clubs.\n"
        f"They no longer appear to students.",
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
