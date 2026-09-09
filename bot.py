# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import CommandStart, Command, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, GROUP_ID, ADMIN_ID, ADMIN_IDS
from config import SPEAKING_CLUB_THREAD_ID, CHATTING_THREAD_ID, UPDATES_THREAD_ID
from config import FEEDBACK_THREAD_ID, SONG_QUIZ_THREAD_ID, BOOK_CLUB_THREAD_ID
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

# Топики для отслеживания активности
ACTIVITY_THREADS = [362, 6, 120]

# ══════════════════════════════════════════════
# МОДЕРАЦИЯ + СЧЁТЧИК АКТИВНОСТИ
# ══════════════════════════════════════════════

BANNED_WORDS = [
    "spam", "реклама", "казино", "крипта", "заработок",
    "суки", "твари", "блять", "блядь", "сука", "тварь",
    "suki", "blyad", "tvar",
]

MODERATED_THREADS = [CHATTING_THREAD_ID, FEEDBACK_THREAD_ID]


@dp.message(F.chat.id == GROUP_ID)
async def handle_group_message(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return

    thread_id = message.message_thread_id

    # Считаем активность в нужных топиках
    if thread_id in ACTIVITY_THREADS:
        db.record_topic_activity(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name,
            thread_id
        )

    # Модерация
    if thread_id in MODERATED_THREADS:
        if message.from_user.id in ADMIN_IDS:
            return
        if not message.text:
            return
        text_lower = message.text.lower()
        for word in BANNED_WORDS:
            if word.lower() in text_lower:
                try:
                    await message.delete()
                    await bot.send_message(
                        message.from_user.id,
                        "Your message was deleted.\n\n"
                        "Please keep the conversation respectful and on-topic.\n"
                        "If you have questions, contact @Tosha_petrolay"
                    )
                except Exception:
                    pass
                return


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

class MessageStudent(StatesGroup):
    username = State()
    text = State()

class MessageCohort(StatesGroup):
    cohort = State()
    text = State()

class MarkAttendance(StatesGroup):
    club_id = State()
    marking = State()


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
                f"New student: {user.full_name} (@{user.username})\n"
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
            f"👋 {user.mention_html()}, welcome! Write to me in private 👉 /start",
            parse_mode="HTML"
        )


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != "private":
        bot_info = await bot.get_me()
        await message.reply(f"👋 Hi! Write to me in private 👉 @{bot_info.username}")
        return

    db.add_student(message.from_user.id, message.from_user.username or "", message.from_user.full_name)
    sheets.add_student(message.from_user.id, message.from_user.username or "", message.from_user.full_name)

    has_profile = db.has_profile(message.from_user.id)
    if has_profile:
        await message.answer(WELCOME_MSG.format(name=message.from_user.first_name), reply_markup=main_menu_kb())
    else:
        await message.answer(WELCOME_NEW_MSG.format(name=message.from_user.first_name), reply_markup=main_menu_with_register_kb())


@dp.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    has_profile = db.has_profile(callback.from_user.id)
    if has_profile:
        await callback.message.edit_text(WELCOME_MSG.format(name=callback.from_user.first_name), reply_markup=main_menu_kb())
    else:
        await callback.message.edit_text(WELCOME_NEW_MSG.format(name=callback.from_user.first_name), reply_markup=main_menu_with_register_kb())
    await callback.answer()


@dp.callback_query(F.data == "rules")
async def show_rules(callback: CallbackQuery):
    await callback.message.edit_text(RULES_MSG, reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "schedule")
async def show_schedule(callback: CallbackQuery):
    await callback.message.edit_text(SCHEDULE_MSG, reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "contacts")
async def show_contacts(callback: CallbackQuery):
    await callback.message.edit_text(CONTACTS_MSG, reply_markup=back_kb())
    await callback.answer()


@dp.callback_query(F.data == "lessons")
async def show_lessons(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 Lessons\n\n"
        "We offer lessons for all levels:\n\n"
        "👥 Group lessons: A1, A2, B1, B2, C1\n"
        "👤 Individual lessons: any level and goal\n"
        "📝 Exam prep: OGE, EGE\n"
        "🎓 IELTS preparation\n\n"
        "Write to our manager to find the right option:\n"
        "@Tosha_petrolay",
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
    await callback.message.edit_text(REGISTER_START_MSG)
    await state.set_state(StudentRegister.first_name)
    await callback.answer()


@dp.message(StudentRegister.first_name)
async def reg_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip())
    await message.answer("Great! Now enter your last name:")
    await state.set_state(StudentRegister.last_name)


@dp.message(StudentRegister.last_name)
async def reg_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip())
    await message.answer("Your phone number (e.g. +7 999 123 45 67):")
    await state.set_state(StudentRegister.phone)


@dp.message(StudentRegister.phone)
async def reg_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("Your email address:")
    await state.set_state(StudentRegister.email)


@dp.message(StudentRegister.email)
async def reg_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer("How did you hear about us?", reply_markup=how_found_kb())
    await state.set_state(StudentRegister.how_found)


@dp.callback_query(StudentRegister.how_found, F.data.startswith("found_"))
async def reg_how_found(callback: CallbackQuery, state: FSMContext):
    options = {"found_ad": "Advertisement", "found_friends": "Friends", "found_teacher": "Teacher", "found_other": None}
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
        "Almost done!\n\n"
        "By clicking I agree, you consent to the processing of your personal data "
        "(name, phone, email) for the purpose of organizing English classes.\n\n"
        "Your data will not be shared with third parties."
    )
    if hasattr(message_or_obj, 'edit_text'):
        await message_or_obj.edit_text(text, reply_markup=consent_kb())
    else:
        await message_or_obj.answer(text, reply_markup=consent_kb())
    await state.set_state(StudentRegister.consent)


@dp.callback_query(StudentRegister.consent, F.data == "consent_agree")
async def reg_consent(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    user = callback.from_user

    db.add_profile(user_id=user.id, first_name=data.get("first_name", ""),
                   last_name=data.get("last_name", ""), phone=data.get("phone", ""),
                   email=data.get("email", ""), how_found=data.get("how_found", ""))
    sheets.update_student_profile(user_id=user.id, first_name=data.get("first_name", ""),
                                   last_name=data.get("last_name", ""), phone=data.get("phone", ""),
                                   email=data.get("email", ""), how_found=data.get("how_found", ""))

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"New student profile!\n\n"
                f"Name: {data.get('first_name')} {data.get('last_name')}\n"
                f"Phone: {data.get('phone')}\n"
                f"Email: {data.get('email')}\n"
                f"Found us via: {data.get('how_found')}\n"
                f"TG: @{user.username or user.full_name}"
            )
        except Exception:
            pass

    await callback.message.edit_text(
        "Registration complete!\n\nWelcome to our English Club!",
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
        await callback.message.edit_text("No Speaking Clubs available right now.\nFollow the announcements in the group!", reply_markup=back_kb())
    else:
        await callback.message.edit_text("Choose a Speaking Club:", reply_markup=clubs_kb(clubs))
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
    text = (f"Speaking Club\n\nDate: {club['date']}\nTime: {club['time']}\n"
            f"Topic: {club['topic']}\nLevel: {club['level']}\nSpots left: {spots_left} of {club['max_spots']}")
    if already:
        text += "\n\nYou are already registered!"

    await callback.message.edit_text(text, reply_markup=club_detail_kb(club_id, spots_left, already))
    await callback.answer()


@dp.callback_query(F.data.startswith("register_") & ~F.data.startswith("register_student"))
async def register_confirm(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    club = db.get_club(club_id)
    await callback.message.edit_text(
        f"Confirm registration:\n\nDate: {club['date']} at {club['time']}\nTopic: {club['topic']}\nLevel: {club['level']}",
        reply_markup=confirm_kb(club_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_"))
async def register_done(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    user = callback.from_user

    if db.get_spots_left(club_id) <= 0:
        await callback.answer("No spots left!", show_alert=True)
        return
    if db.is_registered(user.id, club_id):
        await callback.answer("You are already registered!", show_alert=True)
        return

    db.register(user.id, user.username or "", user.full_name, club_id)
    club = db.get_club(club_id)
    registered = db.get_registered_count(club_id)
    sheets.add_registration(user.id, user.username or "", user.full_name, club_id, club["date"], club["time"], club["topic"])

    await callback.message.edit_text(
        f"You are registered!\n\nDate: {club['date']} at {club['time']}\n"
        f"Topic: {club['topic']}\nLevel: {club['level']}\n\n"
        f"We will send you a reminder with the link before the club.\nTo cancel: /cancel_{club_id}",
        reply_markup=back_kb()
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"New Speaking Club registration!\n"
                f"Name: {user.full_name} (@{user.username})\n"
                f"Date: {club['date']} {club['time']} - {club['topic']}\n"
                f"Registered: {registered}/{club['max_spots']}")
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
        await message.answer("Registration cancelled. See you at the next club!")
    except Exception:
        await message.answer("Could not cancel registration.")


# ══════════════════════════════════════════════
# АДМИН-ПАНЕЛЬ
# ══════════════════════════════════════════════

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Admin panel:", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_create")
async def admin_create_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("Enter club date\nExample: 20 August 2025", reply_markup=cancel_kb())
    await state.set_state(CreateClub.date)
    await callback.answer()


@dp.message(CreateClub.date)
async def get_date(message: Message, state: FSMContext):
    await state.update_data(date=message.text)
    await message.answer("Enter time\nExample: 7:00 PM MSK")
    await state.set_state(CreateClub.time)


@dp.message(CreateClub.time)
async def get_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)
    await message.answer("Enter club topic\nExample: Travel & Holidays")
    await state.set_state(CreateClub.topic)


@dp.message(CreateClub.topic)
async def get_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("Enter level\nExample: A1 / A2 / B1")
    await state.set_state(CreateClub.level)


@dp.message(CreateClub.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Enter meeting link (Google Meet / Zoom / Telemost)")
    await state.set_state(CreateClub.meet_link)


@dp.message(CreateClub.meet_link)
async def get_meet_link(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    club_id = db.create_club(date=data["date"], time=data["time"], topic=data["topic"],
                              level=data["level"], meet_link=message.text, max_spots=8)
    sheets.add_club(club_id, data["date"], data["time"], data["topic"], data["level"])

    announce = (f"New Speaking Club!\n\nDate: {data['date']}\nTime: {data['time']}\n"
                f"Topic: {data['topic']}\nLevel: {data['level']}\nSpots: 8\n\n"
                f"Write to the bot /start and tap Speaking Club to register!")

    await bot.send_message(GROUP_ID, announce, message_thread_id=SPEAKING_CLUB_THREAD_ID)
    await bot.send_message(GROUP_ID, announce, message_thread_id=UPDATES_THREAD_ID)
    await message.answer(f"Club created! Announcement sent to Speaking Clubs and Announcements.\nClub ID: {club_id}")


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
        text = f"ID:{c['id']} | {c['date']} {c['time']}\nTopic: {c['topic']} ({c['level']})\nRegistered: {registered}/{c['max_spots']}\n"
        if members:
            text += "\nParticipants:\n"
            for _, username, full_name in members:
                uname = f"@{username}" if username else full_name
                text += f"- {full_name} ({uname})\n"
        await callback.message.answer(text)


@dp.callback_query(F.data == "admin_notify")
async def admin_notify(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("No active clubs", show_alert=True)
        return

    text = "Choose club for reminder:\n\nEnter club ID:\n\n"
    for c in clubs:
        registered = db.get_registered_count(c["id"])
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']} | {registered} registered\n"

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
                await bot.send_message(user_id,
                    f"Reminder!\n\nSpeaking Club starts soon!\n"
                    f"Date: {club['date']} at {club['time']}\n"
                    f"Topic: {club['topic']}\nLevel: {club['level']}\n\n"
                    f"Link: {club['meet_link']}")
                sent += 1
                uname = f"@{username}" if username else full_name
                names.append(f"- {full_name} ({uname})")
            except Exception:
                pass

        await message.answer(
            f"Reminders sent!\n\n{club['date']} {club['time']} - {club['topic']}\n"
            f"Sent to: {sent}\n\nWho received:\n" + "\n".join(names),
            reply_markup=admin_menu_kb()
        )
    except ValueError:
        await message.answer("Enter only a number - club ID.")


# ── Посещаемость ──
@dp.callback_query(F.data == "admin_attendance")
async def admin_attendance_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.answer("No active clubs", show_alert=True)
        return

    text = "Mark attendance:\n\nEnter club ID:\n\n"
    for c in clubs:
        registered = db.get_registered_count(c["id"])
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']} | {registered} registered\n"

    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(MarkAttendance.club_id)
    await callback.answer()


@dp.message(MarkAttendance.club_id)
async def admin_attendance_club(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Club not found.")
            return

        members = db.get_club_members(club_id)
        if not members:
            await state.clear()
            await message.answer("No one registered for this club.", reply_markup=admin_menu_kb())
            return

        await state.update_data(club_id=club_id)
        text = f"Club: {club['date']} {club['time']} - {club['topic']}\n\n"
        text += "Who attended? Enter usernames separated by commas\n(or 'all' if everyone came):\n\n"
        for _, username, full_name in members:
            uname = f"@{username}" if username else full_name
            text += f"- {full_name} ({uname})\n"

        await message.answer(text, reply_markup=cancel_kb())
        await state.set_state(MarkAttendance.marking)
    except ValueError:
        await message.answer("Enter only a number - club ID.")


@dp.message(MarkAttendance.marking)
async def admin_attendance_mark(message: Message, state: FSMContext):
    data = await state.get_data()
    club_id = data["club_id"]
    club = db.get_club(club_id)
    members = db.get_club_members(club_id)
    await state.clear()

    if message.text.strip().lower() == "all":
        for user_id, _, _ in members:
            db.mark_attended(user_id, club_id)
        await message.answer(f"All {len(members)} participants marked as attended!", reply_markup=admin_menu_kb())
        return

    attended_usernames = [u.strip().lstrip("@").lower() for u in message.text.split(",")]
    marked = 0
    for user_id, username, full_name in members:
        if username and username.lower() in attended_usernames:
            db.mark_attended(user_id, club_id)
            marked += 1

    not_attended = db.get_not_attended(club_id)
    text = f"Attendance marked!\nAttended: {marked}\nDid not come: {len(not_attended)}\n"
    if not_attended:
        text += "\nDid not attend:\n"
        for _, username, full_name in not_attended:
            uname = f"@{username}" if username else full_name
            text += f"- {full_name} ({uname})\n"

    await message.answer(text, reply_markup=admin_menu_kb())


# ── Написать конкретному ученику ──
@dp.callback_query(F.data == "admin_message_student")
async def admin_message_student_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "Enter student username (with or without @):",
        reply_markup=cancel_kb()
    )
    await state.set_state(MessageStudent.username)
    await callback.answer()


@dp.message(MessageStudent.username)
async def admin_message_student_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    student = db.get_student_by_username(username)
    if not student:
        await message.answer(f"Student @{username} not found. Check the username and try again.")
        return
    await state.update_data(student_id=student[0], student_name=student[2])
    await message.answer(f"Write your message to {student[2]} (@{username}):", reply_markup=cancel_kb())
    await state.set_state(MessageStudent.text)


@dp.message(MessageStudent.text)
async def admin_message_student_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(data["student_id"], message.text)
        await message.answer(f"Message sent to {data['student_name']}!", reply_markup=admin_menu_kb())
    except Exception:
        await message.answer("Could not send message. Student may have blocked the bot.", reply_markup=admin_menu_kb())


# ── Написать потоку ──
@dp.callback_query(F.data == "admin_message_cohort")
async def admin_message_cohort_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    cohorts = db.get_cohorts()
    if not cohorts:
        await callback.answer("No cohorts yet", show_alert=True)
        return

    text = "Choose cohort (enter date):\n\n"
    for c in cohorts:
        students = db.get_students_by_cohort(c)
        text += f"- Cohort {c}: {len(students)} students\n"

    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(MessageCohort.cohort)
    await callback.answer()


@dp.message(MessageCohort.cohort)
async def admin_message_cohort_select(message: Message, state: FSMContext):
    cohort = message.text.strip()
    students = db.get_students_by_cohort(cohort)
    if not students:
        await message.answer(f"Cohort {cohort} not found. Try again.")
        return
    await state.update_data(cohort=cohort, count=len(students))
    await message.answer(f"Write message for cohort {cohort} ({len(students)} students):", reply_markup=cancel_kb())
    await state.set_state(MessageCohort.text)


@dp.message(MessageCohort.text)
async def admin_message_cohort_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    students = db.get_students_by_cohort(data["cohort"])
    sent = 0
    failed = 0

    await message.answer(f"Sending to cohort {data['cohort']} ({len(students)} students)...")
    for user_id, _, _ in students:
        try:
            await bot.send_message(user_id, message.text)
            sent += 1
        except Exception:
            failed += 1

    await message.answer(f"Done!\nSent: {sent}\nFailed: {failed}", reply_markup=admin_menu_kb())


# ── Остальные админ функции ──
@dp.callback_query(F.data == "admin_students")
async def admin_students(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    students = db.get_all_students()
    if not students:
        await callback.message.answer("No students yet.")
        return
    text = f"All students ({len(students)}):\n\n"
    for user_id, username, full_name in students:
        uname = f"@{username}" if username else "no username"
        text += f"- {full_name} ({uname})\n"
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
    text = f"Student profiles ({len(profiles)}):\n\n"
    for p in profiles:
        text += f"- {p[1]} {p[2]} | {p[3]} | {p[4]} | {p[5]}\n"
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

    text = "Choose club to cancel:\n\nEnter club ID:\n\n"
    for c in clubs:
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']} ({c['level']})\n"

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
                await bot.send_message(user_id,
                    f"Speaking Club cancelled\n\nDate: {club['date']} at {club['time']}\n"
                    f"Topic: {club['topic']}\n\nFollow new announcements in the group!")
                notified += 1
            except Exception:
                pass

        await message.answer(f"Club cancelled.\nNotified: {notified} participants", reply_markup=admin_menu_kb())
    except ValueError:
        await message.answer("Enter only a number - club ID.")


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("Broadcast to all students\n\nWrite your message:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)
    await callback.answer()


@dp.message(Broadcast.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    await state.clear()
    students = db.get_all_students()
    sent = 0
    failed = 0
    await message.answer(f"Sending to {len(students)} students...")
    for user_id, _, _ in students:
        try:
            await bot.send_message(user_id, message.text)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"Broadcast complete!\nSent: {sent}\nFailed: {failed}", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_weekly_topic")
async def admin_weekly_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("New weekly topic\n\nWrite the text - it will be posted in Chatting:", reply_markup=cancel_kb())
    await state.set_state(WeeklyTopic.text)
    await callback.answer()


@dp.message(WeeklyTopic.text)
async def admin_weekly_send(message: Message, state: FSMContext):
    await state.clear()
    await bot.send_message(GROUP_ID, message.text, message_thread_id=CHATTING_THREAD_ID)
    await message.answer("Weekly topic posted in Chatting!", reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    stats = db.get_stats()
    cohorts = db.get_cohorts()
    text = (
        f"School Statistics\n\n"
        f"Total students: {stats['students']}\n"
        f"Registered profiles: {stats['profiles']}\n"
        f"Active clubs: {stats['active_clubs']}\n"
        f"Total registrations: {stats['total_registrations']}\n"
        f"Cohorts: {len(cohorts)}\n"
    )
    if cohorts:
        text += "\nCohorts:\n"
        for c in cohorts:
            count = len(db.get_students_by_cohort(c))
            text += f"- {c}: {count} students\n"
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
    await callback.message.answer(f"Closed {clubs} clubs.", reply_markup=admin_menu_kb())
    await callback.answer()


# ══════════════════════════════════════════════
# ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ (воскресенье)
# ══════════════════════════════════════════════

async def send_weekly_report():
    """Отправляет отчёт каждое воскресенье"""
    clubs_this_week = db.get_clubs_this_week()
    active_in_topics = db.get_active_in_topics_this_week(ACTIVITY_THREADS)
    all_students = db.get_all_students()

    # Кто не писал в топики
    inactive = [(uid, uname, fname) for uid, uname, fname in all_students if uid not in active_in_topics]

    text = "Weekly Report\n\n"

    # Клубы
    if clubs_this_week:
        text += f"Speaking Clubs this week: {len(clubs_this_week)}\n\n"
        for club in clubs_this_week:
            not_attended = db.get_not_attended(club["id"])
            text += f"Club: {club['date']} {club['time']} - {club['topic']}\n"
            text += f"Registered: {club['registered']}/{club['max_spots']}\n"
            if not_attended:
                text += f"Did not attend ({len(not_attended)}):\n"
                for _, username, full_name in not_attended:
                    uname = f"@{username}" if username else full_name
                    text += f"  - {full_name} ({uname})\n"
            text += "\n"
    else:
        text += "No Speaking Clubs this week.\n\n"

    # Неактивные в топиках
    text += f"Not active in discussion topics this week: {len(inactive)}\n"
    if inactive:
        for _, username, full_name in inactive[:20]:  # максимум 20
            uname = f"@{username}" if username else full_name
            text += f"- {full_name} ({uname})\n"
        if len(inactive) > 20:
            text += f"... and {len(inactive) - 20} more\n"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


@dp.callback_query(F.data == "admin_weekly_report")
async def admin_weekly_report_manual(callback: CallbackQuery):
    """Ручной запуск отчёта"""
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.answer("Generating report...")
    await send_weekly_report()


# ══════════════════════════════════════════════
# Запуск
# ══════════════════════════════════════════════
async def main():
    db.init()

    # Планировщик для воскресного отчёта
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_weekly_report, "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.start()

    logger.info("English School Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
