from .logs import addLog
from .tg_api.queries import telegram_api_request

import traceback
import functools
from textwrap import dedent


def exceptions_catcher(bot='main'): 
    '''Catches all the exceptions in functions.
    If exception is noticed, it adds a new note to a logfile 
    and sends a telegram message for user about unsuccessful request.
    
    :param func: a function in which exceptions must be catched.
    '''

    def container(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                user_id = args[0].from_user.id
            except (IndexError, AttributeError):
                user_id = None

            try:
                result = await func(*args, **kwargs)
            except Exception as e:
                await addLog(
                    level='error', 
                    text=traceback.format_exc(),
                    send_telegram_message=True,
                )

                if user_id:
                    await telegram_api_request(
                        request_method='POST',
                        api_method='sendMessage',
                        bot=bot,
                        parameters={
                            'chat_id': user_id,
                            'text': dedent(
                                f'''
                                *❌ Во время исполнения Вашего запроса произошла неизвестная ошибка.*

                                Уведомление о проблеме уже направлено ответственным лицам.
                                Попробуйте повторить свой запрос, если ничего не изменится - подождите некоторое время.

                                *🙏 Приносим свои извенения за предоставленные неудобства.*
                            '''),
                            'parse_mode': 'Markdown',
                        },
                    )
        return wrapper
    return container


class NotFound(Exception):
    '''Raised when an unknown function is being requested.'''
    pass

class AccessDenied(Exception):
    '''Raised when when a function that is not available to the user is requested.'''
    pass