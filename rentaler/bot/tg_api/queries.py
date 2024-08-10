from ..config import *

import requests
import asyncio

async def telegram_api_request(request_method: str, api_method: str, parameters:dict={}, bot: str='logs') -> str:
    match bot:
        case 'main': BOT_TOKEN = RENTALER_BOT_TOKEN
        case 'work': BOT_TOKEN = RENTALER_WORK_BOT_TOKEN
        case 'logs': BOT_TOKEN = RENTALER_LOGS_BOT_TOKEN
        case _: return ValueError('Unavailable telegram bot token')

    request = f"https://api.telegram.org/bot{BOT_TOKEN}/{api_method}?{'&'.join([f'{k}={v}' for k, v in parameters.items()])}"

    if request_method == 'GET':
        r = requests.get(request)
    elif request_method == 'POST':
        r = requests.post(request)

    response = {
        'code': r.status_code,
        'text': r.text,
    }
    
    return response