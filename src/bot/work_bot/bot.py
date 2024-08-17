from ..config import MAIN_BOT_TOKEN, WORK_BOT_TOKEN
from ..exceptions import exceptions_catcher, NotFound
from ..logs import addLog
from .. import utils
from ..state_machine import *
from ..db import connect, asyncpg_errors
from ..works import getWorkTitle
from ..tg_api.queries import telegram_api_request

import sys
import uuid
import json
import telebot
import asyncio
import datetime
import traceback
from textwrap import dedent


# Telegram Bot API configuration
bot = telebot.TeleBot(token=WORK_BOT_TOKEN)
main_bot = telebot.TeleBot(token=MAIN_BOT_TOKEN)
keyboard_obj = telebot.types.InlineKeyboardMarkup
button_obj = telebot.types.InlineKeyboardButton



# Catching all the "/start" in the chat
@bot.message_handler(commands=['start'])
def firstRun(message):
    user_id = message.from_user.id
    start_text = message.text.split()

    if len(start_text) > 1:
        worker_add_id = str(start_text[1])
        asyncio.run(addWorker(message, worker_add_id))
    else:
        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *❌ RentalerWork доступен только по ссылке-приглашению.*

                Для получения ссылки обратитесь к своему работодателю.
                '''
            ),
            parse_mode="Markdown",
        )


async def addWorker(message: telebot.types.Message, worker_add_id: str) -> None:
    user_id = message.from_user.id
    now = datetime.datetime.now

    conn = await connect()
    try:
        query = '''
            SELECT "userID", "workerID"
            FROM "userWorkers"
            WHERE "addID" = $1
        '''
        user_worker_data = (await conn.fetchrow(query, worker_add_id))
    finally:
        await conn.close()

    if user_worker_data is None:
        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f"*❌ Данная ссылка-приглашение не действительна.*"
            ),
            parse_mode="Markdown",
        )
    else:
        worker_id = user_worker_data[1]
        if worker_id:
            await start(message)
        else:
            conn = await connect()
            try:
                stmt_workers = '''
                    INSERT INTO workers (id, "regDate")
                    VALUES ($1, $2)
                '''
                await conn.fetchval(stmt_workers, user_id, now())
            except asyncpg_errors['UniqueViolationError']:
                pass
            finally:
                stmt_user_workers = '''
                    UPDATE "userWorkers"
                    SET "workerID" = $1, "isActive" = true
                    WHERE "addID" = $2
                '''
                await conn.execute(stmt_user_workers, user_id, worker_add_id)

                landlord_user_id = user_worker_data[0]
                landlord_username = (await utils.getUsername(main_bot, landlord_user_id))
                bot.send_message(
                    chat_id=user_id,
                    text=dedent(
                        f'''
                        ✅ *{landlord_username}* назначил Вас своим сотрудником.
                        
                        Теперь Вам будут приходить уведомления о новых запланированных задачах.
                        '''
                    ),
                    parse_mode="Markdown",
                )

                username = (await utils.getUsername(bot, user_id))
                await telegram_api_request(
                    request_method='POST',
                    api_method='sendMessage',
                    parameters={
                        'chat_id': landlord_user_id,
                        'text': dedent(
                            f'''
                            ✅ Ваш сотрудник *{username}* подключился к системе RentalerWork.

                            Теперь его аккаунт активен и Вы можете ставить ему задачи.
                            '''),
                        'parse_mode': 'Markdown',
                    },
                    bot='main'
                )

                await conn.close()

# Getter of any text messenges in the chat
@bot.message_handler(content_types='text')
def main(message):
    asyncio.run(start(message))


@exceptions_catcher
@autoSetState(bot='work')
async def start(message: telebot.types.Message=None, user_id: int=None) -> None:
    "Outputs the start menu."

    if user_id is None:
        user_id = message.from_user.id

    greeting = await utils.greeting()
    name = await utils.getUsername(bot, user_id)

    keyboard = keyboard_obj()

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''*{greeting}, {name}!*'''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


if __name__ == '__main__':
    while True: 
        try:    
            bot.polling(none_stop=True)
        except Exception as e:
            asyncio.run(addLog(level='critical', text=traceback.format_exc(), send_telegram_message=True))
        asyncio.run(asyncio.sleep(1))