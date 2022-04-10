from datetime import date, time
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QTableWidgetItem
from PyQt5 import uic

from data.Consts import *

import sqlite3 as sql
from PyQt5.QtWidgets import QHeaderView


class FilmSelectionDialog(QDialog):
    """Класс для выбор фильма. Для дальнейшего его изменения в основном окне"""

    def __init__(self, parent):
        super(FilmSelectionDialog, self).__init__(parent)
        self.parent = parent
        self.current_film = -1

        self.projectDB = sql.connect(PROJECT_DATABASE)
        self.projectDB_cur = self.projectDB.cursor()

        self.films_info = list(map(lambda i: dict(zip(FILMS_TABLE_KEYS, i)),
                                   self.projectDB_cur.execute("SELECT * FROM Films").fetchall()))

        tickets = set(map(lambda i: i[0], self.projectDB_cur.execute("SELECT session_id FROM Tickets").fetchall()))

        for dict_ in self.films_info:
            film_id = dict_["film_id"]

            genres_req = "SELECT genre_id FROM Films_Genres WHERE film_id = ?"
            film_genres = list(map(lambda i: i[0], self.projectDB_cur.execute(genres_req, (film_id,)).fetchall()))

            directors_req = "SELECT name, surname FROM Films_Directors WHERE film_id = ?"
            film_directors = self.projectDB_cur.execute(directors_req, (film_id,)).fetchall()

            sessions_req = "SELECT session_id, year, month, day, hour, minute, hall_id FROM Sessions WHERE film_id = ?"
            sessions = list(map(lambda i: (i[0], date(*i[1:4]), time(*i[4:6]), i[6]),
                                self.projectDB_cur.execute(sessions_req, (film_id,)).fetchall()))

            sessions_dict = dict()
            del_sessions = list()
            for session_id, date_, time_, hall in sessions:
                if date_ >= MIN_DATE:
                    if date_ not in sessions_dict:
                        sessions_dict[date_] = []
                    if session_id not in tickets:
                        sessions_dict[date_].append((session_id, time_, hall))
                        del_sessions.append(session_id)

            for date_ in sessions_dict:
                if not sessions_dict[date_]:
                    del sessions_dict[date_]

            dict_['genres'], dict_['directors'], dict_['sessions'], dict_["del_sessions"] = \
                (film_genres, film_directors, sessions_dict, del_sessions)

            try:
                with open(dict_["description_file_name"]) as desc_file:
                    description = desc_file.read()
            except FileNotFoundError:
                description = ''

            dict_['description'] = description
            dict_["image_path"] = f'{os.getcwd()}\\{dict_["image_path"]}'

        uic.loadUi(FSD_INTERFACE, self)
        self.init_ui()
        self.load_films_table()

    def init_ui(self):
        self.setFixedSize(self.size())
        self.setModal(True)

        # Инициализация таблицы FilmsTable
        self.FilmsTable.setColumnCount(FSW_FILMS_TABLE_COLS_COUNT)
        self.FilmsTable.setHorizontalHeaderLabels(FSW_FILMS_TABLE_TITLES)

        ws = [
            [self.FilmsTable, FSW_FILMS_TABLE_COLS_COUNT, FSW_FILMS_TABLE_TITLES, FSW_FILMS_TABLE_COLS_SIZE],
            [self.GenresTable, FSW_GENRES_TABLE_COLS_COUNT, FSW_GENRES_TABLE_TITLES, FSW_GENRES_TABLE_COLS_SIZE],
            [self.DirectorsTable, FSW_DIRECTORS_TABLE_COLS_COUNT, FSW_DIRECTORS_TABLE_TITLES,
             FSW_DIRECTORS_TABLE_COLS_SIZE],
            [self.SessionsTable, FSW_SESSIONS_TABLE_COLS_COUNT, FSW_SESSIONS_TABLE_TITLES, FSW_SESSIONS_TABLE_COLS_SIZE]
        ]

        for table, cols_count, cols_titles, cols_size in ws:
            table.setColumnCount(cols_count)
            table.setHorizontalHeaderLabels(cols_titles)

            for col, size in enumerate(cols_size):
                if isinstance(size, QHeaderView.ResizeMode):
                    table.horizontalHeader().setSectionResizeMode(col, size)
                else:
                    table.setColumnWidth(col, size)
                    table.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)

        self.FilmsTable.cellClicked.connect(self.load_secondary_tables)

        self.SelectBtn.clicked.connect(self.set_film)
        self.CancelBtn.clicked.connect(self.close)

    def load_films_table(self):
        """Загрузка всей основной информации в таблицу FilmsTable о фильмах из бд-таблицы Films"""
        self.FilmsTable.setRowCount(len(self.films_info))

        for row, film in enumerate(self.films_info):
            for col, title in enumerate(FSW_FILMS_TABLE_TITLES):
                item = QTableWidgetItem(str(self.films_info[row][title]))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.FilmsTable.setItem(row, col, item)

    def load_secondary_tables(self, r: int):
        self.current_film = r
        if r == -1:
            return

        self.load_genres_table(r)
        self.load_directors_table(r)
        self.load_sessions_table(r)

    def load_genres_table(self, r: int):
        """Загрузка жанров выбранного фильма в таблицу GenresTable"""
        genres = self.films_info[r]["genres"]
        self.GenresTable.clearContents()
        self.GenresTable.setRowCount(len(genres))

        for row, genre_id in enumerate(genres):
            str_genre = GENRES_DICT[genre_id]

            for col, elem in enumerate([QTableWidgetItem(str(genre_id)), QTableWidgetItem(str_genre)]):
                elem.setFlags(elem.flags() ^ Qt.ItemIsEditable)
                self.GenresTable.setItem(row, col, elem)

    def load_directors_table(self, r: int):
        """Загрузка режиссеров выбранного фильма в таблицу DirectorsTable"""
        directors = sorted(self.films_info[r]["directors"], key=lambda i: i[0])
        self.DirectorsTable.clearContents()
        self.DirectorsTable.setRowCount(len(directors))

        for row, direct in enumerate(directors):
            for col, elem in enumerate(direct):
                item = QTableWidgetItem(str(elem))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.DirectorsTable.setItem(row, col, item)

    def load_sessions_table(self, r: int):
        """Загрузка сеансов выбранного фильма в таблицу SessionsTable"""
        sessions = self.films_info[r]["sessions"]

        self.SessionsTable.clearContents()
        self.SessionsTable.setRowCount(len(sessions))

        for date_ in sessions:
            for row, ses in enumerate(sessions[date_]):
                for col, elem in enumerate(ses[:1] + (date_,) + ses[1:]):
                    if isinstance(elem, date):
                        item = QTableWidgetItem(elem.strftime("%d.%m.%y"))
                    elif isinstance(elem, time):
                        item = QTableWidgetItem(elem.strftime("%H:%M"))
                    else:
                        item = QTableWidgetItem(str(elem))
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    self.SessionsTable.setItem(row, col, item)

    def set_film(self):
        """Передача словаря с информацией о выбранном фильме"""
        self.parent.load_film_tab1(self.films_info[self.current_film])
        self.close()
