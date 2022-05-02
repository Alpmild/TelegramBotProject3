import sqlite3 as sql
from io import BytesIO, TextIOWrapper
from datetime import datetime
from pprint import pp

from data.Consts import *


output = BytesIO()
wrapper = TextIOWrapper(output, encoding='utf-8', write_through=True)

db = sql.connect('DataBases\\DataBase.sqlite')
cur = db.cursor()

result = cur.execute("""SELECT session_id, row, column, year, month, day, hour, minute FROM Tickets WHERE user_id = ?""", (522098052,)).fetchall()
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
new_data = dict()
for time_ in sorted(data.keys()):
    text += time_.strftime(f'{DATE_FORMAT} {TIME_FORMAT}:\n')

    for session_id in data[time_]:
        film_id = cur.execute("""SELECT film_id FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()[0]
        title = cur.execute("""SELECT title FROM Films WHERE film_id = ?""", (film_id,)).fetchone()[0]

        session_time = cur.execute("""SELECT year, month, day, hour, minute FROM Sessions WHERE session_id = ?""", (session_id,)).fetchone()
        session_time = datetime(*session_time)

        text += f"\t{title} Сеанс на " + session_time.strftime(f'{DATE_FORMAT} {TIME_FORMAT}:\n')

        n = len(data[time_][session_id])
        ordered_places = '\n'.join([f'\t\t{i + 1}. Ряд {p[0] + 1} Место {p[1] + 1}' for i, p in enumerate(data[time_][session_id])])

        text += f'{ordered_places}\n' \
                f'\t\tИтог: {TICKET_PRICE * n}р\n\n'


text = text.rstrip('\n')
wrapper.write(text)
print(output.getvalue())

