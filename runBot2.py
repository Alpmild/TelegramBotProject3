from data.Secondary_functions import get_token, make_dict_from_string
from data.Consts import *

from telebot import TeleBot, types
import sqlite3 as sql
from datetime import datetime, time, date, timedelta
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()

token = get_token('token.txt')
bot = TeleBot(token)


@bot.message_handler(commands=['start'])
def start_message(message: types.Message):
    """Начало работы бота"""

    commands = '\n'.join([f'/{key} - {value}' for key, value in COMMANDS.items()])
    bot.send_message(message.chat.id, "Привет ✌️ \n"
                                      "Я FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                                      "а также заказать билеты. Ещё можно написать мне название фильма или жанра.\n"
                                      f"Мои команды:\n"
                                      f"{commands}",
                     reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=['search'])
def search_film(message: types.Message):
    print(message.text)


@bot.message_handler(commands=['random'])
def random_film(message: types.Message):
    print(message.text)


@bot.message_handler(commands=['where'])
def find_place(message: types.Message):
    print(message.text)


@bot.message_handler(commands=['films'])
def available_films(message: types.Message) -> types.Message:
    """Показ фильмов, для которых возможно купить билет"""

    film_ids = cur.execute("""SELECT film_id FROM Films""").fetchall()
    right_film_ids = []

    for film_id in film_ids:
        if check_sessions(film_id[0]):
            right_film_ids.append(film_id[0])
    del film_ids

    if not right_film_ids:
        new_message = bot.send_message(message.chat.id, 'К сожалению, сейчас нет фильмов в прокате(',
                                       reply_markup=types.ReplyKeyboardRemove())
        return start_message(new_message)

    markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    for film_id in right_film_ids:
        btn = types.KeyboardButton(
            text=cur.execute("""SELECT title FROM Films WHERE film_id = ?""", (film_id,)).fetchone()[0])
        markup.add(btn)

    markup.add(types.KeyboardButton(text='Назад'))

    new_message = bot.send_message(message.chat.id, 'Выберите предложенные фильмы', reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: title_waiting(m, right_film_ids))

    return new_message


def title_waiting(message: types.Message, film_ids: list):
    """Ожидание названия фильма"""

    title = message.text
    if title.lower() == BACK_WORD.lower():
        return start_message(message)

    try:
        film_id = cur.execute("""SELECT film_id FROM Films WHERE title = ?""", (title,)).fetchone()
        if film_id is None:
            raise ValueError

        film_id = film_id[0]
        if film_id not in film_ids or not check_sessions(film_id):
            raise ValueError

        show_film_info(message, film_id)
    except ValueError:
        new_message = bot.send_message(message.chat.id, 'Выберите название из предолженных:')
        bot.register_next_step_handler(new_message, lambda m: title_waiting(m, film_ids))


def show_film_info(message: types.Message, film_id: int):
    """Вывод основной информации о фильме"""

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
           f"\t{description}"

    tg_info = cur.execute(f'SELECT * FROM Telegram WHERE id = ?', (message.chat.id,)).fetchall()

    if not tg_info:
        cur.execute("INSERT INTO Telegram VALUES(?, ?, ?)", (message.chat.id, film_id, 0))
    else:
        cur.execute("UPDATE Telegram SET film_id = ? WHERE id = ?", (film_id, message.chat.id))
    db.commit()

    try:
        with open(info['image_path'], 'rb') as desc_file:
            bot.send_photo(
                message.chat.id, desc_file, caption=text, parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())
    except FileNotFoundError:
        bot.send_message(message.chat.id, text=text, parse_mode='HTML', reply_markup=types.ReplyKeyboardRemove())

    show_dates(message, film_id)


def show_dates(message: types.Message, film_id: int):
    """Вывод дней показа"""

    sessions = cur.execute(
        "SELECT DISTINCT year, month, day, hour, minute FROM Sessions WHERE film_id = ?", (film_id,)).fetchall()
    sessions = filter(lambda j: datetime.now() <= j, map(lambda x: datetime(*x), sessions))
    sessions = sorted(set(map(lambda j: j.date(), sessions)))

    markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)

    for i in sessions:
        markup.add(types.KeyboardButton(text=i.strftime(DATE_FORMAT)))
    markup.add(types.KeyboardButton(text=BACK_WORD))

    new_message = bot.send_message(message.chat.id, 'Выберите день показа', reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def date_waiting(message: types.Message, film_id: int):
    """Ожидание даты"""

    date_str = message.text
    if date_str.lower() == BACK_WORD.lower():
        return available_films(message)

    try:
        date_ = datetime.strptime(date_str, DATE_FORMAT).date()
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
             for session_id, time_, hall in sessions], key=lambda j: j['time'])

        markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
        for i in sessions:
            markup.add(types.KeyboardButton(text=SESSION_FORMAT.format_map(i)))
        markup.add(types.KeyboardButton(text=BACK_WORD))

        new_message = bot.send_message(message.chat.id, 'Выберите сеанс', reply_markup=markup)
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))

    except ValueError:
        new_message = bot.send_message(message.chat.id, 'Укажите корректную дату:')
        bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def session_waiting(message: types.Message, film_id: int, date_: date):
    """Ожидание времени сеанса"""

    ses_str = message.text
    if ses_str.lower() == BACK_WORD.lower():
        return show_dates(message, film_id)

    try:
        ses_dict = make_dict_from_string(ses_str, SESSION_FORMAT)
        ses_time, hall = (datetime.strptime(ses_dict['time'], TIME_FORMAT),
                          int(ses_dict['hall']))
        ses_time = ses_time.replace(date_.year, date_.month, date_.day)

        if datetime.now().date() == date_:
            if datetime.now() >= ses_time:
                raise ValueError

        ses_id = cur.execute("""
        SELECT session_id FROM Sessions 
        WHERE 
            film_id = ? AND 
            year = ? AND 
            month = ? AND 
            day = ? AND 
            hour = ? AND 
            minute = ? AND 
            hall_id = ?
            """, (film_id, ses_time.year, ses_time.month, ses_time.day, ses_time.hour, ses_time.minute, hall)
                             ).fetchone()

        if ses_id is None:
            raise ValueError
        ses_id = ses_id[0]

        bot.send_photo(message.chat.id, draw_hall(ses_id, []),
                       f'Выберите места в зале.\n'
                       f'Добавить- "{ADD_PLACE_FORMAT}".\n'
                       f'Изменить- "{CHANGED_PLACE_FORMAT}".\n'
                       f'Удалить- "{DELETE_PLACE_FORMAT}".',
                       reply_markup=types.ReplyKeyboardRemove())
        new_message = show_ordered_places(message, [])
        bot.register_next_step_handler(new_message, lambda m: order_place(m, ses_id, []))

    except ValueError:
        new_message = bot.send_message(message.chat.id, 'Укажите сеанс в правильном формате:')
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))


def draw_hall(session_id: int, ordered_places: list):
    """Создание изображения зала"""

    occupied_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()

    image = Image.new('RGB', HALL_IMAGE_SIZE, HALL_BACK_COLOR)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(ARIALMT, size=FONT_SIZE)

    y_s = (PLACE_HEIGHT - draw.textsize('1', font=font)[1]) // 2
    for col in range(1, HALL_COLUMNS + 1):
        x_c = (PLACE_WIDTH + LEN_BTWN_PLACES) * col + (PLACE_WIDTH - draw.textsize(str(col), font=font)[0]) // 2
        draw.text((x_c, y_s), str(col), font=font, fill=FONT_COLOR)

    x_s = (PLACE_WIDTH - draw.textsize('1', font=font)[0]) // 2
    for row in range(1, HALL_ROWS + 1):
        y_c = (PLACE_HEIGHT + LEN_BTWN_PLACES) * row + (PLACE_HEIGHT - draw.textsize(str(row), font=font)[1]) // 2
        draw.text((x_s, y_c), str(row), font=font, fill=FONT_COLOR)

    for row in range(1, HALL_ROWS + 1):
        for col in range(1, HALL_COLUMNS + 1):
            x_s, y_s = (PLACE_WIDTH + LEN_BTWN_PLACES) * col, (PLACE_HEIGHT + LEN_BTWN_PLACES) * row
            coors = ((x_s, y_s), (x_s + PLACE_WIDTH, y_s),
                     (x_s + PLACE_WIDTH, y_s + PLACE_HEIGHT), (x_s, y_s + PLACE_HEIGHT))

            row, col = row - 1, col - 1
            if (row, col) in occupied_places:
                color = OCCUPIED_COLOR
            elif (row, col) in ordered_places:
                color = ORDER_COLOR
            else:
                color = NORMAL_WINDOW_COLOR
            row, col = row + 1, col + 1
            draw.rectangle((coors[0], coors[2]), color)

            for i in range(len(coors)):
                draw.line((coors[i], coors[(i + 1) % 4]), fill=LINE_COLOR, width=LINE_WIDTH)

    bytes_list = BytesIO()
    image.save(bytes_list, format='PNG')
    bytes_list = bytes_list.getvalue()

    return bytes_list


def order_place(message: types.Message, session_id: int, ordered_places: list):
    """Заказ билета"""
    place_str = message.text
    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]

    if place_str.lower() == BUY_WORD.lower():
        if not ordered_places:
            return send_places_info(message, session_id, ordered_places)
        else:
            markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
            markup.add(types.KeyboardButton(text=BACK_WORD))
            markup.add(types.KeyboardButton(text=CANCEL_WORD))

            new_message = bot.send_message(message.chat.id,
                                           f'Укажите данные банковский карты в формате "{CARD_INFO_FORMAT}"',
                                           reply_markup=types.ReplyKeyboardRemove())
            bot.register_next_step_handler(new_message, lambda m: card_info_waiting(m, session_id, ordered_places))

            return

    if place_str.lower() == CANCEL_WORD.lower():
        return show_film_info(message, film_id)

    for form in (ADD_PLACE_FORMAT, CHANGED_PLACE_FORMAT, DELETE_PLACE_FORMAT):
        try:
            place_dict = make_dict_from_string(place_str, form)
            for key in place_dict:
                place_dict[key] = int(place_dict[key])
        except ValueError:
            continue
        break
    else:
        new_message = bot.send_message(message.chat.id, 'Отправтье место в правильном формате')
        return bot.register_next_step_handler(new_message, lambda m: order_place(m, session_id, ordered_places))

    occupied_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()
    if form == ADD_PLACE_FORMAT:
        row, column = place_dict['row'] - 1, place_dict['column'] - 1
        if 0 <= row < HALL_ROWS and 0 <= column < HALL_COLUMNS and len(ordered_places) < MAX_BUY_PLACES \
                and (row, column) not in occupied_places and (row, column) not in ordered_places:
            ordered_places.append((row, column))

    elif form == CHANGED_PLACE_FORMAT:
        index, row, column = place_dict['index'] - 1, place_dict['row'] - 1, place_dict['column'] - 1
        if 0 <= index < len(ordered_places) and (row, column) not in occupied_places:
            ordered_places[index] = (row, column)

    elif form == DELETE_PLACE_FORMAT:
        index = place_dict['index'] - 1
        if 0 <= index < len(ordered_places):
            del ordered_places[index]

    for i in range(1, -1, -1):
        ordered_places.sort(key=lambda x: x[i])

    send_places_info(message, session_id, ordered_places)


def show_ordered_places(message: types.Message, ordered_places: list):
    text = 'Купленные места:\n' \
           + '\n'.join([f'{i + 1}. Ряд {place[0] + 1} Место {place[1] + 1}'for i, place in enumerate(ordered_places)])

    markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    if ordered_places:
        markup.add(types.KeyboardButton(text=BUY_WORD))
    markup.add(types.KeyboardButton(text=CANCEL_WORD))

    return bot.send_message(message.chat.id, text, reply_markup=markup)


def card_info_waiting(message: types.Message, session_id: int, ordered_places: list):
    card_info = message.text
    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]

    if card_info.lower() == BACK_WORD.lower():
        return send_places_info(message, session_id, ordered_places)

    if card_info.lower() == CANCEL_WORD.lower():
        return show_film_info(message, film_id)

    try:
        card_info = make_dict_from_string(card_info, CARD_INFO_FORMAT)
        number, cvv = card_info['number'].replace(' ', ''), card_info['cvv']

        if len(number) != LEN_CARD_NUMBER or not number.isdigit() or len(cvv) != LEN_CVV or not cvv.isdigit():
            raise ValueError

        datetime.strptime(card_info['date'], CARD_DATE_FORMAT)

        buy_tickets(message, session_id, ordered_places)
    except ValueError:
        new_message = bot.send_message(message.chat.id,
                                       f'Итог: {len(ordered_places) * TICKET_PRICE}Р\n'
                                       f'Укажите данные банковский карты в правильном формате "{CARD_INFO_FORMAT}"',
                                       reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(new_message, lambda m: card_info_waiting(m, session_id, ordered_places))


def send_places_info(message: types.Message, session_id: int, ordered_places: list):
    bot.send_photo(message.chat.id, draw_hall(session_id, ordered_places))
    new_message = show_ordered_places(message, ordered_places)
    bot.register_next_step_handler(new_message, lambda m: order_place(m, session_id, ordered_places))


def buy_tickets(message: types.Message, session_id: int, ordered_places: list):
    for row, col in ordered_places:
        cur.execute("""INSERT INTO Tickets VALUES (?, ?, ?)""", (session_id, row, col))
        db.commit()
    code = str(hash((session_id,) + tuple(ordered_places)))

    markup = types.ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    markup.add(types.KeyboardButton(text=BACK_WORD))

    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]
    new_message = bot.send_message(message.chat.id, f'Вот ваш уникальный код: {code}\n'
                                                    f'Предъявите его при входе в зал.\n'
                                                    f'Спасибо за покупку)',
                                   reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: answer_waiting(m, film_id))


def answer_waiting(message: types.Message, film_id: int):
    if message.text.lower() == BACK_WORD.lower():
        return show_film_info(message, film_id)

    bot.register_next_step_handler(message, lambda m: answer_waiting(m, film_id))


def check_sessions(film_id: int):
    try:
        sessions = cur.execute(
            """SELECT year, month, day, hour, month, day FROM Sessions WHERE film_id = ?""", (film_id,)).fetchall()
        return bool(filter(lambda i: datetime(*i) >= datetime.now(), sessions))
    except sql.InterfaceError:
        return False


bot.infinity_polling()
db.close()
