import telebot
from data.Secondary_functions import get_token


token = get_token('token.txt')
bot = telebot.Telebot(token)


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id,"Привет ✌️ ")
bot.infinity_poling()