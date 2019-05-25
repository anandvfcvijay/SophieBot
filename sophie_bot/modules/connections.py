import re
from functools import wraps

from sophie_bot import bot, mongodb, redis
from sophie_bot.events import command
from sophie_bot.modules.language import get_string
from sophie_bot.modules.users import is_user_admin

from telethon import errors, events
from telethon.tl.custom import Button


@command("connect", arg=True)
async def connect_with_arg(event):
    user_id = event.from_id
    if not event.chat_id == user_id:
        chat = event.chat_id
        chat = mongodb.chat_list.find_one({'chat_id': int(chat)})
    else:
        if not event.pattern_match.group(1):
            return
        else:
            chat = event.message.raw_text.split(" ", 2)[1]
            if not chat[0] == '-':
                chat = mongodb.chat_list.find_one({
                    'chat_nick': chat.replace("@", "")
                })
                if not chat:
                    await event.reply(get_string("connections", "cant_find_chat_use_id", chat))
                    return
            else:
                chat = mongodb.chat_list.find_one({'chat_id': int(chat)})
                if not chat:
                    await event.reply(get_string("connections", "cant_find_chat", chat))
                    return

    chat_id = chat['chat_id']
    chat_title = chat['chat_title']

    user_chats = mongodb.user_list.find_one({'user_id': user_id})
    if user_chats and 'chats' in user_chats:
        if chat_id not in user_chats['chats']:
            await event.reply(get_string("connections", "not_in_group", chat))
            return

    history = mongodb.connections.find_one({'user_id': user_id})
    if not history:
        mongodb.connections.insert_one({
            'user_id': user_id,
            'chat_id': chat_id,
            'btn1': chat_id,
            'btn2': None,
            'btn3': None,
            'btn4': None,
            'btn5': None,
            'updated': 3
        })
    else:
        btn1 = history['btn1']
        btn2 = history['btn2']
        btn3 = history['btn3']
        updated = history['updated']

        if history['updated'] == 1 and chat_id != history['btn2'] and chat_id != history['btn3']:
            btn1 = chat_id
            updated = 2
        elif history['updated'] == 2 and chat_id != history['btn1'] and chat_id != history['btn3']:
            btn2 = chat_id
            updated = 3
        elif history['updated'] >= 3 and chat_id != history['btn2'] and chat_id != history['btn1']:
            btn3 = chat_id
            updated = 1

        mongodb.connections.delete_one({'_id': history['_id']})

        mongodb.connections.insert_one({
            'user_id': user_id,
            'chat_id': chat_id,
            'btn1': btn1,
            'btn2': btn2,
            'btn3': btn3,
            'updated': updated
        })

    redis.set('connection_cache_{}'.format(user_id), chat_id)

    text = get_string("connections", "connected", chat).format(chat_title)
    if event.chat_id == user_id:
        await event.reply(text)
    else:
        try:
            await bot.send_message(user_id, text)
        except errors.rpcerrorlist.UserIsBlockedError:
            await event.reply(get_string("connections", "connected_pm_to_me", chat).format(
                chat_title))
            return
        await event.reply(get_string("connections", "pm_connected", chat).format(chat_title))


@command("connect")
async def connect(event):
    user_id = event.from_id
    if not event.chat_id == user_id:
        return
    history = mongodb.connections.find_one({'user_id': user_id})
    if not history:
        await event.reply(get_string("connections", "history_empty", event.chat_id))
        return
    buttons = []
    chat_title = mongodb.chat_list.find_one({'chat_id': history['btn1']})
    buttons += [[Button.inline("{}".format(chat_title['chat_title']),
                'connect_{}'.format(history['btn1']))]]
    if history['btn2']:
        chat_title = mongodb.chat_list.find_one({'chat_id': history['btn2']})
        buttons += [[Button.inline("{}".format(chat_title['chat_title']),
                    'connect_{}'.format(history['btn2']))]]
    if history['btn3']:
        chat_title = mongodb.chat_list.find_one({'chat_id': history['btn3']})
        buttons += [[Button.inline("{}".format(chat_title['chat_title']),
                    'connect_{}'.format(history['btn3']))]]
    chat_title = mongodb.chat_list.find_one({'chat_id': int(history['chat_id'])})
    text = get_string("connections", "connected_chat", event.chat_id)
    text += chat_title['chat_title']
    text += get_string("connections", "select_chat_to_connect", event.chat_id)
    await event.reply(text, buttons=buttons)


@command("disconnect", arg=True)
async def disconnect(event):
    user_id = event.from_id
    old = mongodb.connections.find_one({'user_id': user_id})
    if not old:
        await event.reply(get_string("connections", "u_wasnt_connected", event.chat_id))
        return
    chat_title = await get_conn_chat(user_id, event.chat_id)
    mongodb.connections.delete_one({'_id': old['_id']})
    redis.delete('connection_cache_{}'.format(user_id))
    await event.reply(get_string("connections", "disconnected", event.chat_id).format(chat_title))


@bot.on(events.CallbackQuery(data=re.compile(b'connect_')))
async def event(event):
    user_id = event.original_update.user_id
    chat_id = re.search(r'connect_(.*)', str(event.data)).group(1)[:-1]
    chat_title = mongodb.chat_list.find_one({'chat_id': int(chat_id)})
    old = mongodb.connections.find_one({'user_id': user_id})
    mongodb.connections.delete_one({'_id': old['_id']})
    mongodb.connections.insert_one({
        'user_id': user_id,
        'chat_id': chat_id,
        'btn1': old['btn1'],
        'btn2': old['btn2'],
        'btn3': old['btn3'],
        'updated': old['updated']
    })
    redis.set('connection_cache_{}'.format(user_id), chat_id)
    await event.edit(get_string("connections", "connected", event.chat_id).format(
        chat_title['chat_title']))


async def get_conn_chat(user_id, chat_id, admin=False, only_in_groups=False):
    if not user_id == chat_id:
        chat_title = mongodb.chat_list.find_one({
            'chat_id': int(chat_id)})['chat_title']
        return True, chat_id, chat_title
    user_chats = mongodb.user_list.find_one({'user_id': user_id})['chats']
    if chat_id not in user_chats:
        return False,
        get_string("connections", "not_in_chat", chat_id),
        None

    group_id = mongodb.connections.find_one({'user_id': int(user_id)})
    if not group_id:
        if only_in_groups is True:
            return False, get_string("connections", "usage_only_in_groups", chat_id), None
        return True, user_id, "Local"
    group_id = group_id['chat_id']

    chat_title = mongodb.chat_list.find_one({
        'chat_id': int(group_id)})['chat_title']

    if admin is True:
        K = await is_user_admin(group_id, user_id)
        if K is False:
            return False, get_string(
                "connections", "u_should_be_admin", event.chat_id).format(chat_title), None

    return True, int(group_id), chat_title


def connection(**kwargs):
    def wrapped(func):
        async def wrapped_1(event, **kwargs):
            status, chat_id, chat_title = await get_conn_chat(
                event.from_id, event.chat_id, **kwargs)
            if status is False:
                await event.reply(chat_id)
                return
            return await func(event, status, chat_id, chat_title)
        return wrapped_1
    return wrapped
