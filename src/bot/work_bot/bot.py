from ..config import MAIN_BOT_TOKEN, WORK_BOT_TOKEN
from ..exceptions import exceptions_catcher, NotFound
from ..logs import addLog
from .. import utils
from ..state_machine import *
from ..db import connect, asyncpg_errors
from ..works import getWorkTitle
from ..tg_api.queries import telegram_api_request
from ..pagination import paginator

import sys
import time
import uuid
import json
import telebot
import asyncio
import datetime
import traceback
from textwrap import dedent
import schedule
import threading


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

@exceptions_catcher('work')
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

@exceptions_catcher('work')
@autoSetState(bot='work')
async def start(message: telebot.types.Message=None, user_id: int=None) -> None:
    "Outputs the start menu."

    if user_id is None:
        user_id = message.from_user.id

    greeting = await utils.greeting()
    name = await utils.getUsername(bot, user_id)

    conn = await connect()
    try:
        query = '''
            SELECT COUNT(id)
            FROM "userWorks"
            WHERE 
                "workID" = 1
                AND "workerID" = $1
                AND "completedDate" IS NULL
                AND "acceptForWorkDate" IS NOT NULL
        '''
        accepted_cleaning = (await conn.fetchval(query, user_id))
    finally:
        await conn.close()

    keyboard = keyboard_obj()
    keyboard.add(button_obj('📅 Предстоящие уборки', callback_data='start_func-cleaningList-status="accepted"'))
    keyboard.add(button_obj('🔎 Свободные уборки', callback_data='start_func-cleaningList-status="scheduled"'))
    keyboard.add(button_obj('✅ Завершённые уборки', callback_data='start_func-cleaningList-status="completed"'))

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *{greeting}, {name}!*
            
            📅 У Вас *{accepted_cleaning}* предстоящих уборок.
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# === Tools ===

@exceptions_catcher('work')
@autoSetState('work')
async def cleaningList(user_id: int, status: str, page: int=1) -> None:
    conn = await connect()
    try:
        args = []
        match status:
            case 'accepted':
                query_where_confitions = '"workerID" = $1'
                args.append(user_id)
            case 'scheduled':
                query_where_confitions = '"acceptForWorkDate" IS NULL'
            case 'completed':
                query_where_confitions = '"completedDate" IS NOT NULL'

        query = f'''
            SELECT id, date, "timeRange"
            FROM "userWorks"
            WHERE {query_where_confitions}
        '''
        cleaning = (await conn.fetch(query, *args))
    finally:
        await conn.close()

    cleaning_count = len(cleaning)

    if cleaning_count > 0:
        cleaning_data = tuple([
            {
                # Cleaning text indexes: 1 - date, 2 - time_range, 3 - acceptanceConfirmed
                'text': f'{c[1]} ({c[2]})',
                'callback_data': f'start_func-cleaningCard-work_id={c[0]}-call_id=True'
            } 
            for c in cleaning
        ])
        keyboard = (await paginator(array=cleaning_data, current_page=page, status=status))
    else:
        keyboard = keyboard_obj()
    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

    match status:
        case 'accepted':
            list_title = '📅 Предстоящие уборки'
        case 'scheduled':
            list_title = '🔎 Свободные уборки'
        case 'completed':
            list_title = '✅ Завершённые уборки'

    bot.send_message(
        chat_id=user_id,
        text=f"{list_title}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )     

@exceptions_catcher('work')
@autoSetState('work')
async def cleaningCard(user_id: int, work_id: int, call_id: int=None) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT 
                w.id,
                w."propertyID", p."address",
                w."workerID",
                w.date, w."timeRange", 
                w."acceptForWorkDate", w."acceptanceConfirmed", w."completedDate",
                w.comment, 
                w."addDate", 
                c."hygieneKitsCount"
            FROM "userWorks" w
            JOIN cleaning c
                ON c."workID" = w.id
            JOIN properties p
                ON p.id = w."propertyID"
            WHERE w.id = $1
        '''
        cleaning_data = (await conn.fetchrow(query, work_id))
    finally:
        await conn.close()

    if cleaning_data:
        cleaning_data = dict(cleaning_data)
    else:
        return bot.answer_callback_query(
            callback_query_id=call_id, 
            text=dedent(
            '''
            🔎 Запись о клининге не найдена!

            Меню из которого Вы пытались открыть карточку клининга устарело.
            '''), 
            show_alert=True
        )


    keyboard = keyboard_obj()
    if cleaning_data['acceptForWorkDate'] is None:
        keyboard.add(
            button_obj(
                text='☑️ Принять в работу', 
                callback_data=f'start_func-acceptCleaning-work_id={work_id}-call_id=True'
            )
        )

    now = datetime.datetime.now().date()
    if cleaning_data['workerID'] == user_id:
        if cleaning_data['date'] == now and cleaning_data['completedDate'] is None:
            keyboard.add(
                button_obj(
                    text='✅ Завершить клининг', 
                    callback_data=f'start_func-completeCleaning-work_id={work_id}'
                )
            )
        if cleaning_data['acceptForWorkDate'] and cleaning_data['acceptanceConfirmed'] is False:
            keyboard.add(
                button_obj(
                    text='🚫 Отказаться от проведения', 
                    callback_data=f'start_func-refuseCleaning-work_id={work_id}-call_id=True'
                )
            )

    keyboard.add(button_obj(text='⬅️ Назад', callback_data='start_func-back'))

    address = cleaning_data['address']
    now_date = datetime.datetime.now().date()
    date = cleaning_data['date']
    if date == now_date: date = 'Сегодня'
    elif date == (now_date + datetime.timedelta(days=1)): date = 'Завтра'
    time_range = cleaning_data['timeRange']
    acceptanceConfirmed = cleaning_data['acceptanceConfirmed']
    hygiene_kits_count = cleaning_data['hygieneKitsCount']

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *🧴 Информация о клининге*

            🏠 Адрес: *{address}*
            📅 Дата и время: *{date} ({time_range})*
            🧺 Кол-во гигиенических наборов: *{hygiene_kits_count}*
            {'✅' if acceptanceConfirmed else '❌'} Клининг подтверждён: *{'да' if acceptanceConfirmed else 'нет'}*
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@exceptions_catcher('work')
async def acceptCleaning(user_id: int, work_id: int, call_id: int, confirmed: bool=False) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT 
                w.id, w."userID", w."propertyID", p."address",
                w.date, w."timeRange", w."acceptForWorkDate"
            FROM "userWorks" w
            JOIN cleaning c
                ON c."workID" = w.id
            JOIN properties p
                ON p.id = w."propertyID"
            WHERE w.id = $1
        '''
        cleaning_data = (await conn.fetchrow(query, work_id))
    finally:
        await conn.close()

    if cleaning_data:
        cleaning_data = dict(cleaning_data)
    else:
        return bot.answer_callback_query(
            callback_query_id=call_id, 
            text=dedent(
            '''
            🔎 Запись о клининге не найдена!

            Меню из которого Вы пытались принять его в работу устарело.
            '''), 
            show_alert=True
        )

    if cleaning_data['acceptForWorkDate'] is not None:
        return bot.answer_callback_query(
            callback_query_id=call_id, 
            text=dedent(
            '''
            ❌ Данная уборка уже закреплена за другим сотрудником!

            Меню из которого Вы пытались принять его в работу устарело.
            '''), 
            show_alert=True
        )

    if confirmed is False:
        keyboard = keyboard_obj()
        keyboard.row(
            button_obj(text='❌ Отмена', callback_data='start_func-back'),
            button_obj(
                text='✅ Принять', 
                callback_data=f'start_func-acceptCleaning-work_id={work_id}&confirmed=True-call_id=True'
            )
        )

        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *❔ Вы уверены, что хотите принять данную уборку на себя?*

                Отказаться от проведения клининга можно будет в его карточке, 
                не позднее чем за день до уборки.
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    else:
        conn = await connect()
        try:
            now = datetime.datetime.now
            stmt = '''
                UPDATE "userWorks"
                SET "workerID" = $1, "acceptForWorkDate" = $2
                WHERE id = $3
            '''
            await conn.execute(stmt, user_id, now(), work_id)

            query = '''
                SELECT "workerName", "workerNumber"
                FROM "userWorkers"
                WHERE "workerID" = $1
            '''
            worker_data = (await conn.fetchrow(query, user_id))
        finally:
            await conn.close()

        keyboard = keyboard_obj()
        keyboard.add(
            button_obj(
                text='🧴 Карточка клининга', 
                callback_data=f'start_func-cleaningCard-work_id={work_id}',
            )
        )

        # Message for worker
        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *✅ Клининг взят в работу!*

                🏠 Место проведения: *{cleaning_data['address']}*
                📅 Дата и время проведения: *{cleaning_data['date']} ({cleaning_data['timeRange']})*

                _За 2 дня до проведения вы получите напоминание,
                а накануне Вам будет необходимо подтвердить
                свою возможность проведения работ._
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    
        # Message for landlord
        worker_name = worker_data['workerName']
        worker_number = worker_data['workerNumber']
        if worker_number:
            worker_name_and_number = f'*{worker_name}* (`{worker_number}`)'
        else:
            worker_name_and_number = worker_name

        await telegram_api_request(
            request_method='POST',
            api_method='sendMessage',
            parameters={
                'chat_id': cleaning_data['userID'],
                'text': dedent(
                    f'''
                    *✅ Сотрудник взял клининг в работу!*

                    🏠 Место проведения: *{cleaning_data['address']}*
                    📅 Дата и время проведения: *{cleaning_data['date']} ({cleaning_data['timeRange']})*
                    🧑🏼‍🔧 Отвественный сотрудник: {worker_name_and_number}
                    '''),
                'parse_mode': 'Markdown',
                'reply_markup': json.dumps({
                    "inline_keyboard": [
                        [
                            {
                                'text': '🧴 Карточка клининга',
                                'callback_data': f'start_func-cleaningCard-work_id={work_id}-call_id=True',
                            },
                        ],
                        [
                            {
                                'text': '🧑🏼‍🔧 Карточка сотрудника',
                                'callback_data': f'start_func-workerCard-worker_id={user_id}-call_id=True',
                            },
                        ],
                    ],
                }),
            },
            bot='main'
        )

@exceptions_catcher('work')
async def refuseCleaning(user_id: int, work_id: int, call_id: int, confirmed: bool=False) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT 
                w.id, w."userID", w."propertyID", p."address",
                w.date, w."timeRange", w."acceptForWorkDate",
                w.comment
            FROM "userWorks" w
            JOIN cleaning c
                ON c."workID" = w.id
            JOIN properties p
                ON p.id = w."propertyID"
            WHERE w.id = $1 
                AND w."workerID" = $2
        '''
        cleaning_data = (await conn.fetchrow(query, work_id, user_id))
    finally:
        await conn.close()

    if cleaning_data:
        cleaning_data = dict(cleaning_data)
    else:
        return bot.answer_callback_query(
            callback_query_id=call_id, 
            text=dedent(
            '''
            🔎 Запись о клининге не найдена!

            Меню из которого Вы пытались принять его в работу устарело.
            '''), 
            show_alert=True
        )

    if confirmed is False:
        keyboard = keyboard_obj()
        keyboard.row(
            button_obj(text='❌ Отмена', callback_data='start_func-back'),
            button_obj(
                text='🚫 Отказаться', 
                callback_data=f'start_func-refuseCleaning-work_id={work_id}&confirmed=True-call_id=True'
            )
        )

        bot.send_message(
            chat_id=user_id,
            text=dedent(
                f'''
                *❔ Вы уверены, что хотите отказаться от проведения клининга?*

                Даная уборка снова станет доступной для принятия в работу среди остальных сотрудников.
                '''
            ),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    else:
        conn = await connect()
        try:
            now = datetime.datetime.now
            stmt = '''
                UPDATE "userWorks"
                SET "workerID" = NULL, "acceptForWorkDate" = NULL
                WHERE id = $1
            '''
            await conn.execute(stmt, work_id)

            query = '''
                SELECT "workerID"
                FROM "userWorkers"
                WHERE "userID" = $1
                    AND "workID" = $2
                    AND "workerID" != $3
            '''
            cleaners = [c[0] for c in (await conn.fetch(query, cleaning_data['userID'], 1, user_id))]
        finally:
            await conn.close()

        keyboard = keyboard_obj()
        keyboard.add(
            button_obj(
                text='🧴 Карточка клининга', 
                callback_data=f'start_func-cleaningCard-work_id={work_id}',
            )
        )

        # Message for worker
        bot.send_message(
            chat_id=user_id,
            text=f"*🚫 Вы отказались от проведения клининга!*",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    
        # Message for landlord
        await telegram_api_request(
            request_method='POST',
            api_method='sendMessage',
            parameters={
                'chat_id': cleaning_data['userID'],
                'text': dedent(
                    f'''
                    *🚫 Сотрудник отказался от проведения клининга!*

                    🏠 Место проведения: *{cleaning_data['address']}*
                    📅 Дата и время проведения: *{cleaning_data['date']} ({cleaning_data['timeRange']})*
                    '''),
                'parse_mode': 'Markdown',
                'reply_markup': json.dumps({
                    "inline_keyboard": [
                        [
                            {
                                'text': '🧴 Карточка клининга',
                                'callback_data': f'start_func-cleaningCard-work_id={work_id}-call_id=True',
                            },
                        ],
                        [
                            {
                                'text': '🧑🏼‍🔧 Карточка сотрудника',
                                'callback_data': f'start_func-workerCard-worker_id={user_id}-call_id=True',
                            },
                        ],
                    ],
                }),
            },
            bot='main'
        )

        keyboard = keyboard_obj()
        keyboard.add(
            button_obj(
                text='☑️ Приянть в работу', 
                callback_data=f'start_func-acceptCleaning-work_id={work_id}-call_id=True'
            )
        )

        property_address = cleaning_data['address']
        date = cleaning_data['date']
        time_range = cleaning_data['timeRange']
        comment = cleaning_data['comment']
        now = datetime.datetime.now
        if date == now().date(): cleaning_date = 'Сегодня'
        elif date == (now() + datetime.timedelta(days=1)).date(): cleaning_date = 'Завтра'
        else: cleaning_date = date

        for cleaner_id in cleaners:
            bot.send_message(
                chat_id=cleaner_id,
                text=dedent(
                    f'''
                    *⏰ Запланирован клининг!*

                    *{cleaning_date} ({time_range})* на адрес: *{property_address}*

                    {f'*💭 Комментарий:* {comment}' if comment else ''}
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

@exceptions_catcher('work')
async def completeCleaning(user_id: int, work_id: int) -> None:
    conn = await connect()
    try:
        now = datetime.datetime.now
        query = '''
            SELECT 
                w.id, w."userID", p."address"
            FROM "userWorks" w
            JOIN properties p
                ON p.id = w."propertyID"
            WHERE w.id = $1
        '''
        work_data = (await conn.fetchrow(query, work_id))

        stmt = '''
            UPDATE "userWorks"
            SET "completedDate" = $1
            WHERE "workerID" = $2 AND id = $3
        '''
        await conn.execute(stmt, now(), user_id, work_id)
    finally:
        await conn.close()

    keyboard = keyboard_obj()
    keyboard.add(
        button_obj(
            text='🧴 Карточка клининга', 
            callback_data=f'start_func-cleaningCard-work_id={work_id}-call_id=True'
        )
    )

    # Message for worker
    bot.send_message(
        chat_id=user_id,
        text=f"*✅ Клининг по адресу {work_data['address']} завершён!*",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    # Message for landlord
    await telegram_api_request(
        request_method='POST',
        api_method='sendMessage',
        parameters={
            'chat_id': work_data['userID'],
            'text': f"*✅ Клининг по адресу {work_data['address']} завершён!*",
            'parse_mode': 'Markdown',
            'reply_markup': json.dumps({
                "inline_keyboard": [
                    [
                        {
                            'text': '🧴 Карточка клининга',
                            'callback_data': f'start_func-cleaningCard-work_id={work_id}-call_id=True',
                        },
                    ],
                    [
                        {
                            'text': '🧑🏼‍🔧 Карточка сотрудника',
                            'callback_data': f'start_func-workerCard-worker_id={user_id}-call_id=True',
                        },
                    ],
                ],
            }),
        },
        bot='main'
    )

@exceptions_catcher('work')
async def confirmAcceptance(user_id: int, work_id: int) -> None:
    conn = await connect()
    try:
        query = '''
            SELECT 
                w.id, w."userID", p."address", w."timeRange"
            FROM "userWorks" w
            JOIN properties p
                ON p.id = w."propertyID"
            WHERE w.id = $1
        '''
        work_data = (await conn.fetchrow(query, work_id))

        stmt = '''
            UPDATE "userWorks"
            SET "acceptanceConfirmed" = TRUE
            WHERE "workerID" = $1 AND id = $2
        '''
        await conn.execute(stmt, user_id, work_id)
    finally:
        await conn.close()

    keyboard = keyboard_obj()
    keyboard.add(
        button_obj(
            text='🧴 Карточка клининга', 
            callback_data=f'start_func-cleaningCard-work_id={work_id}-call_id=True'
        )
    )

    # Message for worker
    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''
            *✅ Проведение клининга подтверждено!*

            Завтра *({work_data['timeRange']})* по адресу *{work_data['address']}*
            '''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )

    # Message for landlord
    await telegram_api_request(
        request_method='POST',
        api_method='sendMessage',
        parameters={
            'chat_id': work_data['userID'],
            'text': dedent(
                f'''
                *✅ Сотрудник подтвердил проведение работ!*
                
                Завтра *({work_data['timeRange']})* по адресу *{work_data['address']}*
                '''
            ),
            'parse_mode': 'Markdown',
            'reply_markup': json.dumps({
                "inline_keyboard": [
                    [
                        {
                            'text': '🧴 Карточка клининга',
                            'callback_data': f'start_func-cleaningCard-work_id={work_id}-call_id=True',
                        },
                    ],
                    [
                        {
                            'text': '🧑🏼‍🔧 Карточка сотрудника',
                            'callback_data': f'start_func-workerCard-worker_id={user_id}-call_id=True',
                        },
                    ],
                ],
            }),
        },
        bot='main'
    )

# /. === Tools ===


# === Work notifications ===

def sendWorkNotificationsStarter():
    asyncio.run(sendWorkNotifications())

@exceptions_catcher('work')
async def sendWorkNotifications() -> None:
    conn = await connect()
    try:
        query = '''
            SELECT 
                w.id, w."workID",
                w."propertyID", p."address",
                w."workerID", uw."workerName",
                w.date, w."timeRange", 
                w."acceptForWorkDate", w."acceptanceConfirmed",
                w.comment
            FROM "userWorks" w
            JOIN properties p
                ON p.id = w."propertyID"
            JOIN "userWorkers" uw
                ON uw."workerID" = w."workerID"
            WHERE w."workerID" IS NOT NULL
                AND w."completedDate" IS NULL
        '''
        works = (await conn.fetch(query))
    finally:
        await conn.close()

    now = datetime.datetime.now().date()

    for work in works:
        work_title = getWorkTitle(work_id=work['workID'])
        address = work['address']
        time_range = work['timeRange']

        if ((work['date'] - now).days == 1) and (work['acceptanceConfirmed'] is False):
            keyboard = keyboard_obj()
            keyboard.row(
                button_obj(text='✅ Подтвердить', callback_data=f'start_func-confirmAcceptance-work_id={work["id"]}'),
                button_obj(text='🚫 Отказаться', callback_data=f'start_func-refuseCleaning-work_id={work["id"]}-call_id=True'),
            )

            bot.send_message(
                chat_id=work['workerID'],
                text=dedent(
                    f'''
                    *☑️ Подтвредите проведение работ*

                    На Вас назначено проведение работ *({work_title})*
                    по адресу *{address}* - завтра *({time_range})*.

                    _Подтвердите возможность проведения работ или откажитесь от их выполнения, нажав на соответствующую кнопку._
                    '''
                ),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        elif ((work['date'] - now).days == 2):
            bot.send_message(
                chat_id=work['workerID'],
                text=dedent(
                    f'''
                    *🔔 Напоминание о предстоящих работах*

                    На Вас назначено проведение работ *({work_title})*
                    по адресу *{address}* - послезавтра *({time_range})*.
                    '''
                ),
                parse_mode="Markdown",
            )

def schedule_notifications():
    schedule.every().day.at("19:00").do(sendWorkNotificationsStarter)

    while True:
        schedule.run_pending()
        time.sleep(60)

# /. === Work notifications ===


# Getter of any callback queries in the chat
@bot.callback_query_handler(lambda call: True)
def callbackHandler(call: telebot.types.CallbackQuery):
    asyncio.run(statesRunner(call))

@exceptions_catcher('work')
async def statesRunner(call: telebot.types.CallbackQuery):
    "Runs required states."

    user_id = call.from_user.id
    data = call.data.split('-') # 0 - command; 1 - command args; 2 - kwargs; 3: - parameters
    command = data[0]

    if command == 'start_func':
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

            # Clear available next step handlers
            bot.clear_step_handler_by_chat_id(chat_id=user_id)

            current_state = (await getState(bot='work', user_id=user_id))
            if current_state:
                last_state = current_state['last_state']
                last_state['is_back'] = True
            else:
                last_state = None

            if last_state is None:
                await start(user_id=user_id)

            func = last_state['func']
            args = last_state['args']
            kwargs = [
                f'{k}={v}' if isinstance(v, int) else f'{k}="{v}"'
                for k,v in last_state['kwargs'].items()
            ]

            if len(set(('user_id', 'message', 'call')) & set(last_state['kwargs'].keys())) == 0 \
                and len(args) == 0:
                    kwargs.insert(0, f'user_id={user_id}')

            # Setting the past state as the current one 
            await setState('work', user_id, last_state)

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
        try:
            bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
        except telebot.apihelper.ApiTelegramException:
            pass
    
        func_arguments = [*args, *kwargs]
        func_arguments_string = ', '.join(func_arguments)
        await eval(f"{func}({func_arguments_string})")


if __name__ == '__main__':
    schedule_thread = threading.Thread(target=schedule_notifications, daemon=True).start()

    while True: 
        try:    
            bot.polling(none_stop=True)
        except Exception as e:
            asyncio.run(addLog(level='critical', text=traceback.format_exc(), send_telegram_message=True))
        asyncio.run(asyncio.sleep(1))