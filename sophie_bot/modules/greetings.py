import re
import time

from telethon.tl.custom import Button
from telethon.tl.types import MessageActionChatJoinedByLink

from aiogram import types

from sophie_bot import tbot, decorator, mongodb
from sophie_bot.modules.bans import mute_user, unmute_user
from sophie_bot.modules.connections import connection, get_conn_chat
from sophie_bot.modules.helper_func.flood import flood_limit
from sophie_bot.modules.language import get_string, get_strings_dec
from sophie_bot.modules.notes import send_note
from sophie_bot.modules.users import user_admin_dec, user_link


async def do_welcomesecurity(event, strings, from_id, chat_id):
    welcome_security = mongodb.welcome_security.find_one({'chat_id': chat_id})
    if welcome_security and welcome_security['security'] == 'soft':
        buttons = [
            [Button.inline(strings['clik2tlk_btn'], 'wlcm_{}_{}'.format(from_id, chat_id))]
        ]
        time_val = int(time.time() + 60 * 60)  # Mute 1 hour
        try:
            await mute_user(event, int(from_id), chat_id, time_val)
        except Exception as err:
            await event.reply(err)

        text = strings['wlcm_sec'].format(mention=await user_link(from_id))
        await event.reply(text, buttons=buttons)

    elif welcome_security and welcome_security['security'] == 'hard':
        buttons = [
            [Button.inline(strings['clik2tlk_btn'], 'wlcm_{}_{}'.format(from_id, chat_id))]
        ]
        try:
            await mute_user(event, int(from_id), chat_id, None)
        except Exception as err:
            await event.reply(err)

        text = strings['wlcm_sec'].format(mention=await user_link(from_id))
        await event.reply(text, buttons=buttons)


async def do_cleanwelcome(event, chat_id, welc_msg):
    clean_welcome = mongodb.clean_welcome.find_one({'chat_id': chat_id})
    if clean_welcome:
        new = {
            'chat_id': chat_id,
            'enabled': True,
            'last_msg': welc_msg.id
        }
        if 'last_msg' in clean_welcome:
            owo = []
            owo.append(clean_welcome['last_msg'])
            await event.client.delete_messages(chat_id, owo)

        mongodb.clean_welcome.update_one({'_id': clean_welcome['_id']}, {'$set': new})


@decorator.ChatAction()
@get_strings_dec("greetings")
async def welcome_trigger(event, strings):
    if event.user_joined \
            or event.user_added \
            or isinstance(event.action_message.action, MessageActionChatJoinedByLink):
        chat = event.chat_id
        chat = mongodb.chat_list.find_one({'chat_id': int(chat)})

        chat_id = event.action_message.chat_id

        if hasattr(event.action_message.action, 'users'):
            from_id = event.action_message.action.users[0]
        else:
            from_id = event.action_message.from_id

        # Don't welcome blacklisted users
        blacklisted = mongodb.blacklisted_users.find_one({'user': from_id})
        if blacklisted:
            return

        # Don't welcome fbanned users
        chat_fed = mongodb.fed_groups.find_one({'chat_id': chat_id})
        if chat_fed:
            fed_id = chat_fed['fed_id']
            is_banned = mongodb.fbanned_users.find_one({'user': from_id, 'fed_id': fed_id})
            if is_banned:
                return

        # Do not welcome yourselve
        bot_id = await tbot.get_me()
        if bot_id.id == from_id:
            return

        reply = event.action_message.id

        # Cleanservice
        cleaner = mongodb.clean_service.find_one({'chat_id': chat_id})
        if cleaner and cleaner['service']:
            await event.delete()
            reply = None

        welcome = mongodb.welcomes.find_one({'chat_id': chat_id})
        if not welcome:
            welc_msg = await event.reply(strings['welcome_hay'].format(
                mention=await user_link(from_id)
            ))
        elif welcome['enabled'] is False:
            welc_msg = None
        else:
            welc_msg = await send_note(
                chat_id, chat_id, reply, welcome['note'],
                show_none=True, from_id=from_id
            )

        # Welcomesecurity
        await do_welcomesecurity(event, strings, from_id, chat_id)

        # Cleanwelcome
        if welc_msg:
            await do_cleanwelcome(event, chat_id, welc_msg)


@decorator.command("setwelcome")
@user_admin_dec
@connection(only_in_groups=True, admin=True)
@get_strings_dec("greetings")
async def setwelcome(message, strings, status, chat_id, chat_title, *args):
    chat = mongodb.chat_list.find_one({'chat_id': int(chat_id)})
    arg = message['text'].split(" ", 2)
    if len(arg) <= 1:
        return
    if status is False:
        await message.reply(chat_id)

    note_name = arg[1]
    off = ['off', 'none', 'disable']
    if note_name in off:
        check = mongodb.welcomes.delete_one({'chat_id': chat})
        if check:
            text = "Welcome disabled for this chat"
        else:
            text = "Welcome didn't setuped yet"
        await message.reply(text)
        return
    note = mongodb.notes.find_one({
        'chat_id': chat_id,
        'name': note_name
    })
    if not note:
        await message.reply(strings["cant_find_note"])
        return
    old = mongodb.welcomes.find_one({'chat_id': chat_id})
    if old:
        mongodb.welcomes.delete_one({'_id': old['_id']})
    mongodb.welcomes.insert_one({
        'chat_id': chat_id,
        'enabled': True,
        'note': note_name
    })
    await message.reply(strings["welcome_set_to_note"].format(note_name),
                        parse_mode=types.ParseMode.HTML)


@decorator.t_command("setwelcome")
async def setwelcome_withot_args(event):
    chat = event.chat_id
    chat = mongodb.chat_list.find_one({'chat_id': int(chat)})
    if await flood_limit(event, 'setwelcome') is False:
        return
    status, chat_id, chat_title = await get_conn_chat(
        event.from_id, event.chat_id, only_in_groups=True)
    if status is False:
        await event.reply(chat_id)
        return
    old = mongodb.welcomes.find_one({'chat_id': chat_id})
    if old:
        note_name = old['note']
        await event.reply(get_string("greetings", "welcome_is_note", chat).format(note_name))
    else:
        await event.reply(get_string("greetings", "welcome_is_default", chat))


@decorator.t_command('cleanservice', arg=True)
@user_admin_dec
async def cleanservice(event):
    args = event.pattern_match.group(1)
    chat_id = event.chat_id
    enable = ['yes', 'on', 'enable']
    disable = ['no', 'disable']
    bool = args.lower()
    old = mongodb.clean_service.find_one({'chat_id': chat_id})
    if bool:
        if bool in enable:
            new = {'chat_id': chat_id, 'service': True}
            if old:
                mongodb.clean_service.update_one({'_id': old['_id']}, {"$set": new}, upsert=False)
            else:
                mongodb.clean_service.insert_one(new)
            await event.reply(get_string("greetings", "serv_yes", chat_id))
        elif bool in disable:
            mongodb.clean_service.delete_one({'_id': old['_id']})
            await event.reply(get_string("greetings", "serv_no", chat_id))
        else:
            await event.reply(get_string("greetings", "no_args_serv", chat_id))
            return
    else:
        await event.reply(get_string("greetings", "no_args_serv", chat_id))
        return


@decorator.t_command('welcomesecurity', arg=True)
@user_admin_dec
@get_strings_dec("greetings")
async def welcomeSecurity(event, strings):
    arg = event.pattern_match.group(1)
    args = arg.lower()
    hard = ['hard', 'high']
    soft = ['soft', 'low']
    off = ['off', 'no']
    chat = event.chat_id
    old = mongodb.welcome_security.find_one({'chat_id': chat})
    if not args:
        await event.reply(strings['noArgs'])
        return
    if args in hard:
        if old:
            mongodb.welcome_security.update_one({'_id': old['_id']}, {'$set': {'security': 'hard'}})
        else:
            mongodb.welcome_security.insert_one({'chat_id': chat, 'security': 'hard'})
        await event.reply(strings['wlcm_sec_hard'])
    elif args in soft:
        if old:
            mongodb.welcome_security.update_one({'$set': {'security': 'soft'}})
        else:
            mongodb.welcome_security.insert_one({'chat_id': chat, 'security': 'soft'})
        await event.reply(strings['wlcm_sec_soft'])
    elif args in off:
        mongodb.welcome_security.delete_one({'chat_id': chat})
        await event.reply(strings['wlcm_sec_off'])


@decorator.t_command('cleanwelcome', arg=True)
@user_admin_dec
@connection(admin=True, only_in_groups=True)
@get_strings_dec("greetings")
async def clean_welcome(event, strings, status, chat_id, chat_title):
    arg = event.pattern_match.group(1)
    args = arg.lower()
    on = ['on', 'yes', 'enable']
    off = ['off', 'no', 'disable']
    old = mongodb.clean_welcome.find_one({'chat_id': chat_id})
    if not args:
        if old:
            await event.reply(strings["cln_wel_enabled"].format(chat_name=chat_title))
        else:
            await event.reply(strings["cln_wel_disabled"].format(chat_name=chat_title))
    if args in on:
        if old:
            await event.reply(strings["cln_wel_alr_enabled"].format(chat_name=chat_title))
            return
        else:
            mongodb.clean_welcome.insert_one({"chat_id": chat_id, "enabled": True})
        await event.reply(strings['cln_wel_s_enabled'].format(chat_name=chat_title))
    elif args in off:
        check = mongodb.clean_welcome.delete_one({'chat_id': chat_id})
        if check.deleted_count < 1:
            await event.reply(strings['cln_wel_alr_disabled'].format(chat_name=chat_title))
            return
        await event.reply(strings['cln_wel_s_disabled'].format(chat_name=chat_title))


@decorator.CallBackQuery('wlcm_')
@get_strings_dec("greetings")
async def welcm_btn_callback(event, strings):
    data = str(event.data)
    details = re.search(r'wlcm_(.*)_(.*)', data)
    target_user = details.group(1)
    target_group = details.group(2)[:-1]
    user = event.query.user_id
    chat = event.chat_id
    if int(target_group) == int(chat) is False:
        return
    if int(user) != int(target_user):
        await event.answer(strings['not_trgt'])
        return
    await unmute_user(event, user, chat)
    await event.answer(strings['trgt_success'])
    await event.delete()
