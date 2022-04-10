import telebot
from telebot import types
import sqlite3 as sql
from data.Secondary_functions import get_token, normalized_text
from data.Consts import PROJECT_DATABASE, COMMANDS


db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()
token = get_token('token.txt')
bot = telebot.TeleBot(token)


def show_film_info(message, name):  # TODO дополнить показом ближайших сеансов на неделю
    markup = types.ReplyKeyboardMarkup(row_width=1)
    res = cur.execute(f"SELECT * FROM Films WHERE title='{name}'").fetchall()[0]
    img = open(f'{res[7]}', 'rb')
    text = f"*{res[1]}*\nСтрана: {res[2]}\nВозрастной рейтинг: {res[3]}+\nДлительность: {res[4]} минут\n" + \
           ''.join([i for i in open(res[6]).readlines()])
    bot.send_photo(message.chat.id, img)
    bot.send_message(message.chat.id, text, parse_mode='Markdown')


@bot.message_handler(commands=['start'])
def start_message(message):
    commands = '\n'.join([f'/{i} - {COMMANDS[i]}' for i in COMMANDS])
    bot.send_message(message.chat.id, "Привет ✌️ \nЯ FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                                      "а также заказать билеты. Ещё можно написать мне название фильма или жанра."
                                      f"\nМои команды:\n{commands}")


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


@bot.message_handler(content_types='text')
def search_films(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    films = cur.execute("""SELECT title, duration, rating FROM Films""").fetchall()
    result = []
    for info in films:
        if normalized_text(info[0]) == normalized_text(message.text):
            show_film_info(message, info[0])
            return True
        elif normalized_text(message.text) in normalized_text(info[0]):
            result.append(info)
    if len(result) == 0:
        text = 'К сожалению, мы не нашли ничего подходящего'
    else:
        text = 'Вот, что мне удалось найти:\n' + \
               "\n".join([f"{i + 1}) {films[i][0]} ({films[i][1]} минут, {films[i][2]}+)" for i in range(len(films))])
        for film in films:
            markup.add(types.KeyboardButton(film[0]))
    bot.send_message(message.chat.id, text, reply_markup=markup)


bot.infinity_polling()
db.close()