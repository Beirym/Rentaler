from ..config import MAIN_BOT_TOKEN
from ..exceptions import exceptions_catcher, NotFound
from ..logs import addLog
from .. import utils
from ..state_machine import *
from ..db import connect, asyncpg_errors
from ..works import getWorkTitle
from ..pagination import paginator

import sys
import uuid
import json
import telebot
import asyncio
import datetime
import traceback
from textwrap import dedent
import collections


# Telegram Bot API configuration
bot = telebot.TeleBot(token=MAIN_BOT_TOKEN)
keyboard_obj = telebot.types.InlineKeyboardMarkup
button_obj = telebot.types.InlineKeyboardButton


# Catching all the "/start" in the chat
@bot.message_handler(commands=['start'])
def firstRun(message):
    asyncio.run(addUser(message))

async def addUser(message: telebot.types.Message) -> None:
    '''Retrieves the user_id from the message and tries to add it to the database.
    If the attempt ends with an error, it returns the bot start menu.'''

    user_id = message.from_user.id
    now = datetime.datetime.now

    conn = await connect()
    try:
        stmt = '''
            INSERT INTO users (id, "regDate")
            VALUES ($1, $2)
        '''
        await conn.execute(stmt, user_id, now())
    except asyncpg_errors['UniqueViolationError']:
        await start(message)
    finally:
        await conn.close()


# Getter of any text messenges in the chat
@bot.message_handler(content_types='text')
def main(message):
    asyncio.run(start(message))

@exceptions_catcher
@autoSetState()
async def start(message: telebot.types.Message=None, user_id: int=None) -> None:
    "Outputs the start menu."

    if user_id is None:
        user_id = message.from_user.id

    greeting = await utils.greeting()
    name = await utils.getUsername(bot, user_id)

    keyboard = keyboard_obj()
    keyboard.add(button_obj(text='🛠 Инструменты', callback_data='start_func-toolsMenu'))
    keyboard.add(button_obj(text='🏠 Мои объекты', callback_data='start_func-propertiesMenu'))
    keyboard.add(button_obj(text='🧑🏼‍🔧 Мои сотрудники', callback_data=f'start_func-workersMenu'))

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''*{greeting}, {name}!*'''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# Tools

@exceptions_catcher
@autoSetState()
async def toolsMenu(message: telebot.types.Message=None, user_id: int=None) -> None:
    if user_id is None:
        user_id = message.from_user.id

    keyboard = keyboard_obj()
    keyboard.add(button_obj(text='🧴 Клининг', callback_data='start_func-cleaning'))
    keyboard.add(button_obj(text='📝 Текст для заселения', callback_data='start_func-clients_text'))
    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *🛠 Инструменты*

            *🧴 Клининг* - учёт и планирование уборок на объектах.
            *📝 Текст для заселения* - составление текста с информацией о заселении для арендатора.
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


@exceptions_catcher
@autoSetState()
async def cleaningMenu(message: telebot.types.Message=None, user_id: int=None) -> None:
    if user_id is None:
        user_id = message.from_user.id

    keyboard = keyboard_obj()
    keyboard.add(button_obj(text='➕ Запланировать уборку', callback_data='start_func-addCleaning'))
    keyboard.add(button_obj(text='🗂 Архив уборок', callback_data='start_func-cleaningsArchive'))
    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

    scheduled_cleaning = 0
    completed_cleaning = 0

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *🧴 Клининг*

            Запланированных уборок: {scheduled_cleaning}
            Выполненных уборок: {completed_cleaning}
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

# /. Tools


# Properties

@exceptions_catcher
@autoSetState
async def propertiesMenu(message: telebot.types.Message=None, user_id: int=None) -> None:
    ...

# /. Properties


# Workers

@exceptions_catcher
@autoSetState()
async def workersMenu(message: telebot.types.Message=None, user_id: int=None) -> None:
    if user_id is None:
        user_id = message.from_user.id

    keyboard = keyboard_obj()
    keyboard.add(button_obj(text='➕ Добавить сотрудника', callback_data='start_func-addWorker'))
    keyboard.add(button_obj(text='🗂 Список сотрудников', callback_data='start_func-workersList'))
    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

    conn = await connect()
    try:
        workers_query = '''SELECT COUNT(id) FROM "userWorkers" WHERE "userID" = $1'''
        active_workers_query = '''SELECT COUNT(id) FROM "userWorkers" WHERE "userID" = $1 AND "isActive" IS TRUE'''

        workers = (await conn.fetchrow(workers_query, user_id))[0]
        active_workers = (await conn.fetchrow(active_workers_query, user_id))[0]
    finally:
        await conn.close()

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *🧑🏼‍🔧 Мои сотрудники*

            🦺 Всего *{workers}* сотрудников, из них *{active_workers}* активных.
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

@exceptions_catcher
@autoSetState()
async def addWorker(message: telebot.types.Message=None, user_id: int=None, work_id: int=None) -> None:
    if user_id is None:
        user_id = message.from_user.id

    keyboard = keyboard_obj()
    back_button = button_obj(text='⬅️ Назад', callback_data='start_func-back')

    if work_id is None:
        keyboard.add(button_obj(text='🧴 Клининг', callback_data='start_func-addWorker-work_id=1'))
        keyboard.add(back_button)

        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *➕ Добавление сотрудника*

                🔧 Выберите вид работ, которые будут входить в обязаности Вашего сотрудника.
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    else:
        keyboard.add(back_button)

        message = bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *➕ Добавление сотрудника*

                🧑🏼‍🔧 Введите имя человека, которого назначаете своим сотрудником.

                _При необходимости, Вы также можете указать его номер телефона через запятую от имени. (Пример: Павел, +79008007060)._
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

        def nextStepHandler(message):
            asyncio.run(confirmWorkerData(message))
        bot.register_next_step_handler(message, nextStepHandler)


    async def confirmWorkerData(message):
        message_parts = message.text.split(',')
        name = message_parts[0]
        if len(message_parts) > 1:
            number = message_parts[1]
        else:
            number = None

        if (len(name) > 36) or (number != None and len(number) > 20):
            keyboard = keyboard_obj()
            keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

            bot.send_message(
                chat_id=user_id,
                text=dedent(
                    f'''
                    *❌ Слишком длинное имя или номер!*

                    Максимальная длина имени - *36 символов*, номера телефона - *20*.
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

        else:
            worker_data = json.dumps({
                'work_id': work_id,
                'name': name,
                'number': number,
            })
            worker_data_key = str(uuid.uuid4())[:8]
            redis = await getRedisConnection()
            redis.set(worker_data_key, worker_data)

            keyboard = keyboard_obj()
            keyboard.row(
                button_obj(
                    text='✅ Подтвердить',
                    callback_data=f'start_func-createWorkerAddLink-worker_data_key="{worker_data_key}"'
                ),
                button_obj(text='❌ Отмена', callback_data='start_func-workersMenu')
            )
            keyboard.add(back_button)

            bot.send_message(
                chat_id=user_id,
                text=dedent(
                    f'''
                    *➕ Добавление сотрудника*

                    Перепроверьте указанную Вами информацию о сотруднике. Если все данные верны - нажмите на кнопку *"Подтвердить"*

                    *🪪 Имя*: {name}
                    *☎️ Номер телефона*: {number if number else 'не указан'}
                    *⚒  Вид работ*: {getWorkTitle(work_id, add_emoji=True)}
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

@exceptions_catcher
async def createWorkerAddLink(user_id: int, worker_data_key: str) -> None:
    redis = await getRedisConnection()
    worker_data = json.loads(redis.get(worker_data_key))
    redis.delete(worker_data_key)

    worker_add_id = str(uuid.uuid4())
    worker_activation_link = f'https://t.me/RentalerWorkBot?start={worker_add_id}'

    conn = await connect()
    try:
        stmt = '''
            INSERT INTO "userWorkers" ("userID", "workID", "workerName", "workerNumber", "addDate", "addID")
            VALUES ($1, $2, $3, $4, $5, $6)
        '''
        await conn.execute(
            stmt, 
            user_id, 
            worker_data['work_id'], 
            worker_data['name'],
            worker_data['number'],
            datetime.datetime.now(),
            worker_add_id
        )
    finally:
        await conn.close()

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *📥 Сотрудник добавлен в базу*

            Перешлите своему сотруднику, указанную ниже ссылку. 
            Он должен перейти по ней и запустить бота _RentalerWork_, после этого
            его профиль активируется и Вы сможете назначать ему задачи.

            *🔗 Ссылка для сотрудника:* `{worker_activation_link}`
            '''
        ),
        parse_mode="Markdown",
    )     

@exceptions_catcher
@autoSetState()
async def workersList(user_id: int, page: int=1) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT id, "workerName", "workID", "isActive"
            FROM "userWorkers"
            WHERE "userID" = $1
        '''
        workers = (await conn.fetch(query, user_id))
    finally:
        await conn.close()

    workers_count = len(workers)
    if workers_count > 0:
        active_workers_count = len([w for w in workers if w[3]]) # w[3] == "isActive" column

        work_workers_count = collections.Counter(w[2] for w in workers)
        workers_by_works_text = '\n'.join(
            f'*{getWorkTitle(k, add_emoji=True)}:* {v} сотрудников'
            for (k,v) in work_workers_count.items()
        )

        message_text = f'''
            *🗂 Список сотрудников*

            🧑🏼‍🔧 Всего *{workers_count}* сотрудников, из них *{active_workers_count}* активных.

            {workers_by_works_text}

            🟢 - сотрудник активен
            🔴 - сотрудник неактивен
        '''

        is_active_emoji = {
            True: '🟢',
            False: '🔴',
        }
        workers_data = tuple([
            {
                'text': f'{is_active_emoji[w[2]]} {w[1][:10]} ({getWorkTitle(w[2], add_emoji=True)})', 
                'callback_data': f'start_func-workerCard-worker_id={w[0]}-call_id=True'
            } 
            for w in workers
        ])
        keyboard = (await paginator(array=workers_data, current_page=page))
    else:
        message_text = f'''
            *🗂 Список сотрудников*

            У Вас нет ни одного сотрудника.
        '''
        keyboard = keyboard_obj()

    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))
    
    bot.send_message(
        chat_id=user_id,
        text=dedent(message_text),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )     

@exceptions_catcher
@autoSetState()
async def workerCard(user_id: int, worker_id: int, call_id: int) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT id, "workID", "workerName", "workerNumber", "addDate", "isActive"
            FROM "userWorkers"
            WHERE id = $1 AND "userID" = $2
        '''
        worker = (await conn.fetchrow(query, worker_id, user_id))
    finally:
        await conn.close()

    if worker is None:
        bot.answer_callback_query(
            call_id, 
            dedent(
            '''
            🔎 Сотрудник не найден!

            Меню из которого Вы пытались открыть его профиль устарело.
            '''), 
            show_alert=True
        )

    else:
        work_id = worker[1]
        name = worker[2]
        phone = worker[3]
        add_date = worker[4]
        is_active = worker[5]

        is_active_emoji = {
            True: '🟢',
            False: '🔴',
        }

        keyboard = keyboard_obj()
        keyboard.add(
            button_obj(
                text='🗑 Удалить сотрудника', 
                callback_data=f'start_func-removeUserWorker-worker_id={worker_id}'
            )
        )
        keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *{is_active_emoji[is_active]} {name}*

                ☎️ Номер телефона: {f'`{phone}`' if phone else '*не указан*'}
                🔧 Род деятельности: *{getWorkTitle(work_id, add_emoji=True)}*
                📅 Дата добавления: *{add_date}*
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )     
        
@exceptions_catcher
async def removeUserWorker(user_id: int, worker_id: int, confirmed: bool=False) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT id, "workID", "workerName"
            FROM "userWorkers"
            WHERE id = $1 AND "userID" = $2
        '''
        worker = (await conn.fetchrow(query, worker_id, user_id))
    finally:
        await conn.close()

    if worker is None:
        bot.answer_callback_query(
            call_id, 
            dedent(
            '''
            🔎 Сотрудник не найден!

            Меню из которого Вы пытались открыть его профиль устарело.
            '''), 
            show_alert=True
        )

    else:
        work_id = worker[1]
        name = worker[2]

        keyboard = keyboard_obj()

        if confirmed:
            conn = await connect()
            try:
                stmt = '''
                    DELETE FROM "userWorkers"
                    WHERE id = $1 AND "userID" = $2
                '''
                await conn.execute(stmt, worker_id, user_id)
            finally:
                await conn.close()

            keyboard.add(button_obj(text='🏠 Главное меню', callback_data='start_func-start'))

            bot.send_message(
                chat_id=user_id,
                text=dedent(
                    f'''
                    *✅ Сотрудник {name} удалён!*
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )     

        else:
            keyboard.row(
                button_obj(text='❌ Отмена', callback_data='start_func-back'),
                button_obj(
                    text='✅ Удалить', 
                    callback_data=f'start_func-removeUserWorker-worker_id={worker_id}&confirmed=True'
                )
            )

            bot.send_message(
                chat_id=user_id,
                text=dedent(
                    f'''
                    *🗑 Вы уверены, что хотите удалить своего сотрудника?*

                    🧑🏼‍🔧 Сотрудник: *({getWorkTitle(work_id, add_emoji=True)}) {name}*
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )     

# /. Workers


# Getter of any callback queries in the chat
@bot.callback_query_handler(lambda call: True)
def callback_handler(call):
    asyncio.run(statesRunner(call))

@exceptions_catcher
async def statesRunner(call: telebot.types.CallbackQuery):
    "Runs required states."

    user_id = call.from_user.id
    data = call.data.split('-') # 0 - command; 1 - kwargs; 2: - parameters

    if data[0] == 'start_func':
        # List which have all the functions from the __main__ module
        functions_list = [
            name for (name, obj) 
                in vars(sys.modules['__main__']).items() 
                if hasattr(obj, "__class__") 
                    and obj.__class__.__name__ == "function"
        ]

        func = data[1]
        if 'back' != func not in functions_list:
            raise NotFound

        elif func == 'back': 
            "Runs previous user state."

            current_state = (await getState(bot='main', user_id=user_id))
            if current_state:
                last_state = current_state['last_state']
                last_state['is_back'] = True
            else:
                last_state = None

            if last_state is None:
                await start(user_id=user_id)

            func = last_state['func']
            args = last_state['args']
            kwargs = [f'{k}={v}' for k,v in last_state['kwargs'].items()]

            if len(set(('user_id', 'message', 'call')) & set(last_state['kwargs'].keys())) == 0 \
                and len(args) == 0:
                    kwargs.insert(0, f'user_id={user_id}')

            # Setting the past state as the current one 
            await setState('main', user_id, last_state)

        else:
            "Runs required function with kwargs."

            if len(data) > 2 and data[2] != '':
                args = []
                kwargs = data[2].split('&')
                kwargs.insert(0, f'user_id={user_id}')
            else:
                args, kwargs = [], []
                kwargs.insert(0, f'user_id={user_id}')
            
            if len(data) > 3:
                parameters = data[3].split('&')
                if 'user_id=None' in parameters:
                    del kwargs[0] # Remove user_id from kwargs
                if 'call_id=True':
                    kwargs.append(f'call_id=call.id')


        # Deleting a bot message from a previous state
        bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
    
        func_arguments = [*args, *kwargs]
        func_arguments_string = ', '.join(func_arguments)
        await eval(f"{func}({func_arguments_string})")
            


if __name__ == '__main__':
    while True: 
        try:    
            bot.polling(none_stop=True)
        except Exception as e:
            asyncio.run(addLog(level='critical', text=traceback.format_exc(), send_telegram_message=True))
        asyncio.run(asyncio.sleep(1))