from data.Secondary_functions import get_token
from data.Consts import *

import telebot
from telebot import types

import sqlite3 as sql
from datetime import datetime, time, date, timedelta

db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()

token = get_token('token.txt')
bot = telebot.TeleBot(token)


@bot.message_handler(commands=['start'])
def start_message(message: types.Message):
    commands = '\n'.join([f'/{key} - {value}' for key, value in COMMANDS.items()])
    bot.send_message(message.chat.id, "Привет ✌️ \n"
                                      "Я FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                                      "а также заказать билеты. Ещё можно написать мне название фильма или жанра.\n"
                                      f"Мои команды:\n"
                                      f"{commands}",
                     reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=['films'])
def available_films(message: types.Message):
    film_ids = cur.execute("""SELECT film_id FROM Films""").fetchall()
    right_film_ids = []

    for film_id in film_ids:
        if check_sessions(film_id[0]):
            right_film_ids.append(film_id)
    del film_ids

    if not right_film_ids:
        new_message = bot.send_message(message.chat.id, 'К сожалению, сейчас нет фильмов в прокате(',
                                       reply_markup=types.ReplyKeyboardRemove())
        return start_message(new_message)

    markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=True)
    for film_id in right_film_ids:
        btn = types.KeyboardButton(
            text=cur.execute("""SELECT title FROM Films WHERE film_id = ?""", film_id).fetchone()[0])
        markup.add(btn)

    markup.add(types.KeyboardButton(text='Назад'))

    new_message = bot.send_message(message.chat.id, 'Выберите предложенные фильмы', reply_markup=markup)
    bot.register_next_step_handler(new_message, title_waiting)

    return new_message


def title_waiting(message: types.Message):
    title = message.text
    if title == BACK_WORD:
        return available_films(message)

    film_id = cur.execute("""SELECT film_id FROM Films WHERE title = ?""", (title,)).fetchone()[0]

    if film_id is None or not check_sessions(film_id):
        new_message = available_films(message)
        return bot.register_next_step_handler(new_message, title_waiting)

    show_film_info(message, film_id)


def show_film_info(message: types.Message, film_id: int):
    info = dict(
        zip(FSW_FILMS_TABLE_TITLES, cur.execute(f"SELECT * FROM Films WHERE film_id = ?", (film_id,)).fetchone()))

    hours_dur, minutes_dur = divmod(info['duration'], 60)
    if hours_dur > 0 and minutes_dur > 0:
        duration = f'{hours_dur}ч. {minutes_dur}мин.'
    elif hours_dur > 0 and minutes_dur == 0:
        duration = f'{hours_dur}ч.'
    else:
        duration = f'{minutes_dur}мин.'

    try:
        with open(info['description_file_name']) as desc_file:
            description = desc_file.read()
    except FileNotFoundError:
        description = 'None'

    text = f"<b>{info['title']}</b>\n" \
           f"<u>Страна</u>: {info['country']}\n" \
           f"<u>Возрастной рейтинг</u>: {info['rating']}+\n" \
           f"<u>Длительность</u>: {duration}\n" \
           f"\t{description}\n"

    tg_info = cur.execute(f'SELECT * FROM Telegram WHERE id = ?', (message.chat.id,)).fetchall()

    if not tg_info:
        cur.execute(f"INSERT INTO Telegram VALUES(?, ?, ?)", (message.chat.id, film_id, 0))
    else:
        cur.execute(f"UPDATE Telegram SET film_id = ? WHERE id = ?", (film_id, message.chat.id))
    db.commit()

    try:
        with open(info['image_path'], 'rb') as desc_file:
            bot.send_photo(
                message.chat.id, desc_file, caption=text, parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
    except FileNotFoundError:
        bot.send_message(message.chat.id, text=text, parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())

    show_dates(message, film_id)


def show_dates(message: types.Message, film_id: int):
    sessions = cur.execute(
        "SELECT DISTINCT year, month, day, hour, minute FROM Sessions WHERE film_id = ?", (film_id,)).fetchall()
    sessions = filter(lambda j: datetime.now() <= j, map(lambda i: datetime(*i), sessions))
    sessions = sorted(set(map(lambda j: j.date(), sessions)))

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    for i in sessions:
        markup.add(types.KeyboardButton(text=i.strftime(DATE_FORMAT)))
    markup.add(types.KeyboardButton(text=BACK_WORD))

    new_message = bot.send_message(message.chat.id, 'Выберите день показа', reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def date_waiting(message: types.Message, film_id: int):
    date_string = message.text
    if date_string == BACK_WORD:
        return available_films(message)

    try:
        date_ = datetime.strptime(date_string, DATE_FORMAT).date()
        if date_ < datetime.now().date():
            raise ValueError

        sessions = cur.execute(
            """
            SELECT DISTINCT session_id, hour, minute, hall_id FROM Sessions 
                WHERE film_id = ? AND year = ? AND month = ? and day = ?
                """,
            (film_id, date_.year, date_.month, date_.day)).fetchall()

        sessions = sorted(map(lambda j: (j[0], time(*j[1:3]), j[3]), sessions))
        if date_ == datetime.now().date():
            sessions = sorted(filter(lambda j: j[1] >= (datetime.now() + timedelta(minutes=15)).time(), sessions))
        if not sessions:
            raise ValueError
        sessions = sorted(
            [{'session_id': session_id, 'time': time_.strftime(TIME_FORMAT), 'hall': hall}
             for session_id, time_, hall in sessions],
            key=lambda j: j['time'])

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        for i in sessions:
            markup.add(types.KeyboardButton(text=SESSION_FORMAT.format_map(i)))
        markup.add(types.KeyboardButton(text=BACK_WORD))

        new_message = bot.send_message(message.chat.id, 'Выберите сеанс', reply_markup=markup)
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))

    except ValueError:
        new_message = bot.send_message(message.chat.id, 'Укажите корректную дату:')
        bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def session_waiting(message: types.Message, film_id: int, date_: date):
    session_string = message.text
    if session_string == BACK_WORD:
        return show_dates(message, film_id)


def check_sessions(film_id: int):
    try:
        sessions = cur.execute(
            """SELECT year, month, day, hour, month, day FROM Sessions WHERE film_id = ?""", (film_id,)).fetchall()
        return bool(filter(lambda i: datetime(*i) >= datetime.now(), sessions))
    except sql.InterfaceError:
        return False


bot.infinity_polling()
db.close()
