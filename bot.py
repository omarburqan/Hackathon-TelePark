import secret_settings

import pymongo
import logging
from telegram import Update, ReplyKeyboardMarkup, ParseMode
from telegram.ext import CommandHandler, CallbackContext, Updater
import time
from random import randint
from prettytable import PrettyTable
import datetime

TOTAL_PARKING_SPOTS = 4


# bot commands #


def help_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text=get_bot_description())


def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    logger.info(f"> Start chat #{chat_id}")
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    user = employees.find_one({'user_id': chat_id})
    if not user:
        user = {'user_id': chat_id, 'name': update.message.from_user.first_name,
                'license plate': randint(103, 200), 'rank': 2, 'points': 0}
        employees.replace_one({'user_id': chat_id}, user, upsert=True)
        context.bot.send_message(chat_id=chat_id,
                                 text=f"🚗️ Welcome {user['name']}! 🚗️\nI'am TelePark 🤖, Your parking manager",
                                 reply_markup=generate_button("free"))
    else:
        parks = db.get_collection('final_list')
        user_with_parks = parks.find_one({'user_id': chat_id})
        waiting_list = db.get_collection('request_list')
        user_waiting = waiting_list.find_one({'user_id': chat_id})
        if not user_with_parks and not user_waiting:
            context.bot.send_message(chat_id=chat_id,
                                     text=f"🚗️ Welcome {user['name']}! 🚗️\nI'am TelePark 🤖, Your parking manager",
                                     reply_markup=generate_button('free'))
        else:
            context.bot.send_message(chat_id=chat_id,
                                     text=f"🚗️ Welcome {user['name']}! 🚗️\nI'am TelePark 🤖, Your parking manager",
                                     reply_markup=generate_button('book'))


def users(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    res = []
    for user in employees.find():
        res.append(user['name'])
    context.bot.send_message(chat_id=chat_id, text=', '.join(res), parse_mode=ParseMode.MARKDOWN)


def status_tomorrow(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    final_list = db.get_collection('final_list')
    request_list = db.get_collection('request_list')
    employees = db.get_collection('employees')
    table = PrettyTable()
    table.title = 'Parking slots'
    table.field_names = ["name", "rank", "points"]
    count = 0
    for user in final_list.find():
        user = employees.find_one({'user_id': user['user_id']})
        table.add_row([user['name'], user['rank'], user['points']])
        count += 1
    for waiting_user in request_list.find().sort(
            [('points', pymongo.DESCENDING), ('time', pymongo.ASCENDING)]):
        if count == TOTAL_PARKING_SPOTS:
            break
        user = employees.find_one({'user_id': waiting_user['user_id']})
        table.add_row([user['name'], user['rank'], user['points']])
        count += 1
    for i in range(TOTAL_PARKING_SPOTS - count):
        table.add_row(['---', '---', '---'])
    text = f"""```{table.get_string()}```"""
    context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)


def book_tmrw(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    logger.info(f"= Got on chat #{chat_id}")
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    user_info = employees.find_one({'user_id': chat_id})  # return a dictionary
    if user_info['rank'] == 1:
        seniors_spot = db.get_collection('final_list')
        seniors_spot.replace_one({"user_id": chat_id}, {"user_id": chat_id, "time": time.time()},
                                 upsert=True)
        res = "Dear senior employee,a parking spot has been booked successfully ✔️"
    else:
        requests = db.get_collection('request_list')
        requests.replace_one({"user_id": chat_id},
                             {"user_id": chat_id, "points": user_info["points"],
                              "time": time.time()},
                             upsert=True)
        res = 'We received your request ✍🏼, we will reply to you 🔜'

        context.bot.send_message(chat_id=chat_id, text=res, reply_markup=generate_button('book'))
        status_tomorrow(update, context)


def free_tmrw(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    user_info = employees.find_one({'user_id': chat_id})  # return a dictionary
    if user_info['rank'] == 1:
        seniors_spot = db.get_collection('final_list')
        seniors_spot.delete_one({'user_id': chat_id})
    else:
        juniors_spot = db.get_collection('request_list')
        juniors_spot.delete_one({'user_id': chat_id})
    res = "Thank you for releasing the spot for another great worker tomorrow 👋."
    context.bot.send_message(chat_id=chat_id, text=res, reply_markup=generate_button('free'))


def send_plan(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    final_list = db.get_collection('final_list')
    if final_list.find_one({'user_id': chat_id}):
        context.bot.send_message(chat_id=chat_id,
                                 text="Your request has been accepted, you can park tomorrow ✔️")
    else:
        context.bot.send_message(chat_id=chat_id,
                                 text="Your request has been rejected, no parking for you! ❌")


# helper methods #

def user_as_string(user):
    return f"{user['user_id']} {user['name']} {user['license plate']} " \
           f"{user['rank']} {user['points']}\n"


def update_final_list(context: CallbackContext):
    db = client.get_database('parking_db')
    final_list = db.get_collection('final_list')
    empty_spots = TOTAL_PARKING_SPOTS - final_list.count()
    request_list = db.get_collection('request_list')
    accept_text = 'your request has been accepted, you can park tomorrow'
    reject_text = 'your request has been rejected, no parking for you!'
    for waiting_user in request_list.find().sort(
            [('points', pymongo.DESCENDING), ('time', pymongo.ASCENDING)]):
        if not empty_spots:  # empty == 0
            context.bot.send_message(chat_id=waiting_user['user_id'], text=reject_text)
        else:
            final_list.replace_one({'user_id': waiting_user['user_id']},
                                   {'user_id': waiting_user['user_id']}, upsert=True)
            context.bot.send_message(chat_id=waiting_user['user_id'], text=accept_text)
            empty_spots -= 1


def get_bot_description():
    return """Hello there👋 
This is a company's parking lot management system 🅿
Please note that there are parking spots that are fixed for specific employees😊
You can book/free parking spot from 8 pm to 7 am the next day
After 7 A.m., a list is decided and a message is sent in accordance to the decision to anyone who has requested a parking
The decision is made according to the staff score💯
Commands description:
/users :  Show info on all users
/free_tmrw : Release parking spot that has been booked
/book_tmrw : Ask for parking spot
/status_tmrw : Displays the current parking status
"""


def generate_button(data):
    if data == 'free':
        basic_buttons = [['/users', '/help'], ['/book_tmrw', '/status_tmrw']]
    else:
        basic_buttons = [['/users', '/help'], ['/free_tmrw', '/status_tmrw']]
    return ReplyKeyboardMarkup(basic_buttons)


# db #

def create_request_list():
    db = client.get_database('parking_db')
    requests = db.get_collection('request_list')
    requests.delete_many({})
    requests.create_index([('user_id', pymongo.ASCENDING)])


def creat_users():
    liwaa_id = 1044776988
    tameer_id = 836471985
    omar_id = 574225603
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    employees.delete_many({})
    employees.create_index([('user_id', pymongo.ASCENDING)])
    employees.replace_one({'user_id': liwaa_id},
                          {'user_id': liwaa_id, 'name': 'liwaa', 'license plate': 100, 'rank': 1,
                           'points': 17},
                          upsert=True)

    employees.replace_one({'user_id': tameer_id},
                          {'user_id': tameer_id, 'name': 'tameer', 'license plate': 101, 'rank': 1,
                           'points': 33},
                          upsert=True)
    employees.replace_one({'user_id': omar_id},
                          {'user_id': omar_id, 'name': 'omar', 'license plate': 102, 'rank': 1,
                           'points': 28},
                          upsert=True)
    employees.replace_one({'user_id': 908413173},
                          {'user_id': 908413173, 'name': 'ibrahim', 'license plate': 104, 'rank': 2,
                           'points': 30},
                          upsert=True)


def create_final_list():
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    final_list = db.get_collection('final_list')
    final_list.create_index([('user_id', pymongo.ASCENDING)])
    final_list.delete_many({})
    for employee in employees.find():
        if employee['rank'] == 1:
            final_list.replace_one({'user_id': employee['user_id']},
                                   {'user_id': employee['user_id']},
                                   upsert=True)


if __name__ == '__main__':
    client = pymongo.MongoClient()

    creat_users()
    create_request_list()
    create_final_list()

    logging.basicConfig(
        format='[%(levelname)s %(asctime)s %(module)s:%(lineno)d] %(message)s',
        level=logging.INFO)

    logger = logging.getLogger(__name__)

    updater = Updater(token=secret_settings.BOT_TOKEN, use_context=True)

    dispatcher = updater.dispatcher

    jobs = updater.job_queue
    jobs.run_daily(update_final_list, datetime.datetime(datetime.datetime.now().year,
                                                        datetime.datetime.now().month,
                                                        datetime.datetime.now().day, 9, 0, 0))

    help_handler = CommandHandler('help', help_command)
    dispatcher.add_handler(help_handler)

    start_handler = CommandHandler('start', start, )
    dispatcher.add_handler(start_handler)

    users_handler = CommandHandler('users', users, )
    dispatcher.add_handler(users_handler)

    free_handler = CommandHandler('free_tmrw', free_tmrw, )
    dispatcher.add_handler(free_handler)

    book_tomorrow_handler = CommandHandler('book_tmrw', book_tmrw, )
    dispatcher.add_handler(book_tomorrow_handler)

    users_handler = CommandHandler('status_tmrw', status_tomorrow, )
    dispatcher.add_handler(users_handler)

    send_plan_handler = CommandHandler('send_plan', send_plan, )
    dispatcher.add_handler(send_plan_handler)

    logger.info("* Start polling...")
    updater.start_polling()  # Starts polling in a background thread.
    updater.idle()  # Wait until Ctrl+C is pressed
    logger.info("* Bye!")
