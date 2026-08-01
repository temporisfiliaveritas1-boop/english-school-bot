import gspread
import os
import json
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def get_sheet(sheet_name: str):
    client = get_client()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")
    spreadsheet = client.open_by_key(spreadsheet_id)
    return spreadsheet.worksheet(sheet_name)

def add_student(user_id: int, username: str, full_name: str):
    try:
        sheet = get_sheet("Ученики")
        # Добавляем заголовки если лист пустой
        if sheet.row_count == 0 or not sheet.row_values(1):
            sheet.append_row(["ID", "Username", "Имя", "Дата добавления"])
        # Проверяем нет ли уже такого ученика
        all_ids = sheet.col_values(1)
        if str(user_id) in all_ids:
            return
        sheet.append_row([
            str(user_id),
            f"@{username}" if username else "-",
            full_name,
            datetime.now().strftime("%d.%m.%Y %H:%M")
        ])
    except Exception as e:
        print(f"Sheets error (add_student): {e}")

def add_club(club_id: int, date: str, time: str, topic: str, level: str):
    try:
        sheet = get_sheet("Клубы")
        if sheet.row_count == 0 or not sheet.row_values(1):
            sheet.append_row(["ID", "Дата", "Время", "Тема", "Уровень", "Записано"])
        sheet.append_row([str(club_id), date, time, topic, level, "0"])
    except Exception as e:
        print(f"Sheets error (add_club): {e}")

def add_registration(user_id: int, username: str, full_name: str, club_id: int, date: str, time: str, topic: str):
    try:
        sheet = get_sheet("Записи")
        if sheet.row_count == 0 or not sheet.row_values(1):
            sheet.append_row(["User ID", "Username", "Имя", "ID клуба", "Дата клуба", "Время", "Тема", "Дата записи"])
        sheet.append_row([
            str(user_id),
            f"@{username}" if username else "-",
            full_name,
            str(club_id),
            date,
            time,
            topic,
            datetime.now().strftime("%d.%m.%Y %H:%M")
        ])
        # Обновляем счётчик в листе Клубы
        clubs_sheet = get_sheet("Клубы")
        all_ids = clubs_sheet.col_values(1)
        if str(club_id) in all_ids:
            row = all_ids.index(str(club_id)) + 1
            current = clubs_sheet.cell(row, 6).value or "0"
            clubs_sheet.update_cell(row, 6, str(int(current) + 1))
    except Exception as e:
        print(f"Sheets error (add_registration): {e}")
