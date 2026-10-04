# sheets.py
import gspread
import os
import json
import logging
from google.oauth2.service_account import Credentials
from datetime import datetime

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

STUDENTS_HEADER = ["Telegram ID", "Username", "Имя в TG", "Дата добавления",
                   "Имя", "Фамилия", "Телефон", "Email", "Откуда узнали"]


def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise RuntimeError("GOOGLE_CREDENTIALS is not set")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(sheet_name: str):
    client = get_client()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("SPREADSHEET_ID is not set")
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)


def add_student(user_id: int, username: str, full_name: str):
    try:
        sheet = get_sheet("Ученики")
        if not sheet.row_values(1):
            sheet.append_row(STUDENTS_HEADER)
        all_ids = sheet.col_values(1)
        if str(user_id) in all_ids:
            return
        sheet.append_row([
            str(user_id),
            f"@{username}" if username else "-",
            full_name,
            datetime.now().strftime("%d.%m.%Y %H:%M"),
            "", "", "", "", ""
        ])
    except Exception:
        logger.exception("Sheets error (add_student)")


def update_student_profile(user_id: int, first_name: str, last_name: str,
                           phone: str, email: str, how_found: str):
    """Обновляет анкету ученика в таблице"""
    try:
        sheet = get_sheet("Ученики")
        all_ids = sheet.col_values(1)
        if str(user_id) in all_ids:
            row = all_ids.index(str(user_id)) + 1
            # одним запросом вместо пяти
            sheet.update(range_name=f"E{row}:I{row}",
                         values=[[first_name, last_name, phone, email, how_found]])
        else:
            if not sheet.row_values(1):
                sheet.append_row(STUDENTS_HEADER)
            sheet.append_row([
                str(user_id), "-", "-",
                datetime.now().strftime("%d.%m.%Y %H:%M"),
                first_name, last_name, phone, email, how_found
            ])
    except Exception:
        logger.exception("Sheets error (update_student_profile)")


def add_club(club_id: int, date: str, time: str, topic: str, level: str):
    try:
        sheet = get_sheet("Клубы")
        if not sheet.row_values(1):
            sheet.append_row(["ID", "Дата", "Время", "Тема", "Уровень", "Записано"])
        sheet.append_row([str(club_id), date, time, topic, level, "0"])
    except Exception:
        logger.exception("Sheets error (add_club)")


def add_registration(user_id: int, username: str, full_name: str,
                     club_id: int, date: str, time: str, topic: str):
    try:
        sheet = get_sheet("Записи")
        if not sheet.row_values(1):
            sheet.append_row(["User ID", "Username", "Имя", "ID клуба",
                              "Дата клуба", "Время", "Тема", "Дата записи"])
        sheet.append_row([
            str(user_id),
            f"@{username}" if username else "-",
            full_name,
            str(club_id),
            date, time, topic,
            datetime.now().strftime("%d.%m.%Y %H:%M")
        ])
        # Обновляем счётчик
        clubs_sheet = get_sheet("Клубы")
        all_ids = clubs_sheet.col_values(1)
        if str(club_id) in all_ids:
            row = all_ids.index(str(club_id)) + 1
            current = clubs_sheet.cell(row, 6).value or "0"
            clubs_sheet.update_cell(row, 6, str(int(current) + 1))
    except Exception:
        logger.exception("Sheets error (add_registration)")


# ══════════════════════════════════════════════
# ВОССТАНОВЛЕНИЕ БАЗЫ ИЗ ТАБЛИЦЫ
# ══════════════════════════════════════════════

def _clean(value: str) -> str:
    value = (value or "").strip()
    return "" if value == "-" else value


def _parse_date(value: str) -> datetime:
    """'04.10.2026 23:42' -> datetime. Если дата битая — текущее время."""
    value = (value or "").strip()
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return datetime.now()


def restore_students(db) -> tuple[int, int]:
    """
    Читает лист 'Ученики' и восстанавливает учеников и анкеты в SQLite.
    Сохраняет исходную дату добавления из таблицы (важно для холодных клиентов).
    Возвращает (новых учеников, новых анкет).
    Ошибки не глушатся — их покажет бот и логи Railway.
    """
    sheet = get_sheet("Ученики")
    rows = sheet.get_all_values()
    logger.info("[restore] строк в листе 'Ученики' (с заголовком): %d", len(rows))

    students_added = 0
    profiles_added = 0
    skipped = 0

    for r in rows[1:]:  # пропускаем заголовок
        r = list(r) + [""] * (9 - len(r))
        raw_id = r[0].strip()
        if not raw_id.isdigit():
            skipped += 1
            continue

        user_id = int(raw_id)
        username = _clean(r[1]).lstrip("@")
        joined_at = _parse_date(r[3])
        first_name, last_name = _clean(r[4]), _clean(r[5])
        phone, email, how_found = _clean(r[6]), _clean(r[7]), _clean(r[8])
        full_name = _clean(r[2]) or f"{first_name} {last_name}".strip() or str(user_id)

        profile = None
        if any([first_name, last_name, phone, email]):
            profile = {
                "first_name": first_name, "last_name": last_name,
                "phone": phone, "email": email, "how_found": how_found,
            }

        s_added, p_added = db.restore_student(user_id, username, full_name, joined_at, profile)
        students_added += s_added
        profiles_added += p_added

    logger.info("[restore] новых учеников: %d, новых анкет: %d, пропущено строк: %d",
                students_added, profiles_added, skipped)
    return students_added, profiles_added
