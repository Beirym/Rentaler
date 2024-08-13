from ..config import MAIN_BOT_TOKEN
from ..exceptions import exceptions_catcher, NotFound
from ..logs import addLog
from .. import utils
from ..state_machine import *

import sys
import telebot
import asyncio
import traceback
from textwrap import dedent


# Connect to Telegram Bot API
bot = telebot.TeleBot(token=MAIN_BOT_TOKEN)

# Getter of any text messenges in the chat
@bot.message_handler(content_types='text')
def main(message):
    asyncio.run(start(message))


@exceptions_catcher
@autoSetState('main')
async def start(message: telebot.types.Message=None, user_id: int=None) -> None:
    '''Outputs the start menu.
    
    :param message: object of telebot message.
    '''

    if user_id is None:
        user_id = message.from_user.id

    greeting = await utils.greeting()
    name = await utils.getUsername(bot, user_id)

    keyboard = telebot.types.InlineKeyboardMarkup()
    button = telebot.types.InlineKeyboardButton
    keyboard.add(button(text='Инструменты', callback_data='start_func-tools'))
    keyboard.add(button(text='Мои объекты', callback_data='start_func-properties'))
    keyboard.add(button(text='Мои рабочие', callback_data='start_func-workers'))

    bot.send_message(
        chat_id=user_id,
        text=dedent(
            f'''*{greeting}, {name}!*'''
        ),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


# Getter of any callback queries in the chat
@bot.callback_query_handler(lambda call: True)
def callback_handler(call):
    asyncio.run(statesRunner(call))

@exceptions_catcher
async def statesRunner(call: telebot.types.CallbackQuery):
    '''Runs required states.'''
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

        if data[1] == 'back': 
            back_to_previous_state = True
        else: 
            back_to_previous_state = False

        if back_to_previous_state:
            '''Runs previous user state.'''

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

        else:
            func = data[1]

            if len(data) > 2:
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


        if func in functions_list:
            func_arguments = [*args, *kwargs]
            func_arguments_string = ', '.join(func_arguments)

            if back_to_previous_state:
                await setState('main', user_id, last_state)

            bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
            await eval(f"{func}({func_arguments_string})")
        else:
            raise NotFound


if __name__ == '__main__':
    while True: 
        try:    

            bot.polling(none_stop=True)
        except Exception as e:
            asyncio.run(addLog(level='critical', text=traceback.format_exc(), send_telegram_message=True))
        asyncio.run(asyncio.sleep(1))