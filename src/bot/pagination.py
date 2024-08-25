import math
import inspect
from telebot import types


async def paginator(
    array: tuple[dict], 
    per_page: int=5, 
    current_page: int=1,
    **kwargs
) -> types.InlineKeyboardMarkup:
    '''Creates a keyboard with objects from array and pagination buttons.
    
    :param array: tuple of objects for pagination.
    :param per_page: number of objects per page.
    :param current_page: current page number.
    '''

    keyboard = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton

    pages_count = math.ceil(len(array) / per_page)
    last_index = per_page * current_page
    first_index = last_index - per_page
    
    for i in array[first_index:last_index]:
        keyboard.add(button(text=i['text'], callback_data=i['callback_data']))

    # Get the name of the func calling paginator
    stack = inspect.stack()
    caller_func = stack[1].function 

    if kwargs:
        kwargs_parts = []
        for k, v in kwargs.items():
            if isinstance(v, int): form = f'{k}={v}'
            else: form = f'{k}="{v}"'
            kwargs_parts.append(form)
        kwargs = '&'.join(kwargs_parts)
    else:
        kwargs = ''


    manage_buttons = {
        'previous': button(text='⬅️', callback_data=f'start_func-{caller_func}-page={current_page-1}&{kwargs}'),
        'current': button(text=f'{current_page} / {pages_count}', callback_data='#'),
        'next': button(text='➡️', callback_data=f'start_func-{caller_func}-page={current_page+1}&{kwargs}'),
        'first': button(text='⏪', callback_data=f'start_func-{caller_func}-page=1&{kwargs}'),
        'last': button(text='⏩', callback_data=f'start_func-{caller_func}-page={pages_count}&{kwargs}'),
        'empty': button(text=' ', callback_data=f'#'),
    }
    if pages_count > 1:
        keyboard.row(
            manage_buttons['first'] if current_page != 1 else manage_buttons['empty'],
            manage_buttons['previous'] if current_page != 1 else manage_buttons['empty'],
            manage_buttons['current'],
            manage_buttons['next'] if current_page != pages_count else manage_buttons['empty'],
            manage_buttons['last'] if current_page != pages_count else manage_buttons['empty'],
        )

    return keyboard