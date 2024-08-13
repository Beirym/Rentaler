from .storage import getRedisConnection

import json
import functools


async def setState(bot: str, user_id: int, state_data: dict) -> None:
    redis = await getRedisConnection()
    state = json.dumps(state_data)
    redis.set(f"bot={bot}&user={user_id}-state", state)

async def getState(bot: str, user_id: int) -> dict | None:
    redis = await getRedisConnection()
    state_data = redis.get(f"bot={bot}&user={user_id}-state")
    if state_data:
        return json.loads(state_data)

async def delStates(bot: str, user_id: int) -> None:
    redis = await getRedisConnection()
    redis.delete(f"bot={bot}&user={user_id}-state")


def autoSetState(bot: str):
    '''Sets the function and the values of its arguments as the current state.'''

    def container(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                user_id = args[0].from_user.id
            except (IndexError, AttributeError):
                if 'user_id' in kwargs.keys():
                    user_id = kwargs['user_id']
                else: 
                    user_id = None

            if user_id:
                if func.__name__ == 'start':
                    await delStates(bot, user_id)
                    last_state_data = None
                else:
                    last_state_data = (await getState(bot, user_id))

                if (last_state_data is None) or (last_state_data['is_back'] is False):
                    state_data = {
                        'func': func.__name__,
                        'args': args[1:],
                        'kwargs': kwargs,
                        'is_back': False,
                        'last_state': last_state_data,
                    }
                    await setState(bot, user_id, state_data)

            result = await func(*args, **kwargs)
            return result
        return wrapper
    return container