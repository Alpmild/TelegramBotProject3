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
           f"\t{description}\n"

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

        new_message = bot.send_photo(
            message.chat.id,
            draw_hall(ses_id),
            f'Выберите места в зале. Формат-"{PLACE_FORMAT}". Пример-"{PLACE_FORMAT.format(row=3, column=5)}".\n'
            f'Максимум-{MAX_BUY_PLACES}.')

        raise ValueError

    except ValueError:
        new_message = bot.send_message(message.chat.id, 'Укажите сеанс в правильном формате:')
        bot.register_next_step_handler(new_message, lambda m: session_waiting(m, film_id, date_))


def draw_hall(session_id: int):
    """Создание изображения зала"""
    ordered_places = cur.execute("""SELECT row, column FROM Tickets WHERE session_id = ?""", (session_id,)).fetchall()

    image = Image.new('RGB', HALL_IMAGE_SIZE, HALL_BACK_COLOR)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(ARIALMT, size=FONT_SIZE)

    y_s = (PLACE_HEIGHT - draw.textsize('1', font=font)[1]) // 2
    for x in range(1, HALL_COLUMNS + 1):
        x_c = (PLACE_WIDTH + LEN_BTWN_PLACES) * x + (PLACE_WIDTH - draw.textsize(str(x), font=font)[0]) // 2
        draw.text((x_c, y_s), str(x), font=font, fill=FONT_COLOR)

    x_s = (PLACE_WIDTH - draw.textsize('1', font=font)[0]) // 2
    for y in range(1, HALL_ROWS + 1):
        y_c = (PLACE_HEIGHT + LEN_BTWN_PLACES) * y + (PLACE_HEIGHT - draw.textsize(str(y), font=font)[1]) // 2
        draw.text((x_s, y_c), str(y), font=font, fill=FONT_COLOR)

    for y in range(1, HALL_ROWS + 1):
        for x in range(1, HALL_COLUMNS + 1):
            x_s, y_s = (PLACE_WIDTH + LEN_BTWN_PLACES) * x, (PLACE_HEIGHT + LEN_BTWN_PLACES) * y
            coors = ((x_s, y_s), (x_s + PLACE_WIDTH, y_s),
                     (x_s + PLACE_WIDTH, y_s + PLACE_HEIGHT), (x_s, y_s + PLACE_HEIGHT))

            color = OCCUPIED_COLOR if (y, x) in ordered_places else NORMAL_LINE_COLOR
            draw.rectangle((coors[0], coors[2]), color)

            for i in range(len(coors)):
                draw.line((coors[i], coors[(i + 1) % 4]), fill=LINE_COLOR, width=LINE_WIDTH)

    bytes_list = BytesIO()
    image.save(bytes_list, format='PNG')
    bytes_list = bytes_list.getvalue()

    return bytes_list


def check_sessions(film_id: int):
    try:
        sessions = cur.execute(
            """SELECT year, month, day, hour, month, day FROM Sessions WHERE film_id = ?""", (film_id,)).fetchall()
        return bool(filter(lambda i: datetime(*i) >= datetime.now(), sessions))
    except sql.InterfaceError:
        return False


bot.infinity_polling()
db.close()
