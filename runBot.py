import telebot
from telebot import types

import sqlite3 as sql
from random import sample
from datetime import datetime, date
# from PIL import Image, ImageDraw

from data.Secondary_functions import get_token, normalized_text
from data.Consts import PROJECT_DATABASE, COMMANDS, FSW_FILMS_TABLE_TITLES, DATE_FORMAT

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


def show_film_info(message: types.Message, film_id: int):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    info = dict(
        zip(FSW_FILMS_TABLE_TITLES, cur.execute(f"SELECT * FROM Films WHERE film_id = ?", (film_id,)).fetchone()))

    dates = cur.execute("SELECT year, month, day FROM Sessions WHERE film_id = ?", (film_id,)).fetchall()
    dates = sorted(set(filter(lambda j: datetime.now().date() <= j, map(lambda i: date(*i), dates))))
    if not dates:
        return bot.send_message(message.chat.id, 'К сожалению, в данный момент нет сеансов на этот фильм.')

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

    str_dates = '\n'.join(map(lambda i: f"{i[0] + 1}) {i[1].strftime(DATE_FORMAT)}", enumerate(dates)))

    text = f"<b>{info['title']}</b>\n" \
           f"<u>Страна</u>: {info['country']}\n" \
           f"<u>Возрастной рейтинг</u>: {info['rating']}+\n" \
           f"<u>Длительность</u>: {duration}\n" \
           f"\t{description}\n" \
           f"Дни показа:\n" \
           f"{str_dates}"

    last_i = 0
    for i in range(2, len(dates) // 2 * 2, 2):
        markup.add(*map(lambda j: types.KeyboardButton(text=j.strftime(DATE_FORMAT)), dates[last_i:i]))
        last_i = i
    if len(dates) % 2:
        markup.add(types.KeyboardButton(text=dates[-1].strftime(DATE_FORMAT)))

    tg_info = cur.execute(f'SELECT * FROM Telegram WHERE id = ?', (message.chat.id,)).fetchall()

    if not tg_info:
        cur.execute(f"INSERT INTO Telegram VALUES(?, ?, ?)", (message.chat.id, film_id, 0))
    else:
        cur.execute(f"UPDATE Telegram SET film_id = ? WHERE id = ?", (film_id, message.chat.id))
    db.commit()

    try:
        with open(info['image_path'], 'rb') as desc_file:
            new_message = bot.send_photo(
                message.chat.id, desc_file, caption=text, parse_mode='HTML', reply_markup=markup)
    except FileNotFoundError:
        new_message = bot.send_message(message.chat.id, text=text, parse_mode='HTML', reply_markup=markup)
    # bot.register_next_step_handler(new_message, pass)


def choose_seat():
    print('ok')


@bot.message_handler(commands=['random'])
def random_film(message: types.Message):
    films = cur.execute("""SELECT DISTINCT Films.title, Films.film_id FROM Films 
        INNER JOIN Sessions ON Films.film_id = Sessions.film_id""").fetchall()
    film = sample(films, 1)
    bot.send_dice(message.chat.id)
    show_film_info(message, film[0][1])


@bot.message_handler(commands=['films'])
def avaible_films(message: types.Message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    films = cur.execute("""SELECT title, duration, rating FROM Films""").fetchall()

    if not films:
        text = "К сожалению, у нас пока что нет доступных фильмов"
    else:
        text = f"Вот список доступных фильмов:\n" + \
               "\n".join([
                   f'{i + 1}) {info[0]} ({info[1]} минут, {info[2]}+)' for i, info in enumerate(films)
               ])
        for film in films:
            markup.add(types.KeyboardButton(film[0]))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == 'Заказать билеты')
def order_ticket(message: types.Message):
    info = cur.execute(f"SELECT * FROM Telegram WHERE id = '{message.chat.id}'").fetchall()
    if len(info) == 0:
        bot.send_message(message.chat.id, "Вы не выбрали фильм и сеанс!", reply_markup=types.ReplyKeyboardRemove())
    else:
        if info[0][1] is None:
            bot.send_message(message.chat.id, "Вы не выбрали фильм!", reply_markup=types.ReplyKeyboardRemove())
        else:
            sessions = cur.execute("SELECT * FROM Sessions WHERE film_id = "
                                   f"(SELECT film_id FROM Films WHERE title = '{info[0][1]}') "
                                   "ORDER BY year, month, day, hour, minute, hall_id").fetchall()
            if len(sessions) == 0:
                bot.send_message(message.chat.id, "К сожалению, сейчас у нас нет доступных сеансов")
                return
            text = '\n'.join([f"{i + 1}) "
                              f"{':'.join(str(j) if len(str(j)) == 2 else '0' + str(j) for j in sessions[i][5:7])}"
                              f", {'.'.join(str(j) if len(str(j)) >= 2 else '0' + str(j) for j in sessions[i][4:1:-1])}"
                              f" , Зал №{sessions[i][7]}" for i in range(len(sessions))])
            bot.send_message(message.chat.id, "Выбери сеанс, написав его номер.\n" + text)


@bot.message_handler(content_types='text')
def search_films(message: types.Message):
    if message.text.isdigit():
        try:
            number = int(message.text)
            res = cur.execute(f"SELECT * FROM Telegram WHERE id = ?", (message.chat.id,)).fetchall()
            if not res:
                return bot.send_message(message.chat.id, "Вы не выбрали фильм, чтобы называть номер сеанса")
            elif res[0][1] is None:
                return bot.send_message(message.chat.id, "Вы не выбрали фильм, чтобы называть номер сеанса")
            else:
                sessions = cur.execute("SELECT * FROM Sessions WHERE film_id = "
                                       f"(SELECT film_id FROM Films WHERE title = ?) "
                                       "ORDER BY year, month, day, hour, minute, hall_id", (res[0][1],)).fetchall()
                if number <= 0 or number > len(sessions):
                    return bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер")
                return choose_seat()
        except Exception as e:
            return bot.send_message(message.chat.id, "Отправьте, пожалуйста, корректный номер")

    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    films = cur.execute("""SELECT film_id, title, duration, rating FROM Films""").fetchall()
    res = []

    for info in films:
        if normalized_text(info[1]) == normalized_text(message.text):
            show_film_info(message, info[0])
            return True
        elif normalized_text(message.text) in normalized_text(info[1]):
            res.append(info)

    if not res:
        text = 'К сожалению, мы не нашли ничего подходящего'
        markup = types.ReplyKeyboardRemove()
    else:
        text = 'Вот, что мне удалось найти:\n' + '\n'.join(map(lambda i: f"{i + 1}) ({res[i][2]} минут, {res[i][3]}+)",
                                                               range(len(res))))
        for film in res:
            markup.add(types.KeyboardButton(film[0]))
    bot.send_message(message.chat.id, text, reply_markup=markup)


bot.infinity_polling()
db.close()
