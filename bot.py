# bot.py
import asyncio
from datetime import datetime
import logging
import random
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
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
    clubs_kb, club_detail_kb, confirm_kb, unregister_kb,
    admin_menu_kb, cancel_kb, consent_kb, how_found_kb
)
from messages import WELCOME_MSG, WELCOME_NEW_MSG, RULES_MSG, SCHEDULE_MSG, CONTACTS_MSG, REGISTER_START_MSG
from database import Database
import sheets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()

ACTIVITY_THREADS = [362, 6, 120]

SPEAKING_QUESTIONS = [
    "Do you live in a house or an apartment?",
    "What's your favorite color?",
    "Do you prefer to read books or watch movies?",
    "Do you like to cook?",
    "What's your favorite kind of music?",
    "Do you have any pets?",
    "Do you like to travel?",
    "What's your favorite time of year?",
    "Do you enjoy shopping?",
    "What do you usually do in your free time?",
    "Do you like to watch TV?",
    "Do you think it's important to learn a foreign language?",
    "Do you prefer to live in a big city or a small town?",
    "Do you like to go to the cinema?",
    "Do you think it's important to exercise regularly?",
    "Do you enjoy spending time outdoors?",
    "What's your favorite holiday?",
    "Do you prefer to read books or listen to audiobooks?",
    "Do you think it's important to learn about other cultures?",
    "Do you like to take photos?",
    "What's your favorite kind of weather?",
    "Do you enjoy playing any sports?",
    "Do you like to go to the beach?",
    "Do you think it's important to protect the environment?",
    "What's your favorite kind of food?",
    "Do you think it's important to learn about history?",
    "Do you prefer to study alone or in a group?",
    "Do you use the internet a lot?",
    "Do you like to play computer games?",
    "Do you enjoy going to the theater?",
    "Do you like to cook or order takeout?",
    "Do you prefer to drink coffee or tea?",
    "What's your favorite way to relax?",
    "Do you prefer the city or the countryside?",
    "What kind of movies do you enjoy?",
    "Do you like to try new foods?",
    "How often do you exercise?",
    "What's your favorite season and why?",
    "Do you like to spend time with family or friends more?",
    "What do you like to do on weekends?",
    "Do you prefer mornings or evenings?",
    "What's your favorite thing about your hometown?",
    "Do you like learning new things? What have you learned recently?",
    "What's one thing you would like to change about your daily routine?",
    "Do you think social media is good or bad? Why?",
    "What's the most interesting place you have ever visited?",
    "Do you prefer hot or cold weather?",
    "What's your favorite type of book?",
    "Do you think it's important to have hobbies? Why?",
    "What would you do if you had a day off tomorrow?",
]

pending_questions: dict[int, str] = {}


# ══════════════════════════════════════════════
# МОДЕРАЦИЯ + СЧЁТЧИК АКТИВНОСТИ
# ══════════════════════════════════════════════

BANNED_WORDS = [
    "spam", "реклама", "казино", "крипта", "заработок",
    "суки", "твари", "блять", "блядь", "сука", "тварь",
]
MODERATED_THREADS = [CHATTING_THREAD_ID, FEEDBACK_THREAD_ID]


@dp.message(F.chat.id == GROUP_ID)
async def handle_group_message(message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    thread_id = message.message_thread_id
    if thread_id in ACTIVITY_THREADS:
        db.record_topic_activity(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name,
            thread_id
        )
    if thread_id in MODERATED_THREADS:
        if message.from_user.id in ADMIN_IDS:
            return
        if not message.text:
            return
        for word in BANNED_WORDS:
            if word.lower() in message.text.lower():
                try:
                    await message.delete()
                    await bot.send_message(
                        message.from_user.id,
                        "Your message was deleted. Please keep the conversation respectful.\n"
                        "If you have questions, contact @Tosha_petrolay"
                    )
                except Exception:
                    pass
                return


# ══════════════════════════════════════════════
# FSM
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

class RestoreFromSheets(StatesGroup):
    confirm = State()

class MessageColdLeads(StatesGroup):
    text = State()


# ══════════════════════════════════════════════
# ПЕРЕПИСКА ЧЕРЕЗ БОТА (пункт 1)
# ══════════════════════════════════════════════

async def forward_to_admins(message: Message):
    user = message.from_user
    header = (
        f"Message from {user.full_name} (@{user.username or 'no username'})\n"
        f"ID: {user.id}\n"
        f"Reply with: /reply_{user.id} your text\n\n"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header)
            await message.forward(admin_id)
        except Exception as e:
            logger.error(f"Forward error: {e}")


@dp.message(F.chat.type == "private", F.text.startswith("/reply_"))
async def admin_reply_cmd(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("Usage: /reply_USER_ID your message text")
        return
    try:
        student_id = int(parts[0].replace("/reply_", ""))
        text = parts[1]
        await bot.send_message(student_id, f"Message from teacher:\n\n{text}")
        await message.answer("Message sent to student!")
    except Exception as e:
        await message.answer(f"Error: {e}")


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
            await bot.send_message(admin_id,
                f"New student: {user.full_name} (@{user.username})\n"
                f"ID: {user.id} | Total: {db.count_students()}")
        except Exception:
            pass
    try:
        await bot.send_message(user.id, WELCOME_NEW_MSG.format(name=user.first_name),
                               reply_markup=main_menu_with_register_kb())
    except Exception:
        await bot.send_message(GROUP_ID,
            f"Welcome {user.mention_html()}! Write to me in private /start",
            parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != "private":
        bot_info = await bot.get_me()
        await message.reply(f"Hi! Write to me in private: @{bot_info.username}")
        return
    db.add_student(message.from_user.id, message.from_user.username or "", message.from_user.full_name)
    sheets.add_student(message.from_user.id, message.from_user.username or "", message.from_user.full_name)
    has_profile = db.has_profile(message.from_user.id)
    if has_profile:
        await message.answer(WELCOME_MSG.format(name=message.from_user.first_name), reply_markup=main_menu_kb())
    else:
        await message.answer(WELCOME_NEW_MSG.format(name=message.from_user.first_name), reply_markup=main_menu_with_register_kb())


# ══════════════════════════════════════════════
# ВХОДЯЩИЕ СООБЩЕНИЯ ОТ СТУДЕНТОВ
# ══════════════════════════════════════════════

@dp.message(F.chat.type == "private")
async def handle_private_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        return
    current_state = await state.get_state()
    if current_state is not None:
        return

    await forward_to_admins(message)

    if user_id in pending_questions:
        question = pending_questions.pop(user_id)
        await message.answer(
            "Thank you! Your answer has been sent to the teacher.\n"
            "You will receive feedback soon!"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                    f"Student answer to practice question:\n\"{question}\"\n\n"
                    f"From: {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"To reply: /reply_{user_id} your text")
            except Exception:
                pass
    else:
        await message.answer("Your message has been forwarded to the teacher. We will reply soon!")


# ── Навигация ──
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
        "Lessons\n\nWe offer lessons for all levels:\n\n"
        "Group lessons: A1, A2, B1, B2, C1\n"
        "Individual lessons: any level and goal\n"
        "Exam prep: OGE, EGE\n"
        "IELTS preparation\n\n"
        "Write to our manager:\n@Tosha_petrolay",
        reply_markup=back_kb()
    )
    await callback.answer()


# ══════════════════════════════════════════════
# РАНДОМНАЯ ТЕМА (пункт 2)
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "random_question")
async def send_random_question(callback: CallbackQuery):
    question = random.choice(SPEAKING_QUESTIONS)
    user_id = callback.from_user.id
    pending_questions[user_id] = question
    await callback.message.edit_text(
        "Try it now - get free feedback!\n\n"
        f"Your question:\n\n{question}\n\n"
        "Answer in text or send a voice message directly to this chat.\n"
        "Our teacher will send you personal feedback!",
        reply_markup=back_kb()
    )
    await callback.answer()


# ══════════════════════════════════════════════
# РЕГИСТРАЦИЯ
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
    options = {
        "found_ad": "Advertisement",
        "found_friends": "Friends",
        "found_teacher": "Teacher",
        "found_social": "Social media",
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
        "Almost done!\n\n"
        "By clicking I agree, you consent to the processing of your personal data "
        "(name, phone, email) for organizing English classes.\n\n"
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
    db.assign_cohort(user.id)  # cohort только после регистрации
    sheets.update_student_profile(user_id=user.id, first_name=data.get("first_name", ""),
                                   last_name=data.get("last_name", ""), phone=data.get("phone", ""),
                                   email=data.get("email", ""), how_found=data.get("how_found", ""))
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"New student profile!\n\nName: {data.get('first_name')} {data.get('last_name')}\n"
                f"Phone: {data.get('phone')}\nEmail: {data.get('email')}\n"
                f"Found us via: {data.get('how_found')}\nTG: @{user.username or user.full_name}")
        except Exception:
            pass
    await callback.message.edit_text("Registration complete!\n\nWelcome to our English Club!", reply_markup=main_menu_kb())
    await callback.answer()


# ══════════════════════════════════════════════
# SPEAKING CLUB
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "show_clubs")
async def show_clubs(callback: CallbackQuery):
    clubs = db.get_active_clubs()
    if not clubs:
        await callback.message.edit_text("No Speaking Clubs available right now.\nFollow the announcements!", reply_markup=back_kb())
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
        reply_markup=confirm_kb(club_id))
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
    sheets.add_registration(user.id, user.username or "", user.full_name,
                            club_id, club["date"], club["time"], club["topic"])
    await callback.message.edit_text(
        f"You are registered!\n\nDate: {club['date']} at {club['time']}\n"
        f"Topic: {club['topic']}\nLevel: {club['level']}\n\n"
        f"We will send you a reminder before the club.\nTap below to cancel if needed.",
        reply_markup=unregister_kb(club_id))
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"New Speaking Club registration!\nName: {user.full_name} (@{user.username})\n"
                f"Date: {club['date']} {club['time']} - {club['topic']}\nRegistered: {registered}/{club['max_spots']}")
        except Exception:
            pass
    await callback.answer()


# ══════════════════════════════════════════════
# ВЫПИСАТЬСЯ ИЗ КЛУБА (пункт 3)
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "my_clubs")
async def show_my_clubs(callback: CallbackQuery):
    user_id = callback.from_user.id
    my_registrations = db.get_user_registrations(user_id)
    if not my_registrations:
        await callback.message.edit_text(
            "You are not registered for any Speaking Clubs.\nTap Speaking Club to see available clubs!",
            reply_markup=back_kb())
        await callback.answer()
        return
    buttons = []
    for club in my_registrations:
        label = f"{club['date']} {club['time']} - {club['topic']}"
        buttons.append([InlineKeyboardButton(text=f"Cancel: {label}", callback_data=f"unregister_{club['id']}")])
    buttons.append([InlineKeyboardButton(text="Back to menu", callback_data="back")])
    await callback.message.edit_text(
        "Your Speaking Club registrations:\n\nTap to cancel:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@dp.callback_query(F.data.startswith("unregister_"))
async def unregister_from_club(callback: CallbackQuery):
    club_id = int(callback.data.split("_")[1])
    user = callback.from_user
    if not db.is_registered(user.id, club_id):
        await callback.answer("You are not registered for this club.", show_alert=True)
        return
    club = db.get_club(club_id)
    db.unregister(user.id, club_id)
    await callback.message.edit_text(
        f"Registration cancelled.\n\nClub: {club['date']} at {club['time']}\nTopic: {club['topic']}\n\nSee you next time!",
        reply_markup=back_kb())
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"Student cancelled registration!\nName: {user.full_name} (@{user.username})\n"
                f"Club: {club['date']} {club['time']} - {club['topic']}\n"
                f"Spots left: {db.get_spots_left(club_id)}/{club['max_spots']}")
        except Exception:
            pass
    await callback.answer()


@dp.message(F.text.startswith("/cancel_"))
async def cancel_registration_cmd(message: Message):
    try:
        club_id = int(message.text.split("_")[1])
        club = db.get_club(club_id)
        db.unregister(message.from_user.id, club_id)
        await message.answer("Registration cancelled. See you next time!")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                    f"Student cancelled!\nName: {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"Club: {club['date']} {club['time']} - {club['topic']}")
            except Exception:
                pass
    except Exception:
        await message.answer("Could not cancel registration.")


@dp.callback_query(F.data.in_({"already", "no_spots"}))
async def stub_callbacks(callback: CallbackQuery):
    await callback.answer()


# ══════════════════════════════════════════════
# ВОССТАНОВЛЕНИЕ ИЗ SHEETS (пункт 5)
# ══════════════════════════════════════════════

@dp.callback_query(F.data == "admin_restore")
async def admin_restore_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer(
        "Restore students from Google Sheets?\n\n"
        "This will re-import all students from the sheet.\n"
        "Existing students will not be duplicated.\n\n"
        "Type YES to confirm:",
        reply_markup=cancel_kb())
    await state.set_state(RestoreFromSheets.confirm)
    await callback.answer()


@dp.message(RestoreFromSheets.confirm)
async def admin_restore_confirm(message: Message, state: FSMContext):
    if message.text.strip().upper() != "YES":
        await state.clear()
        await message.answer("Cancelled.", reply_markup=admin_menu_kb())
        return
    await state.clear()
    await message.answer("Restoring students from Google Sheets...")
    try:
        restored = sheets.restore_students(db)
        await message.answer(
            f"Restore complete!\nStudents restored: {restored}\nTotal in database: {db.count_students()}",
            reply_markup=admin_menu_kb())
    except Exception as e:
        await message.answer(f"Error during restore: {e}", reply_markup=admin_menu_kb())


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
    await message.answer("Enter meeting link")
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
    await message.answer(f"Club created! Announcement sent.\nClub ID: {club_id}")


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
                text += f"- {full_name} (@{username or 'no username'})\n"
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
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']} | {db.get_registered_count(c['id'])} registered\n"
    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(NotifyClub.club_id)
    await callback.answer()


@dp.message(NotifyClub.club_id)
async def admin_notify_send(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Club not found.")
            return
        members = db.get_club_members(club_id)
        if not members:
            await state.clear()
            await message.answer("No one registered.", reply_markup=admin_menu_kb())
            return
        await state.clear()
        sent = 0
        names = []
        for user_id, username, full_name in members:
            try:
                await bot.send_message(user_id,
                    f"Reminder!\n\nSpeaking Club starts soon!\n"
                    f"Date: {club['date']} at {club['time']}\nTopic: {club['topic']}\nLevel: {club['level']}\n\n"
                    f"Link: {club['meet_link']}")
                sent += 1
                names.append(f"- {full_name} (@{username or 'no username'})")
            except Exception:
                pass
        await message.answer(f"Reminders sent!\n{club['date']} - {club['topic']}\nSent to: {sent}\n\n" + "\n".join(names), reply_markup=admin_menu_kb())
    except ValueError:
        await message.answer("Enter only a number.")


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
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']}\n"
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
            await message.answer("No one registered.", reply_markup=admin_menu_kb())
            return
        await state.update_data(club_id=club_id)
        text = f"Club: {club['date']} {club['time']} - {club['topic']}\n\nWho attended? Enter usernames comma-separated\n(or 'all'):\n\n"
        for _, username, full_name in members:
            text += f"- {full_name} (@{username or 'no username'})\n"
        await message.answer(text, reply_markup=cancel_kb())
        await state.set_state(MarkAttendance.marking)
    except ValueError:
        await message.answer("Enter only a number.")


@dp.message(MarkAttendance.marking)
async def admin_attendance_mark(message: Message, state: FSMContext):
    data = await state.get_data()
    club_id = data["club_id"]
    members = db.get_club_members(club_id)
    await state.clear()
    if message.text.strip().lower() == "all":
        for user_id, _, _ in members:
            db.mark_attended(user_id, club_id)
        await message.answer(f"All {len(members)} marked as attended!", reply_markup=admin_menu_kb())
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
            text += f"- {full_name} (@{username or 'no username'})\n"
    await message.answer(text, reply_markup=admin_menu_kb())


@dp.callback_query(F.data == "admin_message_student")
async def admin_message_student_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.message.answer("Enter student username (with or without @):", reply_markup=cancel_kb())
    await state.set_state(MessageStudent.username)
    await callback.answer()


@dp.message(MessageStudent.username)
async def admin_message_student_username(message: Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    student = db.get_student_by_username(username)
    if not student:
        await message.answer(f"Student @{username} not found.")
        return
    await state.update_data(student_id=student[0], student_name=student[2])
    await message.answer(f"Write your message to {student[2]}:", reply_markup=cancel_kb())
    await state.set_state(MessageStudent.text)


@dp.message(MessageStudent.text)
async def admin_message_student_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        await bot.send_message(data["student_id"], f"Message from teacher:\n\n{message.text}")
        await message.answer(f"Message sent to {data['student_name']}!", reply_markup=admin_menu_kb())
    except Exception:
        await message.answer("Could not send. Student may have blocked the bot.", reply_markup=admin_menu_kb())


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
        count = len(db.get_students_by_cohort(c))
        text += f"- Cohort {c}: {count} students\n"
    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(MessageCohort.cohort)
    await callback.answer()


@dp.message(MessageCohort.cohort)
async def admin_message_cohort_select(message: Message, state: FSMContext):
    cohort = message.text.strip()
    students = db.get_students_by_cohort(cohort)
    if not students:
        await message.answer(f"Cohort {cohort} not found.")
        return
    await state.update_data(cohort=cohort)
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
        text += f"- {full_name} (@{username or 'no username'})\n"
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
async def cancel_state_handler(callback: CallbackQuery, state: FSMContext):
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
    text = "Cancel club:\n\nEnter club ID:\n\n"
    for c in clubs:
        text += f"ID:{c['id']} - {c['date']} {c['time']} | {c['topic']}\n"
    await callback.message.answer(text, reply_markup=cancel_kb())
    await state.set_state(DeleteClub.club_id)
    await callback.answer()


@dp.message(DeleteClub.club_id)
async def admin_delete_confirm(message: Message, state: FSMContext):
    try:
        club_id = int(message.text.strip())
        club = db.get_club(club_id)
        if not club:
            await message.answer("Club not found.")
            return
        members = db.get_club_members(club_id)
        db.deactivate_club(club_id)
        await state.clear()
        notified = 0
        for user_id, _, _ in members:
            try:
                await bot.send_message(user_id,
                    f"Speaking Club cancelled\n\nDate: {club['date']} at {club['time']}\n"
                    f"Topic: {club['topic']}\n\nFollow new announcements in the group!")
                notified += 1
            except Exception:
                pass
        await message.answer(f"Club cancelled.\nNotified: {notified} participants", reply_markup=admin_menu_kb())
    except ValueError:
        await message.answer("Enter only a number.")


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
    await callback.message.answer("New weekly topic\n\nWrite the text:", reply_markup=cancel_kb())
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
    text = (f"School Statistics\n\nTotal students: {stats['students']}\n"
            f"Registered profiles: {stats['profiles']}\n"
            f"Active clubs: {stats['active_clubs']}\n"
            f"Total registrations: {stats['total_registrations']}\n"
            f"Cohorts: {len(cohorts)}\n")
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
    for club in clubs:
        db.deactivate_club(club["id"])
    await callback.message.answer(f"Closed {len(clubs)} clubs.", reply_markup=admin_menu_kb())
    await callback.answer()


@dp.callback_query(F.data == "admin_weekly_report")
async def admin_weekly_report_manual(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    await callback.message.answer("Generating report...")
    await send_weekly_report()


@dp.callback_query(F.data == "admin_cold_leads")
async def admin_cold_leads(callback: CallbackQuery):
    """Показать список холодных клиентов"""
    if callback.from_user.id not in ADMIN_IDS:
        return
    await callback.answer()
    cold = db.get_unregistered_students()
    if not cold:
        await callback.message.answer("No cold leads! Everyone has registered.")
        return
    text = f"Cold leads ({len(cold)}) - signed up but no profile:\n\n"
    for user_id, username, full_name, joined_at in cold:
        uname = f"@{username}" if username else "no username"
        days_ago = (datetime.now() - datetime.fromisoformat(joined_at)).days
        text += f"- {full_name} ({uname}) - {days_ago} days ago\n"
    await callback.message.answer(text)


@dp.callback_query(F.data == "admin_message_cold")
async def admin_message_cold_start(callback: CallbackQuery, state: FSMContext):
    """Рассылка холодным клиентам"""
    if callback.from_user.id not in ADMIN_IDS:
        return
    cold = db.get_unregistered_students()
    if not cold:
        await callback.answer("No cold leads!", show_alert=True)
        return
    await callback.message.answer(
        f"Message to {len(cold)} cold leads:\n\nWrite your message or send /default for standard reminder:",
        reply_markup=cancel_kb()
    )
    await state.set_state(MessageColdLeads.text)
    await callback.answer()


@dp.message(MessageColdLeads.text)
async def admin_message_cold_send(message: Message, state: FSMContext):
    await state.clear()
    cold = db.get_unregistered_students()

    if message.text.strip() == "/default":
        text = (
            "Добрый день! Вы не зарегистрировались в нашем клубе.\n\n"
            "Предлагаю бесплатно попробовать получить фидбек нашего преподавателя - "
            "включи рандомайзер тем и ответь письменно или голосом, "
            "кнопка называется \"Try it now - get free feedback!\"\n\n"
            "А также ты можешь задать вопросы по клубу @Tosha_petrolay"
        )
    else:
        text = message.text

    sent = 0
    failed = 0
    await message.answer(f"Sending to {len(cold)} cold leads...")
    for user_id, _, _ in cold:
        try:
            await bot.send_message(user_id, text)
            sent += 1
        except Exception:
            failed += 1
    await message.answer(f"Done!\nSent: {sent}\nFailed: {failed}", reply_markup=admin_menu_kb())


async def send_weekly_report():
    clubs_this_week = db.get_clubs_this_week()
    active_in_topics = db.get_active_in_topics_this_week(ACTIVITY_THREADS)
    all_students = db.get_all_students()
    inactive = [(uid, uname, fname) for uid, uname, fname in all_students if uid not in active_in_topics]
    text = "Weekly Report\n\n"
    if clubs_this_week:
        text += f"Speaking Clubs this week: {len(clubs_this_week)}\n\n"
        for club in clubs_this_week:
            not_attended = db.get_not_attended(club["id"])
            text += f"Club: {club['date']} {club['time']} - {club['topic']}\nRegistered: {club['registered']}/{club['max_spots']}\n"
            if not_attended:
                text += f"Did not attend ({len(not_attended)}):\n"
                for _, username, full_name in not_attended:
                    text += f"  - {full_name} (@{username or 'no username'})\n"
            text += "\n"
    else:
        text += "No Speaking Clubs this week.\n\n"
    text += f"Not active in topics this week: {len(inactive)}\n"
    for _, username, full_name in inactive[:20]:
        text += f"- {full_name} (@{username or 'no username'})\n"
    if len(inactive) > 20:
        text += f"... and {len(inactive) - 20} more\n"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def send_reminder_to_cold_leads():
    """Автоматическое напоминание холодным клиентам через 3 дня"""
    cold = db.get_students_older_than_days(3)
    sent = 0
    for user_id, _, _ in cold:
        try:
            await bot.send_message(
                user_id,
                "Добрый день! Вы не зарегистрировались в нашем клубе.\n\n"
                "Предлагаю бесплатно попробовать получить фидбек нашего преподавателя - "
                "включи рандомайзер тем и ответь письменно или голосом, "
                "кнопка называется \"Try it now - get free feedback!\"\n\n"
                "А также ты можешь задать вопросы по клубу @Tosha_petrolay"
            )
            sent += 1
        except Exception:
            pass
    if sent > 0:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"Auto-reminder sent to {sent} cold leads.")
            except Exception:
                pass


async def main():
    db.init()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_weekly_report, "cron", day_of_week="sun", hour=20, minute=0)
    scheduler.add_job(send_reminder_to_cold_leads, "cron", hour=12, minute=0)
    scheduler.start()
    logger.info("English School Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
