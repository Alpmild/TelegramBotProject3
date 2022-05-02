from data.Secondary_functions import get_token, make_dict_from_string
from data.Consts import *

import sqlite3 as sql
from datetime import datetime, time, date, timedelta
from io import BytesIO, TextIOWrapper
from os.path import exists
from random import choice

from PIL import Image, ImageDraw, ImageFont
from qrcode import make
from telebot import TeleBot
from telebot.types import Message, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InputMediaPhoto
import requests as req

db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()

token = get_token('token.txt')
bot = TeleBot(token)


@bot.message_handler(commands=['start'])
def start_message(message: Message, hi: bool = True):
    """Начало работы бота"""

    if hi:
        bot.send_message(message.chat.id,
                         "Привет ✌️ \n"
                         "Я FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                         "а также заказать билеты.",
                         reply_markup=ReplyKeyboardRemove())

    commands = '\n'.join([f'/{key} - {value}' for key, value in COMMANDS.items()])
    bot.send_message(message.chat.id, f"Мои команды:\n{commands}", reply_markup=ReplyKeyboardRemove())


@bot.message_handler(commands=['search'])
def search_film(message: Message):
    """Поиск фильма по названию"""
    title = message.text.lstrip('/search ')
    if not title:
        bot.send_message(message.chat.id, 'Ничего не найдено')
        return start_message(message, False)

    films_id = cur.execute("""SELECT film_id FROM Films WHERE title like ?""", (f'%{title}%',)).fetchall()

    films_id = tuple(filter(lambda i: check_sessions(i[0]), films_id))
    if not films_id:
        bot.send_message(message.chat.id, 'Ничего не найдено')
        return start_message(message, False)

    show_film_info(message, choice(films_id)[0])


@bot.message_handler(commands=['random'])
def random_film(message: Message):
    """Рандомный фильм"""
    films_id = cur.execute("""SELECT film_id FROM Films""").fetchall()
    films_id = tuple(filter(lambda i: check_sessions(i[0]), films_id))

    if not films_id:
        bot.send_message(message.chat.id, 'Сейчас нет фильмов в нашем прокате.')
        return start_message(message, False)

    show_film_info(message, choice(films_id)[0])


@bot.message_handler(commands=['where'])
def show_theatre(message: Message):
    """Отправка геолокации театра"""

    data = MAP_PARAMS.copy()
    data['geocode'] = ','.join(map(str, tuple(THEATRE_COORS.values())[::-1]))

    address = req.get(GEOCODE_MAP_URL, params=data).json()
    address = address['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']['metaDataProperty'][
        'GeocoderMetaData']['Address']['formatted']

    bot.send_location(message.chat.id, **THEATRE_COORS)
    new_message = bot.send_message(message.chat.id, f'Мы находимся по адресу: {address}')
    start_message(new_message, False)


@bot.message_handler(commands=['history'])
def get_purchased_history(message: Message):
    """Создание документа с историей покупок пользователя"""

    user_id = message.from_user.id

    output = BytesIO()
    wrapper = TextIOWrapper(output, encoding='utf-8', write_through=True)

    result = cur.execute(
        """SELECT session_id, row, column, year, month, day, hour, minute FROM Tickets WHERE user_id = ?""",
        (user_id,)).fetchall()

    data = dict()
    for i in result:
        ses_id, row, col, *buy_time = i
        buy_time = datetime(*buy_time)

        if buy_time not in data:
            data[buy_time] = dict()
        if ses_id not in data[buy_time]:
            data[buy_time][ses_id] = []
        data[buy_time][ses_id].append((row, col))

    text = ''
    for time_ in sorted(data.keys()):
        text += time_.strftime(f'{DATE_FORMAT} {TIME_FORMAT}:\n')

        for session_id in data[time_]:
            film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]
            title = cur.execute("""SELECT title FROM Films WHERE film_id = ?""", (film_id,)).fetchone()[0]

            session_time = cur.execute("""SELECT year, month, day, hour, minute FROM Sessions WHERE session_id = ?""",
                                       (session_id,)).fetchone()
            session_time = datetime(*session_time)

            text += f"\t{title}, Сеанс на " + session_time.strftime(f'{DATE_FORMAT} {TIME_FORMAT}:\n')

            n = len(data[time_][session_id])
            ordered_places = '\n'.join(
                [f'\t\t{i + 1}. Ряд {p[0] + 1} Место {p[1] + 1}' for i, p in enumerate(data[time_][session_id])])

            text += f'{ordered_places}\n' \
                    f'\t\tИтог: {TICKET_PRICE * n}р\n\n'

    text = text.rstrip('\n')
    # Запись строки в байты
    wrapper.write(text)

    new_message = bot.send_document(message.chat.id, output.getvalue(), caption='Ваша история покупок')
    start_message(new_message, False)


@bot.message_handler(commands=['authors'])
def send_authors(message: Message):
    new_message = bot.send_message(message.chat.id, f'Петров Дмитрий https://vk.com/yeah_metal\n'
                                                    f'Иванов Григорий https://vk.com/jsprogrammist')

    start_message(new_message, False)


@bot.message_handler(commands=['films'])
def available_films(message: Message) -> Message:
    """Показ фильмов, для которых возможно купить билет"""

    film_ids = cur.execute("""SELECT film_id FROM Films""").fetchall()
    right_film_ids = []

    # Фильтрация id-шников фильмов по сеансам
    # Если есть доступные сеансы, то id фильма добавляется в список
    for film_id in film_ids:
        if check_sessions(film_id[0]):
            right_film_ids.append(film_id[0])
    del film_ids

    if not right_film_ids:
        new_message = bot.send_message(message.chat.id, 'К сожалению, сейчас нет фильмов в прокате(',
                                       reply_markup=ReplyKeyboardRemove())
        return start_message(new_message, False)

    titles_photo = dict()
    titles_without_photos = []

    # Получение названия и дирекирии изображения к каждому фильму
    for film_id in right_film_ids:
        title, image_path = cur.execute(
            """SELECT title, image_name FROM Films WHERE film_id = ?""", (film_id,)).fetchone()
        if exists(image_path):
            titles_photo[title] = image_path
        else:
            titles_without_photos.append(title)

    photos = []
    # Добавление доступных изображений в список в виде байтов
    for t in sorted(titles_photo.keys()):
        photos.append(InputMediaPhoto(open(titles_photo[t], 'rb')))

    titles = sorted(titles_photo.keys()) + sorted(titles_without_photos)
    text = 'Выберите предложенные фильмы:\n' + '\n'.join([f'{i + 1}. {title}' for i, title in enumerate(titles)])

    # Создание клавиатуры с названиями фильмов и кнопкой "Назад"
    markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    for t in titles:
        markup.add(KeyboardButton(text=t))

    markup.add(KeyboardButton(text='Назад'))

    # Ожидание ввода нужного названия фильма
    bot.send_media_group(message.chat.id, photos)
    new_message = bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: title_waiting(m, right_film_ids))

    return new_message


def title_waiting(message: Message, film_ids: list):
    """Ожидание названия фильма"""

    title = message.text
    # Если нажать на кнопку "Назад", то пользователь вернется обратно к выбору фильма
    if title.lower() == BACK_WORD.lower():
        return start_message(message, False)

    try:
        film_id = cur.execute("""SELECT film_id FROM Films WHERE title = ?""", (title,)).fetchone()
        if film_id is None:
            raise ValueError

        film_id = film_id[0]
        if film_id not in film_ids or not check_sessions(film_id):
            raise ValueError

        # При выполнении всех условий выводится основная информация о выбранном фильме
        show_film_info(message, film_id)
    except ValueError:
        # При неправильно вводе прооисходит повторное ожидание выбора названия
        new_message = bot.send_message(message.chat.id, 'Выберите название из предолженных:')
        bot.register_next_step_handler(new_message, lambda m: title_waiting(m, film_ids))


def show_film_info(message: Message, film_id: int):
    """Вывод основной информации о фильме"""

    # Получение основной информации о фильме
    info = dict(
        zip(FSW_FILMS_TABLE_TITLES, cur.execute(f"SELECT * FROM Films WHERE film_id = ?", (film_id,)).fetchone()))

    hours_dur, minutes_dur = divmod(info['duration'], 60)
    if hours_dur > 0 and minutes_dur > 0:
        duration = f'{hours_dur}ч. {minutes_dur}мин.'
    elif hours_dur > 0 and minutes_dur == 0:
        duration = f'{hours_dur}ч.'
    else:
        duration = f'{minutes_dur}мин.'

    # Получение описания
    try:
        with open(info['description_file_name']) as image:
            description = image.read()
    except FileNotFoundError:
        description = 'None'

    # Текст в виде HTML-кода для выделения текста
    text = f"<b>{info['title']}</b>\n" \
           f"<u>Страна</u>: {info['country']}\n" \
           f"<u>Возрастной рейтинг</u>: {info['rating']}+\n" \
           f"<u>Длительность</u>: {duration}\n" \
           f"\t{description}"

    tg_info = cur.execute(f'SELECT * FROM Telegram WHERE id = ?', (message.chat.id,)).fetchall()

    # Запись в БД, какой фильм последним смотрел пользователь
    if not tg_info:
        cur.execute("INSERT INTO Telegram VALUES(?, ?, ?)", (message.chat.id, film_id, 0))
    else:
        cur.execute("UPDATE Telegram SET film_id = ? WHERE id = ?", (film_id, message.chat.id))
    db.commit()

    # Отправка всего сообщения с изображением и описанием
    try:
        with open(info['image_path'], 'rb') as image:
            bot.send_photo(
                message.chat.id, image, caption=text, parse_mode='HTML', reply_markup=ReplyKeyboardRemove())
    except FileNotFoundError:
        bot.send_message(message.chat.id, text=text, parse_mode='HTML', reply_markup=ReplyKeyboardRemove())

    # Вывод дней показа
    show_dates(message, film_id)


def show_dates(message: Message, film_id: int):
    """Вывод дней показа"""

    # Получение и фильтрация сеансов
    sessions = cur.execute(
        "SELECT DISTINCT year, month, day, hour, minute FROM Sessions WHERE film_id = ?", (film_id,)).fetchall()
    sessions = filter(lambda j: datetime.now() <= j, map(lambda x: datetime(*x), sessions))
    sessions = sorted(set(map(lambda j: j.date(), sessions)))

    # Создание клавиатуры с датами и кнопкой "Назад"
    markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    for i in sessions:
        markup.add(KeyboardButton(text=i.strftime(DATE_FORMAT)))
    markup.add(KeyboardButton(text=BACK_WORD))

    # Ожидание ввода правильноый даты
    new_message = bot.send_message(message.chat.id, 'Выберите день показа', reply_markup=markup)
    bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def date_waiting(message: Message, film_id: int):
    """Ожидание даты"""

    date_str = message.text
    # Если пользователь выбрал варимант "Назад", то он вернется к выбору фильма
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

        # При првильном вводе даты происходит:
        # 1. Формирование клавиатуры с сеансами и кнопкой "Назад"
        markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
        for i in sessions:
            markup.add(KeyboardButton(text=SESSION_FORMAT.format_map(i)))
        markup.add(KeyboardButton(text=BACK_WORD))

        # 2. Ожидание ввода сеанса в правильном формате
        new_message = bot.send_message(message.chat.id, 'Выберите сеанс', reply_markup=markup)
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))

    except ValueError:
        # При несоответствии формату происход повторное ожидание ввода
        new_message = bot.send_message(message.chat.id, 'Укажите корректную дату:')
        bot.register_next_step_handler(new_message, lambda m: date_waiting(m, film_id))


def session_waiting(message: Message, film_id: int, date_: date):
    """Ожидание времени сеанса"""

    # Если пользователь выбрал варимант "Назад", то он вернется к выбору дня
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

        # Формирование и отправка изображения зала с занятыми местами
        bot.send_photo(message.chat.id, draw_hall(ses_id, []),
                       f'Выберите места в зале.\n'
                       f'Добавить- "{ADD_PLACE_FORMAT}".\n'
                       f'Изменить- "{CHANGED_PLACE_FORMAT}".\n'
                       f'Удалить- "{DELETE_PLACE_FORMAT}".',
                       reply_markup=ReplyKeyboardRemove())

        # Ожидание ввода пользователя в правильном формате
        new_message = show_ordered_places(message, [])
        bot.register_next_step_handler(new_message, lambda m: order_place(m, ses_id, []))

    except ValueError:
        # При несоответствии формату происход повторное ожидание ввода
        new_message = bot.send_message(message.chat.id, 'Укажите сеанс в правильном формате:')
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))


def draw_hall(session_id: int, ordered_places: list):
    """Создание изображения зала"""

    # Получение уже купленных мест
    occupied_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()

    image = Image.new('RGB', HALL_IMAGE_SIZE, HALL_BACK_COLOR)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(ARIALMT, size=FONT_SIZE)

    # Отрисовка цифр по горизонтали
    y_s = (PLACE_HEIGHT - draw.textsize('1', font=font)[1]) // 2
    for col in range(1, HALL_COLUMNS + 1):
        x_c = (PLACE_WIDTH + LEN_BTWN_PLACES) * col + (PLACE_WIDTH - draw.textsize(str(col), font=font)[0]) // 2
        draw.text((x_c, y_s), str(col), font=font, fill=FONT_COLOR)

    # Отрисовка цифр по вертикали
    x_s = (PLACE_WIDTH - draw.textsize('1', font=font)[0]) // 2
    for row in range(1, HALL_ROWS + 1):
        y_c = (PLACE_HEIGHT + LEN_BTWN_PLACES) * row + (PLACE_HEIGHT - draw.textsize(str(row), font=font)[1]) // 2
        draw.text((x_s, y_c), str(row), font=font, fill=FONT_COLOR)

    # Отрисовка мест
    for row in range(1, HALL_ROWS + 1):
        for col in range(1, HALL_COLUMNS + 1):
            x_s, y_s = (PLACE_WIDTH + LEN_BTWN_PLACES) * col, (PLACE_HEIGHT + LEN_BTWN_PLACES) * row
            coors = ((x_s, y_s), (x_s + PLACE_WIDTH, y_s),
                     (x_s + PLACE_WIDTH, y_s + PLACE_HEIGHT), (x_s, y_s + PLACE_HEIGHT))

            # Цвет места
            row, col = row - 1, col - 1
            if (row, col) in occupied_places:
                color = OCCUPIED_COLOR
            elif (row, col) in ordered_places:
                color = ORDER_COLOR
            else:
                color = NORMAL_WINDOW_COLOR
            row, col = row + 1, col + 1
            draw.rectangle((coors[0], coors[2]), color)

            # Контур места
            for i in range(len(coors)):
                draw.line((coors[i], coors[(i + 1) % 4]), fill=LINE_COLOR, width=LINE_WIDTH)

    # Сохранение изображения в байтах
    bytes_list = BytesIO()
    image.save(bytes_list, format='PNG')
    bytes_list = bytes_list.getvalue()

    return bytes_list


def order_place(message: Message, session_id: int, ordered_places: list):
    """Заказ билета"""
    place_str = message.text
    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]

    # Покупка мест, если человек ввел слово "Купить"
    if place_str.lower() == BUY_WORD.lower():
        if not ordered_places:
            return send_places_info(message, session_id, ordered_places)
        else:
            # Если пользователь выбрал хотя бы одно место, то бот будет ожидать ввода данных банковской карты
            markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
            markup.add(KeyboardButton(text=BACK_WORD))
            markup.add(KeyboardButton(text=CANCEL_WORD))

            new_message = bot.send_message(message.chat.id,
                                           f'Укажите данные банковский карты в формате "{CARD_INFO_FORMAT}"',
                                           reply_markup=ReplyKeyboardRemove())
            bot.register_next_step_handler(new_message, lambda m: card_info_waiting(m, session_id, ordered_places))
            return

    # Если пользователь выбрал варимант "Назад", то он вернется к выбору дня
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

    # Добавление нового места
    occupied_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()
    if form == ADD_PLACE_FORMAT:
        row, column = place_dict['row'] - 1, place_dict['column'] - 1
        if 0 <= row < HALL_ROWS and 0 <= column < HALL_COLUMNS and len(ordered_places) < MAX_BUY_PLACES \
                and (row, column) not in occupied_places and (row, column) not in ordered_places:
            ordered_places.append((row, column))

    # Изменение места
    elif form == CHANGED_PLACE_FORMAT:
        index, row, column = place_dict['index'] - 1, place_dict['row'] - 1, place_dict['column'] - 1
        if 0 <= index < len(ordered_places) and (row, column) not in occupied_places:
            ordered_places[index] = (row, column)

    # Удаление места
    elif form == DELETE_PLACE_FORMAT:
        index = place_dict['index'] - 1
        if 0 <= index < len(ordered_places):
            del ordered_places[index]

    # Сортировка выбранных мест
    for i in range(1, -1, -1):
        ordered_places.sort(key=lambda x: x[i])

    # Отправка изображения зала
    send_places_info(message, session_id, ordered_places)


def show_ordered_places(message: Message, ordered_places: list):
    """Отправка сообщения с выбранными местами"""
    text = f'Купленные места: {TICKET_PRICE * len(ordered_places)}р\n' \
           + '\n'.join([f'{i + 1}. Ряд {p[0] + 1} Место {p[1] + 1}' for i, p in enumerate(ordered_places)])

    markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    if ordered_places:
        markup.add(KeyboardButton(text=BUY_WORD))
    markup.add(KeyboardButton(text=CANCEL_WORD))

    return bot.send_message(message.chat.id, text, reply_markup=markup)


def card_info_waiting(message: Message, session_id: int, ordered_places: list):
    """Ожидание ввода данных банковской карты"""
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

        # Покупка мест
        buy_tickets(message, session_id, ordered_places)
    except ValueError:
        new_message = bot.send_message(message.chat.id,
                                       f'Итог: {len(ordered_places) * TICKET_PRICE}Р\n'
                                       f'Укажите данные банковский карты в правильном формате "{CARD_INFO_FORMAT}"',
                                       reply_markup=ReplyKeyboardRemove())
        bot.register_next_step_handler(new_message, lambda m: card_info_waiting(m, session_id, ordered_places))


def buy_tickets(message: Message, session_id: int, ordered_places: list):
    """Покупка билета"""
    occupied_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()
    f_ordered_places = list(filter(lambda i: i not in occupied_places, ordered_places))
    if ordered_places != f_ordered_places:
        bot.send_message(message.chat.id, 'За время ожидания ответа некоторые выбранные места были куплены.')
        return send_places_info(message, session_id, f_ordered_places)

    user_id = message.from_user.id
    buy_time = datetime.now()
    req_ = f"INSERT INTO Tickets VALUES ({session_id}, ?, ?, {user_id}, {buy_time.year}, {buy_time.month}, " \
           f"{buy_time.day}, {buy_time.hour}, {buy_time.minute})"

    for place in ordered_places:
        cur.execute(req_, place)
        db.commit()

    qr_code_image = make_qrcode(message, session_id, ordered_places, buy_time)
    ordered_places = '\n'.join([f"{i + 1}. Ряд {p[0] + 1} Место {p[1] + 1}" for i, p in enumerate(ordered_places)])
    text = f'Спасибо за покупку 😀. Предъяевите этот QR-код проверяющему при входе в зал.\n{ordered_places}'

    markup = ReplyKeyboardMarkup(row_width=FILMS_KEYBOARD_WIDTH, resize_keyboard=RESIZE_MODE)
    markup.add(KeyboardButton(text=BACK_WORD))

    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]
    new_message = bot.send_photo(message.chat.id, qr_code_image, text)
    bot.register_next_step_handler(new_message, lambda m: answer_waiting(m, film_id))


def make_qrcode(message: Message, session_id: int, places: list, buy_time: datetime):
    """Создание qr-кода с купленными местами"""
    user_id = message.from_user.id

    film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]
    title = cur.execute("""SELECT title FROM Films WHERE film_id = ?""", (film_id,)).fetchone()[0]

    session_time = datetime(*cur.execute(
        """SELECT year, month, day, hour, minute FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone())

    places = '\n'.join([f"{i + 1}. Ряд {p[0] + 1} Место {p[1] + 1}" for i, p in enumerate(places)])

    text = f'user_id: {user_id}' \
           f'Время покупки: {buy_time.strftime(f"{DATE_FORMAT} {TIME_FORMAT}")}\n' \
           f'film_id: {film_id}\n' \
           f'Фильм: {title}\n' \
           f'session_id: {session_id}\n' \
           f'Время сеанса: {session_time.strftime(f"{DATE_FORMAT} {TIME_FORMAT}")}\n' \
           f'\n' \
           f'Купленные места:\n' \
           f'{places}'

    qr_code = make(text)

    arr = BytesIO()
    qr_code.save(arr, format='PNG')
    arr = arr.getvalue()

    return arr


def send_places_info(message: Message, session_id: int, ordered_places: list):
    bot.send_photo(message.chat.id, draw_hall(session_id, ordered_places))
    new_message = show_ordered_places(message, ordered_places)
    bot.register_next_step_handler(new_message, lambda m: order_place(m, session_id, ordered_places))


def answer_waiting(message: Message, film_id: int):
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
