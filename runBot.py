import telebot
from telebot import types
import sqlite3 as sql
from data.Secondary_functions import get_token, normalized_text
from data.Consts import PROJECT_DATABASE, COMMANDS
from random import sample


db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()
token = get_token('token.txt')
bot = telebot.TeleBot(token)


def show_film_info(message, name):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add('Заказать билеты')
    res = cur.execute(f"SELECT * FROM Films WHERE title='{name}'").fetchall()[0]
    sessions = cur.execute("SELECT * FROM Sessions WHERE film_id = "
                           f"(SELECT film_id FROM Films WHERE title = '{name}') "
                           "ORDER BY year, month, day, hour, minute, hall_id LIMIT 25").fetchall()
    if len(sessions) != 0:
        sess = '\nБлижайшие сеансы:\n' + \
               '\n'.join([f"{i + 1}) {':'.join(str(j) if len(str(j)) == 2 else '0' + str(j) for j in sessions[i][5:7])}"
                          f", {'.'.join(str(j) if len(str(j)) >= 2 else '0' + str(j) for j in sessions[i][4:1:-1])} "
                          f", Зал №{sessions[i][7]}" for i in range(len(sessions))])
    else:
        sess = '\nПока что нет ближайших сеансов'
    img = open(f'{res[7]}', 'rb')
    text = f"*{res[1]}*\nСтрана: {res[2]}\nВозрастной рейтинг: {res[3]}+\nДлительность: {res[4]} минут\n" + \
           ''.join([i for i in open(res[6]).readlines()]) + sess
    tg_info = cur.execute(f'SELECT * FROM Telegram WHERE id = "{message.chat.id}"').fetchall()
    if len(tg_info) == 0:
        cur.execute(f"INSERT INTO Telegram VALUES('{message.chat.id}', '{name}', {0})")
        db.commit()
    else:
        cur.execute(f"UPDATE Telegram SET film = '{name}' WHERE id = '{message.chat.id}'")
        db.commit()

    bot.send_photo(message.chat.id, img)
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')


def choose_seat():
    print('ok')


@bot.message_handler(commands=['start'])
def start_message(message):
    commands = '\n'.join([f'/{i} - {COMMANDS[i]}' for i in COMMANDS])
    bot.send_message(message.chat.id, "Привет ✌️ \nЯ FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                                      "а также заказать билеты. Ещё можно написать мне название фильма или жанра."
                                      f"\nМои команды:\n{commands}")


@bot.message_handler(commands=['random'])
def random_film(message):
    films = cur.execute("""SELECT DISTINCT Films.title, Films.film_id FROM Films 
        INNER JOIN Sessions ON Films.film_id = Sessions.film_id""").fetchall()
    film = sample(films, 1)
    bot.send_dice(message.chat.id)
    show_film_info(message, film[0][0])


@bot.message_handler(commands=['films'])
def avaible_films(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    films = cur.execute("""SELECT title, duration, rating FROM Films""").fetchall()
    if len(films) == 0:
        text = "К сожалению, у нас пока что нет доступных фильмов"
    else:
        text = "Вот список доступных фильмов:\n" + \
               "\n".join([f"{i + 1}) {films[i][0]} ({films[i][1]} минут, {films[i][2]}+)" for i in range(len(films))])
        for film in films:
            markup.add(types.KeyboardButton(film[0]))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == 'Заказать билеты')
def order_ticket(message):
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
def search_films(message):
    if message.text.isdigit():
        try:
            number = int(message.text)
            res = cur.execute(f"SELECT * FROM Telegram WHERE id = '{message.chat.id}'").fetchall()
            if len(res) == 0:
                return bot.send_message(message.chat.id, "Вы не выбрали фильм, чтобы называть номер сеанса")
            elif res[0][1] is None:
                return bot.send_message(message.chat.id, "Вы не выбрали фильм, чтобы называть номер сеанса")
            else:
                sessions = cur.execute("SELECT * FROM Sessions WHERE film_id = "
                                       f"(SELECT film_id FROM Films WHERE title = '{res[0][1]}') "
                                       "ORDER BY year, month, day, hour, minute, hall_id").fetchall()
                if number <= 0 or number > len(sessions):
                    return bot.send_message(message.chat.id, "Пожалуйста, введите корректный номер")
                return choose_seat()
        except Exception as e:
            return bot.send_message(message.chat.id, "Отправьте, пожалуйста, корректный номер")

    markup = types.ReplyKeyboardMarkup(row_width=1)
    films = cur.execute("""SELECT title, duration, rating FROM Films""").fetchall()
    res = []
    for info in films:
        if normalized_text(info[0]) == normalized_text(message.text):
            show_film_info(message, info[0])
            return True
        elif normalized_text(message.text) in normalized_text(info[0]):
            res.append(info)
    if len(res) == 0:
        text = 'К сожалению, мы не нашли ничего подходящего'
        markup = types.ReplyKeyboardRemove()
    else:
        text = 'Вот, что мне удалось найти:\n' + \
               "\n".join([f"{i + 1}) {res[i][0]} ({res[i][1]} минут, {res[i][2]}+)" for i in range(len(res))])
        for film in res:
            markup.add(types.KeyboardButton(film[0]))
    bot.send_message(message.chat.id, text, reply_markup=markup)


bot.infinity_polling()
db.close()