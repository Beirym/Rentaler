from .exceptions import exceptions_catcher

import telebot
import datetime


async def getUsername(bot: telebot.TeleBot, user_id: int, profile_link=False) -> str:
    '''Checks all the username options and reduces them to one.

    :param bot: object of telebot.TeleBot.
    :param user_id: telegram user id.
    :param profile_link: if `True`, the username becomes clickable with a link to the user's profile.
    '''

    user = bot.get_chat_member(chat_id=user_id, user_id=user_id).user
    first_name = user.first_name
    last_name = user.last_name
    telegram_username = user.username

    username_parts = []
    if first_name: username_parts.append(first_name)
    if first_name and last_name: username_parts.append(last_name)
    if len(username_parts) == 0 and telegram_username: username_parts.append(telegram_username)
    if len(username_parts) == 0: username_parts.append(user_id)

    username = ' '.join(username_parts)
    if profile_link:
        username = f'[{username}](tg://user?id={user_id})'

    return username


async def greeting():
    '''Creates a personalized greeting depending on the current server time.'''

    hour = datetime.datetime.now().hour
    morning = [*range(4, 11)]
    afternoon = [*range(11, 16)]
    evening = [*range(16, 22)]
    night = [*range(0, 4), *range(22, 24)]

    if hour in morning: greeting = '☕ Доброе утро'
    elif hour in afternoon: greeting = '☀️ Добрый день'
    elif hour in evening: greeting = '🛋 Добрый вечер'
    elif hour in night: greeting = '🌙 Доброй ночи'
    else: greeting = '👋 Здравствуйте'

    return greeting
