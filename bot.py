import secret_settings

import pymongo
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, Updater, CallbackQueryHandler
import time

TOTAL_PARKING_SPOTS = 3


def get_bot_description():
    return 'help'


def button(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    text_command = update.callback_query.data
    if text_command == 'help':
        response = get_bot_description()
        context.bot.send_message(chat_id=chat_id,
                                 text=response)
    elif text_command == 'commands':
        response = 'Here a list of all commands you can do'
        keyboard = [
            [InlineKeyboardButton("Book", callback_data='book_tmrw'),
             InlineKeyboardButton("Free", callback_data='free_spot'),
             InlineKeyboardButton("Status", callback_data='status_tmrw'),
             InlineKeyboardButton("Users", callback_data='users'),
             InlineKeyboardButton("Plan", callback_data='send_plan')
             ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(chat_id=chat_id,
                                 text=response, reply_markup=reply_markup)
    else:
        if text_command == 'book_tmrw':
            book_tmrw(update, context)
        elif text_command == 'free_spot':
            free_spot(update, context)
        elif text_command == 'status_tmrw':
            status_tomorrow(update, context)
        elif text_command == 'users':
            users(update,context)
        elif text_command == 'send_plan':
            send_plan(update,context)

# bot commands #

def start(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    logger.info(f"> Start chat #{chat_id}")
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    keyboard = [
        [InlineKeyboardButton("Help", callback_data='help'),
         InlineKeyboardButton("Command", callback_data='commands'),
         ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    for user in employees.find({'user_id': chat_id}):
        context.bot.send_message(chat_id=chat_id,
                                 text=f"💣 Welcome! 💣 {user['name']}",
                                 reply_markup=reply_markup)


def users(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    employees = db.get_collection('employees')
    res = 'user_id - name - license plate - rank - points\n'
    for user in employees.find():
        res += user_as_string(user)
    context.bot.send_message(chat_id=chat_id, text=res)


def status_tomorrow(update: Update, context: CallbackContext):
    # print final list
    chat_id = update.effective_chat.id
    db = client.get_database('parking_db')
    final_list = db.get_collection('final_list')
    request_list = db.get_collection('request_list')
    employees = db.get_collection('employees')
    res = 'user_id - name - license plate - rank - points\n'
    count = 0
    for user in final_list.find():
        res += user_as_string(employees.find_one({'user_id': user['user_id']}))
        count += 1
    for waiting_user in request_list.find().sort(
            [('user_id', pymongo.DESCENDING), ('time', pymongo.DESCENDING)]):
        if count == TOTAL_PARKING_SPOTS:
            break
        res += user_as_string(employees.find_one({'user_id': waiting_user['user_id']}))
        count += 1
    res += f'empty * {TOTAL_PARKING_SPOTS - count}'
    context.bot.send_message(chat_id=chat_id, text=res)


def book_tmrw(update : Update,context :CallbackContext):
    chat_id = update.effective_chat.id
    logger.info(f"= Got on chat #{chat_id}")
    db = client.get_database('parking_db')
    requests = db.get_collection('request_list')
    requests.replace_one(
        {"user_id": chat_id},
        {"user_id": chat_id, "time": time.time()},
        upsert=True
    )
    res = 'we received your request, we will reply to you soon'
    context.bot.send_message(chat_id=chat_id, text=res)


def free_spot(update : Update , context : CallbackContext):
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
    res = "thank you for releasing the spot for another great worker tmrw."
    context.bot.send_message(chat_id=chat_id, text=res)



def send_plan(update: Update, context: CallbackContext):
    pass


# helper methods #

def user_as_string(user):
    return f"{user['user_id']} {user['name']} {user['license plate']} " \
        f"{user['rank']} {user['points']}\n"


def update_final_list():
    pass


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
                           'points': 0},
                          upsert=True)
    employees.replace_one({'user_id': tameer_id},
                          {'user_id': tameer_id, 'name': 'tameer', 'license plate': 101, 'rank': 2,
                           'points': 0},
                          upsert=True)
    employees.replace_one({'user_id': omar_id},
                          {'user_id': omar_id, 'name': 'omar', 'license plate': 102, 'rank': 2,
                           'points': 0},
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
    updater.dispatcher.add_handler(CallbackQueryHandler(button))

    start_handler = CommandHandler('start', start, )
    dispatcher.add_handler(start_handler)

    users_handler = CommandHandler('users', users, )
    dispatcher.add_handler(users_handler)

    free_handler = CommandHandler('free_tmrw', free_spot, )
    dispatcher.add_handler(free_handler)

    book_tomorrow_handler = CommandHandler('book_tmrw', book_tmrw, )
    dispatcher.add_handler(book_tomorrow_handler)

    users_handler = CommandHandler('status_tmrw', status_tomorrow, )
    dispatcher.add_handler(users_handler)

    users_handler = CommandHandler('send_plan', status_tomorrow, )
    dispatcher.add_handler(users_handler)

    logger.info("* Start polling...")
    updater.start_polling()  # Starts polling in a background thread.
    updater.idle()  # Wait until Ctrl+C is pressed
    logger.info("* Bye!")
