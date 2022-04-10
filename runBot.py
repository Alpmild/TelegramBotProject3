import telebot
import sqlite3 as sql
from data.Secondary_functions import get_token
from data.Consts import PROJECT_DATABASE


db = sql.connect(PROJECT_DATABASE, check_same_thread=False)
cur = db.cursor()
token = get_token('token.txt')
bot = telebot.TeleBot(token)


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "Привет ✌️ \nЯ FilmBot, ты можешь посмотреть сеансы фильмов и свободные места, "
                                      "а также заказать билеты.\nМои команды:\n```films``` - посмотреть список"
                                      " доступных фильмов\n")


@bot.message_handler(commands=['films'])
def avaible_films(message):
    films = cur.execute("""SELECT title, duration, rating FROM Films""").fetchall()
    if len(films) == 0:
        text = "К сожалению, у нас пока что нет доступных фильмов"
    else:
        text = "Вот список доступных фильмов:\n" + \
               "\n".join([f"{i + 1}) {films[i][0]} ({films[i][1]} минут, {films[i][2]}+)" for i in range(len(films))])
    bot.send_message(message.chat.id, text)


bot.infinity_polling()
db.close()