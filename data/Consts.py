import sqlite3 as sql
from PyQt5.QtWidgets import QHeaderView

from datetime import datetime, timedelta


# _______FILES________
INTERFACES_FOLDER = 'Interfaces'

AW_INTERFACE = f'{INTERFACES_FOLDER}\\AdminWindow.ui'
DSD_INTERFACE = f'{INTERFACES_FOLDER}\\DirectorSetupDialog.ui'
FSD_INTERFACE = f'{INTERFACES_FOLDER}\\FilmSelectionDialog.ui'
FW_INTERFACE = f'{INTERFACES_FOLDER}\\FilmWindow.ui'
GSD_INTERFACE = f'{INTERFACES_FOLDER}\\GenresSelectionDialog.ui'
HD_INTERFACE = f'{INTERFACES_FOLDER}\\HallDialog.ui'
SSD_INTERFACE = f'{INTERFACES_FOLDER}\\SessionSetupDialog.ui'
TD_INTERFACE = f'{INTERFACES_FOLDER}\\TabDialog.ui'
UW_INTERFACE = f'{INTERFACES_FOLDER}\\UserWindow.ui'

DATABASES_FOLDER = 'DataBases'

PROJECT_DATABASE = f'{DATABASES_FOLDER}\\DataBase.sqlite'

# ___________COLORS___________
NORMAL_LINE_COLOR = '#ffffff'
NORMAL_WINDOW_COLOR = '#f0f0f0'
ERROR_COLOR = '#ff5133'

OCCUPIED_COLOR = '#aa0000'
ORDER_COLOR = '#ffe666'

# _______FORMATS_______
DATE_FORMAT = '%d.%m.%Y'

# ___________SIZES____________
IMAGE_SIZE = (IMAGE_WIDTH, IMAGE_HEIGHT) = (280, 400)

AW_GENRES_TABLE_COLS_SIZE = (160, QHeaderView.Stretch)
AW_DIRECTORS_TABLE_COLS_SIZE = (QHeaderView.Stretch, QHeaderView.Stretch)
AW_SESSIONS_TABLE_COLS_SIZE = (QHeaderView.Stretch, QHeaderView.Stretch)

FSW_FILMS_TABLE_COLS_SIZE = (80, 200, 100, 100, QHeaderView.Stretch, QHeaderView.Stretch,
                             QHeaderView.Stretch, QHeaderView.Stretch)
FSW_GENRES_TABLE_COLS_SIZE = (80, QHeaderView.Stretch)
FSW_DIRECTORS_TABLE_COLS_SIZE = (QHeaderView.Stretch, QHeaderView.Stretch)
FSW_SESSIONS_TABLE_COLS_SIZE = (80, QHeaderView.Stretch, QHeaderView.Stretch, QHeaderView.Stretch)

UW_FILMS_TABLE_COLS_SIZE = (300, 250, 300, QHeaderView.Stretch, QHeaderView.Stretch)

# __________NUMBERS___________
MIN_DATE = datetime.now().date()
MAX_DATE = MIN_DATE + timedelta(days=730)

MIN_AGE_RATING = 0
MIN_DURATION = 30

MAX_DIRECTORS = 6
MAX_SESSIONS = 8
MAX_AGE_RATING = 18
MAX_DURATION = 400
MAX_BUY_PLACES = 4

AW_GENRES_TABLE_COLS_COUNT = 2
AW_DIRECTORS_TABLE_COLS_COUNT = 2
AW_SESSIONS_TABLE_COLS_COUNT = 2

FSW_FILMS_TABLE_COLS_COUNT = 8
FSW_GENRES_TABLE_COLS_COUNT = 2
FSW_DIRECTORS_TABLE_COLS_COUNT = 2
FSW_SESSIONS_TABLE_COLS_COUNT = 4

UW_FILMS_TABLE_COLS_COUNT = 5

# ___________TITLES___________
AW_GENRES_TABLE_COLS_TITLES = ["genre_id", "Жанр"]
AW_DIRECTORS_TABLE_COLS_TITLES = ["Имя", "Фамилия"]
AW_SESSIONS_TABLE_COLS_TITLES = ["Время", "Зал"]

FSW_FILMS_TABLE_TITLES = ["film_id", "title", "country", "rating", "duration",
                          "file_folder_name", "description_file_name", "image_path"]
FSW_GENRES_TABLE_TITLES = ["genre_id", "genre_title"]
FSW_DIRECTORS_TABLE_TITLES = ["director_id", "name", "surname"]
FSW_SESSIONS_TABLE_TITLES = ["session_id", "date", "time", "hall_id"]

UW_FILMS_TABLE_TITLES = ["Название", "Страна", "Жанры", "Рейтинг", "Длительность"]

# _________SECONDARY_________
FILMS_TABLE_KEYS = ['film_id', 'title', 'country', 'rating', 'duration',
                    'file_folder_name', 'description_file_name', 'image_path']

AW_FILM_INFO_TAB0 = {"film_id": -1, "title": "", "country": "", "genres": [], 'directors': [], "rating": 0,
                     "duration": 30, "description": "", "sessions": dict(), "image_path": ""}

AW_FILM_INFO_TAB1 = {"film_id": -1, "title": "", "country": "", "genres": [], 'directors': [], "rating": 0,
                     "duration": 30, "description": "", "sessions": dict(), "file_folder_name": "",
                     "description_file_name": "", "image_path": "", "del_sessions": []}

AW_FILMS_INFO_CHECKED_PARAMS = ['title', 'country', 'genres', 'directors', 'description', 'sessions', 'image_path']

UW_SEARCH_INFO = {"title": '', 'genres': [], 'rating': [MIN_AGE_RATING, MAX_AGE_RATING], 'date': MIN_DATE}

TRANSCRIPTION = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z',
                 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
                 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
                 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'u', 'я': 'ja', 'a': 'a', 'b': 'b', 'c': 'c',
                 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g', 'h': 'h', 'i': 'i', 'j': 'j', 'k': 'k', 'l': 'l',
                 'm': 'm', 'n': 'n', 'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't', 'u': 'u',
                 'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z', '0': '0', '1': '1', '2': '2', '3': '3',
                 '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'}

db = sql.connect(PROJECT_DATABASE)
cur = db.cursor()

GENRES_DICT = dict(cur.execute("SELECT * FROM Genres").fetchall())

db.close()
del db
del cur

# Telegram
COMMANDS = {
    'films': 'Показать полный список доступных фильмов',
    'random': 'Показать случайный фильм'
}

