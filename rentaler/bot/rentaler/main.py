from ..config import RENTALER_BOT_TOKEN
from ..exceptions import exceptions_catcher
from ..logs import addLog

import telebot
import asyncio
import traceback


bot = telebot.TeleBot(token=RENTALER_BOT_TOKEN)

@bot.message_handler(content_types='text')
def main(message):
    asyncio.run(start(message))


@exceptions_catcher
async def start(message):
    ...


if __name__ == '__main__':
    while True: 
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            asyncio.run(addLog(level='error', text=traceback.format_exc(), send_telegram_message=True))