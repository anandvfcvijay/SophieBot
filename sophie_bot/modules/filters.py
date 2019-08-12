import re

from aiogram import types
from aiogram.types.inline_keyboard import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from sophie_bot import WHITELISTED, decorator, mongodb, redis, dp, bot
from sophie_bot.modules.connections import connection
from sophie_bot.modules.disable import disablable_dec
from sophie_bot.modules.language import get_string, get_strings_dec
from sophie_bot.modules.notes import send_note
from sophie_bot.modules.bans import ban_user, kick_user, convert_time
from sophie_bot.modules.users import user_admin_dec, user_link, get_chat_admins, user_link_html
from sophie_bot.modules.warns import randomString


# State
class NewFilter(StatesGroup):
    handler = State()
    action = State()
    time = State()
    note_name = State()
    reason = State()


new_filter_cb = CallbackData('new_filter', 'action')
new_filter_time_cb = CallbackData('select_filter_time', 'time')


@decorator.AioBotDo()
async def check_message(message):
    chat_id = message.chat.id
    filters = redis.lrange('filters_cache_{}'.format(chat_id), 0, -1)
    if not filters:
        update_handlers_cache(chat_id)
        filters = redis.lrange('filters_cache_{}'.format(chat_id), 0, -1)
    if redis.llen('filters_cache_{}'.format(chat_id)) == 0:
        return
    text = message.text
    user_id = message.from_user.id
    msg_id = message.message_id
    for keyword in filters:
        keyword = keyword.decode("utf-8")
        keyword = re.escape(keyword)
        keyword = keyword.replace('\(\+\)', '.*')
        pattern = r"( |^|[^\w])" + keyword + r"( |$|[^\w])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            H = mongodb.filters.find_one({'chat_id': chat_id, "handler": {'$regex': str(pattern)}})
            if not H:
                update_handlers_cache(chat_id)
                return
            action = H['action']
            if action == 'note':
                await send_note(chat_id, chat_id, msg_id, H['arg'], show_none=True)
            elif action == 'answer':
                # TODO
                await message.answer(H['arg'])
            elif action == 'delete':
                await message.delete()
            elif action == 'ban':
                if await ban_user(message, user_id, chat_id, None, no_msg=True) is True:
                    text = get_string('filters', 'filter_ban_success', chat_id).format(
                        user=await user_link_html(user_id),
                        filter=H['handler']
                    )
                    await message.reply(text)
            elif action == 'tban':
                timee, unit = await convert_time(message, H['arg'])
                if await ban_user(message, user_id, chat_id, timee, no_msg=True) is True:
                    text = get_string('filters', 'filter_tban_success', chat_id).format(
                        user=await user_link_html(user_id),
                        time=H['arg'],
                        filter=H['handler']
                    )
                    await message.reply(text)
            elif action == 'kick':
                if await kick_user(message, user_id, chat_id, no_msg=True) is True:
                    text = get_string('filters', 'filter_kick_success', chat_id).format(
                        user=await user_link_html(user_id),
                        filter=H['handler']
                    )
                    await message.reply(text)
            elif action == 'warn':
                user_id = message.from_user.id
                await warn_user_filter(message, H, user_id, chat_id)
            break


@decorator.command("filter")
@user_admin_dec
@connection(admin=True)
@get_strings_dec("filters")
async def add_filter(message, strings, status, chat_id, chat_title):
    args = message.get_args().split(" ")
    if len(args) < 2:
        await message.reply(strings["wrong_action"])
        return

    handler = args[0]
    action = args[1]
    if len(args) > 2:
        arg = args[2]
    else:
        arg = None

    if args[0].startswith(("'", '"')):
        raw = args
        _handler = []
        for x in raw:
            if x.startswith(("'", '"')):
                _handler.append(x.replace('"', '').replace("'", ''))
            elif x.endswith(("'", '"')):
                _handler.append(x.replace('"', '').replace("'", ''))
                break
            else:
                _handler.append(x)

        handler = " ".join(_handler)
        action = raw[len(_handler)]
        _arg = len(_handler) + 1
        arg = raw[_arg:]

    text = strings["filter_added"]
    text += strings["filter_keyword"].format(handler)
    if action == 'delete':
        text += strings["a_del"]
    elif action == 'ban':
        text += strings["a_ban"]
    elif action == 'mute':
        text += strings["a_mute"]
    elif action == 'kick':
        text += strings["a_kick"]

    elif action == 'note':
        if not arg:
            await message.reply(strings["no_arg_note"])
            return
        arg = arg[0]
        text += strings["a_send_note"].format(arg)
    elif action == 'tban':
        if not arg:
            await message.reply(strings["no_arg_note"])
            return
        arg = arg[0]
        text += strings["a_tban"].format(arg)
    elif action == 'answer':
        if not arg:
            await message.reply(strings["no_arg_note"])
            return
        arg = " ".join(arg)
        text += strings["a_answer"]
    elif action == 'warn':
        if arg:
            text += "Reason: " + arg
        text += strings["a_warn"].format(arg)
    else:
        await message.reply(strings["wrong_action"])
        return

    mongodb.filters.update_one(
        {'chat_id': chat_id, 'handler': handler},
        {"$set": {'action': action, 'arg': arg}}, upsert=True
    )

    update_handlers_cache(chat_id)
    await message.reply(text)


@dp.callback_query_handler(regexp='cancel', state='*')
async def cancel_handler(query, state):
    await state.finish()
    await bot.delete_message(query.message.chat.id, query.message.message_id)


@decorator.command('addfilter')
@connection()
@get_strings_dec("filters")
async def new_filter(message, strings, status, chat_id, chat_title):
    print('oow')
    await NewFilter.handler.set()
    await message.reply("Please write keyword/key words.")


@dp.message_handler(state=NewFilter.handler)
@dp.callback_query_handler(regexp='add_filter_actions', state='*')
@dp.callback_query_handler(regexp='add_filter_actions_del_msg', state='*')
async def add_filter_handler(message, state: FSMContext, del_msg=False, edit=False):
    if 'message' in message:
        query = message
        message = message.message
        edit = message.message_id

    handler = message.text
    chat_id = message.chat.id
    async with state.proxy() as data:
        data['chat_id'] = chat_id
        if 'handler' in data:
            handler = data['handler']
        else:
            data['handler'] = handler

        if 'query' in locals() and query.data == 'add_filter_actions_del_msg':
            del_msg = True
            data['del_msg'] = True

    await NewFilter.action.set()
    text = f"Great! I will answer on \"<code>{handler}</code>\"."
    text += "\nNow please select a action for this filter:"

    buttons = InlineKeyboardMarkup(row_width=2)

    buttons.add(
        InlineKeyboardButton(
            "Send note",
            callback_data=new_filter_cb.new(action='note')),
        InlineKeyboardButton(
            "Answer on message",
            callback_data=new_filter_cb.new(action='answer')),
        InlineKeyboardButton(
            "Just delete message",
            callback_data=new_filter_cb.new(action='delmsg')),
        InlineKeyboardButton(
            "Warn user",
            callback_data=new_filter_cb.new(action='warn')),
        InlineKeyboardButton(
            "Ban user",
            callback_data=new_filter_cb.new(action='ban')),
        InlineKeyboardButton(
            "Mute user",
            callback_data=new_filter_cb.new(action='mute')),
        InlineKeyboardButton(
            "Kick user",
            callback_data=new_filter_cb.new(action='kick')),
    )

    if del_msg is False:
        buttons.add(
            InlineKeyboardButton("❌ Delete origin message: off",
                                 callback_data='add_filter_actions_del_msg')
        )
    else:
        buttons.add(
            InlineKeyboardButton("❌ Delete origin message: on",
                                 callback_data='add_filter_actions')
        )

    buttons.add(
        InlineKeyboardButton("❗️ Exit", callback_data='cancel')
    )

    if edit is False:
        await message.reply(text, reply_markup=buttons)
    else:
        await bot.edit_message_text(text, chat_id, edit, reply_markup=buttons)


@dp.callback_query_handler(new_filter_cb.filter(), state='*')
async def add_filter_action(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    action = callback_data['action']
    chat_id = query.message.chat.id
    msg_id = query.message.message_id

    async with state.proxy() as data:
        data['action'] = action

    actions_with_timer = ('ban', 'mute')
    actions_with_reason = ('warn')

    if action in actions_with_timer:
        await select_time(state, action, chat_id, msg_id)
    elif action in actions_with_reason:
        await NewFilter.reason.set()
        text = "Great! Please write reason with which we will do this action."
        await bot.edit_message_text(text, chat_id, msg_id)
    elif action == 'note':
        await NewFilter.note_name.set()
        text = "Great! Please write notename."
        await bot.edit_message_text(text, chat_id, msg_id)
    else:
        async with state.proxy() as data:
            await add_new_filter(**data)
            await filter_added(msg_id, edit=True, **data)
            await state.finish()


async def select_time(state, action, chat_id, msg_id):
    async with state.proxy() as data:
        data['time_sel_msg'] = msg_id

    await NewFilter.time.set()  # For manual select time

    text = f"Great! On which time you wanna {action} user?"
    text += "\nYou can also manually write time, for example write '2d'"
    text += "\nOr select time by buttons below:"
    buttons = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton(
            "Forever", callback_data=new_filter_time_cb.new(time=False)),
        InlineKeyboardButton(
            "2 hours", callback_data=new_filter_time_cb.new(time='2h')),
        InlineKeyboardButton(
            "5 hours", callback_data=new_filter_time_cb.new(time='5h')),
        InlineKeyboardButton(
            "24 hours", callback_data=new_filter_time_cb.new(time='24h')),
        InlineKeyboardButton(
            "2 days", callback_data=new_filter_time_cb.new(time='2d')),
        InlineKeyboardButton(
            "1 week", callback_data=new_filter_time_cb.new(time='7d'))
    )

    buttons.add(
        InlineKeyboardButton("◀️ Back", callback_data='add_filter_actions')
    )

    buttons.add(
        InlineKeyboardButton("❗️ Exit", callback_data='cancel')
    )

    await bot.edit_message_text(text, chat_id, msg_id, reply_markup=buttons)
    return


@dp.callback_query_handler(new_filter_time_cb.filter(), state='*')
async def add_filter_time(query: types.CallbackQuery, callback_data: dict, state: FSMContext):
    time = callback_data['time']
    async with state.proxy() as data:
        data['time'] = time
        await filter_added(query.message.message_id, edit=True, **data)
        await state.finish()


@dp.message_handler(state=NewFilter.time)
async def add_filter_time_manual(message, state: FSMContext):
    text = message.text
    if not any(text.endswith(unit) for unit in ('m', 'h', 'd')):
        text = "Time value isn't valid!"
        await bot.send_message(message.chat.id, text, reply_to_message_id=message.message_id)
        await state.finish()
        return
    async with state.proxy() as data:
        data['time'] = text
        await filter_added(message.message_id, **data)
        await state.finish()


@dp.message_handler(state=NewFilter.reason)
async def add_filter_reason(message, state: FSMContext):
    reason = message.text
    async with state.proxy() as data:
        data['reason'] = reason
        await add_new_filter(**data)
        await filter_added(message.message_id, **data)
        await state.finish()


@dp.message_handler(state=NewFilter.note_name)
async def add_filter_note(message, state: FSMContext):
    note_name = message.text
    async with state.proxy() as data:
        data['note_name'] = note_name
        await add_new_filter(**data)
        await filter_added(message.message_id, **data)
        await state.finish()


async def filter_added(msg_id, edit=False, **data):
    text = "<b>Filter added!</b>"
    text += f"\nHandler: <code>{data['handler']}</code>"
    text += f"\nAction: <code>{data['action']}</code>"
    if 'time' in data and not data['time'] == 'False':
        text += f"\nTime: on <code>{data['time']}</code>"
    if 'note_name' in data:
        text += f"\nNote: <code>{data['note_name']}</code>"
    if 'del_msg' in data and data['del_msg'] is True:
        text += "\nAlso delete origin message"
    if 'reason' in data:
        text += "\nReason:\n<code>"
        text += data['reason'] + "</code>"

    chat_id = data['chat_id']
    if edit is True:
        await bot.edit_message_text(text, chat_id, msg_id)
    else:
        await bot.send_message(chat_id, text, reply_to_message_id=msg_id)


async def add_new_filter(**kwargs):
    print(kwargs)
    return True


@decorator.command("filters")
@disablable_dec("filters")
@connection()
@get_strings_dec("filters")
async def list_filters(message, strings, status, chat_id, chat_title):
    filters = mongodb.filters.find({'chat_id': chat_id})
    text = strings["filters_in"].format(chat_name=chat_title)
    H = 0

    for filter in filters:
        H += 1
        if filter['arg']:
            text += "- {} ({} - <code>{}</code>)\n".format(
                filter['handler'], filter['action'], filter['arg'])
        else:
            text += "- {} ({})\n".format(filter['handler'], filter['action'])
    if H == 0:
        text = strings["no_filters_in"].format(chat_title)
    await message.reply(text)


@decorator.command("stop")
@user_admin_dec
@connection(admin=True)
@get_strings_dec("filters")
async def stop_filter(message, strings, status, chat_id, chat_title):
    handler = message.get_args()
    filter = mongodb.filters.find_one({'chat_id': chat_id,
                                      "handler": {'$regex': str(handler)}})
    if not filter:
        await message.reply(strings["cant_find_filter"])
        return
    mongodb.filters.delete_one({'_id': filter['_id']})
    update_handlers_cache(chat_id)
    text = strings["filter_deleted"]
    text = text.format(filter=filter['handler'], chat_name=chat_title)
    await message.reply(text)


def update_handlers_cache(chat_id):
    filters = mongodb.filters.find({'chat_id': chat_id})
    redis.delete('filters_cache_{}'.format(chat_id))
    for filter in filters:
        redis.lpush('filters_cache_{}'.format(chat_id), filter['handler'])


async def warn_user_filter(message, H, user_id, chat_id):
    if user_id in WHITELISTED:
        return

    if user_id in await get_chat_admins(chat_id):
        return

    warn_limit = mongodb.warnlimit.find_one({'chat_id': chat_id})
    db_warns = mongodb.warns.find({
        'user_id': user_id,
        'group_id': chat_id
    })

    #  to avoid adding useless another warn in db
    current_warns = 1

    for _ in db_warns:
        current_warns += 1

    if not warn_limit:
        warn_limit = 3
    else:
        warn_limit = int(warn_limit['num'])

    if current_warns >= warn_limit:
        if await ban_user(message, user_id, chat_id, None) is False:
            print(f'cannot ban user {user_id}')
            return

        await ban_user(message, user_id, chat_id, None, no_msg=False)
        mongodb.warns.delete_many({
            'user_id': user_id,
            'group_id': chat_id
        })

        resp = get_string("filters", "filter_warn_ban", chat_id).format(
            warns=warn_limit,
            user=await user_link(user_id),
            reason=H['arg']
        )

        await message.reply(resp)
        return
    else:
        rndm = randomString(15)

        mongodb.warns.insert_one({
            'warn_id': rndm,
            'user_id': user_id,
            'group_id': chat_id,
            'reason': H['arg']
        })

        buttons = InlineKeyboardMarkup().add(InlineKeyboardButton(
            "⚠️ Remove warn", callback_data='remove_warn_{}'.format(rndm)
        ))
        rules = mongodb.rules.find_one({"chat_id": chat_id})

        if rules:
            InlineKeyboardMarkup().add(InlineKeyboardButton(
                "📝 Rules", callback_data='get_note_{}_{}'.format(chat_id, rules['note'])
            ))

        chat_title = mongodb.chat_list.find_one({'chat_id': chat_id})['chat_title']

        txt = get_string("filters", "filter_warn_warned", chat_id).format(
            user=await user_link_html(user_id),
            chat=chat_title,
            current_warns=current_warns,
            max_warns=warn_limit,
            reason=H['arg']
        )
        await message.answer(txt, reply_markup=buttons)
        return
