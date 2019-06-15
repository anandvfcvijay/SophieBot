import random

from requests import post

from telethon.errors import BadRequestError, ChatNotModifiedError
from telethon.tl.custom import Button
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.types import ChatAdminRights

import sophie_bot.modules.helper_func.bot_rights as bot_rights
from sophie_bot import OWNER_ID, SUDO, BOT_USERNAME, bot, decorator, mongodb
from sophie_bot.modules.disable import disablable_dec
from sophie_bot.modules.helper_func.flood import flood_limit_dec
from sophie_bot.modules.language import get_string, get_strings_dec
from sophie_bot.modules.users import get_user, user_admin_dec, user_link

RUN_STRINGS = (  # Thanks PaulSonOfLars
    "Where do you think you're going?",
    "Huh? what? did they get away?",
    "ZZzzZZzz... Huh? what? oh, just them again, nevermind.",
    "Get back here!",
    "Not so fast...",
    "Look out for the wall!",
    "Don't leave me alone with them!!",
    "You run, you die.",
    "Jokes on you, I'm everywhere",
    "You're gonna regret that...",
    "You could also try /kickme, I hear that's fun.",
    "Go bother someone else, no-one here cares.",
    "You can run, but you can't hide.",
    "Is that all you've got?",
    "I'm behind you...",
    "You've got company!",
    "We can do this the easy way, or the hard way.",
    "You just don't get it, do you?",
    "Yeah, you better run!",
    "Please, remind me how much I care?",
    "I'd run faster if I were you.",
    "That's definitely the droid we're looking for.",
    "May the odds be ever in your favour.",
    "Famous last words.",
    "And they disappeared forever, never to be seen again.",
    "\"Oh, look at me! I'm so cool, I can run from a bot!\" - this person",
    "Yeah yeah, just tap /kickme already.",
    "Here, take this ring and head to Mordor while you're at it.",
    "Legend has it, they're still running...",
    "Unlike Harry Potter, your parents can't protect you from me.",
    "Fear leads to anger. Anger leads to hate. Hate leads to suffering."
    "If you keep running in fear, you might "
    "be the next Vader.",
    "Multiple calculations later, I have decided my interest in your shenanigans is exactly 0.",
    "Legend has it, they're still running.",
    "Keep it up, not sure we want you here anyway.",
    "You're a wiza- Oh. Wait. You're not Harry, keep moving.",
    "NO RUNNING IN THE HALLWAYS!",
    "Hasta la vista, baby.",
    "Who let the dogs out?",
    "It's funny, because no one cares.",
    "Ah, what a waste. I liked that one.",
    "Frankly, my dear, I don't give a damn.",
    "My milkshake brings all the boys to yard... So run faster!",
    "You can't HANDLE the truth!",
    "A long time ago, in a galaxy far far away... "
    "Someone would've cared about that. Not anymore though.",
    "Hey, look at them! They're running from the inevitable banhammer... Cute.",
    "Han shot first. So will I.",
    "What are you running after, a white rabbit?",
    "As The Doctor would say... RUN!",
)


@decorator.command("id", arg=True)
@disablable_dec("id")
@flood_limit_dec("id")
async def id(event):
    text = get_string("misc", "your_id", event.chat_id).format(event.from_id)
    text += get_string("misc", "chat_id", event.chat_id).format(event.chat_id)

    if event.message.reply_to_msg_id:
        msg = await event.get_reply_message()
        userl = await user_link(msg.from_id)
        text += get_string("misc", "user_id", event.chat_id).format(userl, msg.from_id)

    elif len(event.message.raw_text) == 3:
        await event.reply(text)
        return

    else:
        user = await get_user(event)
        userl = await user_link(user['user_id'])
        text += get_string("misc", "user_id", event.chat_id).format(userl, user['user_id'])

    await event.reply(text)


@decorator.command("pin", arg=True)
@user_admin_dec
@bot_rights.pin_messages()
@get_strings_dec('misc')
async def pinMessage(event, strings):
    tagged_message = await event.get_reply_message()
    if not tagged_message:
        await event.reply(get_string('misc', 'no_reply_msg', event.chat_id))
        return
    msg_2_pin = tagged_message.id
    chk = event.pattern_match.group(1)
    args = chk.lower()
    tru_txt = ['loud', 'notify']
    chat = event.chat_id
    if args in tru_txt:
        notify = True
    else:
        notify = False
    try:
        await bot.pin_message(chat, msg_2_pin, notify=notify)
    except ChatNotModifiedError:
        await event.reply(strings['chat_not_modified_pin'])
        return
    await event.reply(get_string('misc', 'pinned_success', event.chat_id))


@decorator.command("runs")
async def runs(event):
    await event.reply(random.choice(RUN_STRINGS))


@decorator.command("unpin")
@user_admin_dec
@bot_rights.pin_messages()
@get_strings_dec('misc')
async def unpin_message(event, strings):
    try:
        await bot.pin_message(event.chat_id, None)
    except ChatNotModifiedError:
        await event.reply(strings['chat_not_modified_unpin'])
        return
    await event.reply(get_string('misc', 'unpin_success', event.chat_id))


@decorator.command("promote", arg=True)
@user_admin_dec
@bot_rights.add_admins()
async def promote(event):

    user = await get_user(event)
    if user:
        pass
    else:
        return

    new_rights = ChatAdminRights(
        add_admins=True,
        invite_users=True,
        change_info=True,
        ban_users=True,
        delete_messages=True,
        pin_messages=True
    )

    try:
        await event.client(
            EditAdminRequest(
                event.chat_id,
                user['user_id'],
                new_rights
            )
        )
        await event.reply(get_string('misc', 'promote_success', event.chat_id))

    except BadRequestError:  # TODO(Better exception)
        await event.reply(get_string('misc', 'promote_failed', event.chat_id))
        return


@decorator.command("demote")
@user_admin_dec
@bot_rights.add_admins()
async def demote(event):
    # Admin right check

    user = await get_user(event)
    if user:
        pass
    else:
        return

    bot_id = bot.get_me().id
    if bot_id == user['user_id']:
        return

    # New rights after demotion
    newrights = ChatAdminRights(
        add_admins=None,
        invite_users=None,
        change_info=None,
        ban_users=None,
        delete_messages=None,
        pin_messages=None
    )
    # Edit Admin Permission
    try:
        await event.client(
            EditAdminRequest(
                event.chat_id,
                user['user_id'],
                newrights
            )
        )

    # If we catch BadRequestError from Telethon
    # Assume we don't have permission to demote
    except BadRequestError:
        await event.reply(get_string('misc', 'demote_failed', event.chat_id))
        return
    await event.reply(get_string('misc', 'demote_success', event.chat_id))


@decorator.command('help')
@get_strings_dec('misc')
async def help(event, strings):
    if event.chat_id != event.from_id:
        buttons = [
            [Button.url(strings['help_btn'], url='https://t.me/{}?start=help'.format(BOT_USERNAME))]
        ]
        text = strings['help_txt']
        await event.reply(text, buttons=buttons)


@decorator.command('setrules', arg=True)
@user_admin_dec
@get_strings_dec('misc')
async def setrules(event, strings):
    reply_msg = await event.get_reply_message()
    if reply_msg:
        rule = str(reply_msg.message)
    else:
        rule = str(event.text[10:])

    chat = event.chat_id

    if rule == " ":
        await event.reply(strings['rule_empty'])
        return

    old_rules = mongodb.rules.find_one({'chat': chat})
    if old_rules:
        mongodb.rules.update_one({'_id': old_rules['_id']}, {'$set': {'rule': rule}})
        await event.reply(strings['rule_updated'])
    else:
        mongodb.rules.insert_one({'chat': chat, 'rule': rule})
        await event.reply(strings['rules_inserted'])


@decorator.command('rules')
@get_strings_dec('misc')
async def rules(event, strings):
    rule = mongodb.rules.find_one({'chat': event.chat_id})
    if rule:
        buttons = [
            [Button.url(strings['rules_btn'], url='https://t.me/{}?start=rules{}'.format(
                        BOT_USERNAME, event.chat_id))]
        ]
        text = strings['rules_text']
        await event.reply(text, buttons=buttons)
    else:
        await event.reply(strings['no_rules'])  # thank paul for dis string :/


@decorator.command('clearrules')
@user_admin_dec
@get_strings_dec('misc')
async def clear_rules(event, strings):
    chat = event.chat_id
    mongodb.rules.delete_one({'chat': chat})
    await event.reply(strings['clrd_rules'])


@decorator.command('paste', arg=True)
@get_strings_dec('misc')
async def paste_deldog(event, strings):
    DOGBIN_URL = "https://del.dog/"
    dogbin_final_url = None
    to_paste = None
    reply_msg = await event.get_reply_message()

    if reply_msg:
        to_paste = str(reply_msg.message)
    else:
        to_paste = event.text[6:]

    if not to_paste:
        await event.reply(strings['paste_no_text'])
        return

    resp = post(DOGBIN_URL + "documents", data=to_paste.encode('utf-8'))

    if resp.status_code == 200:
        response = resp.json()
        key = response['key']
        dogbin_final_url = DOGBIN_URL + key

        if response['isUrl']:
            full_url = "{}v/{}".format(DOGBIN_URL, key)
            reply_text = (strings["paste_success_extra"].format(dogbin_final_url, full_url))
        else:
            reply_text = (strings["paste_success"].format(dogbin_final_url))
    else:
        reply_text = (strings["paste_fail"])

    await event.reply(reply_text, link_preview=False)


@decorator.command("info", arg=True)
@flood_limit_dec("info")
@get_strings_dec("misc")
async def user_info(event, strings):
    user = await get_user(event)

    check = mongodb.blacklisted_users.find_one({'user': user['user_id']})
    if check:
        gban_stat = strings['gbanned_yes']
        gban_stat += strings["gbanned_date"].format(data=check['date'])
        gban_stat += strings["gbanned_reason"].format(reason=check['reason'])
    else:
        gban_stat = strings['gbanned_no']

    text = strings["user_info"]
    text += strings["info_id"].format(id=user['user_id'])
    text += strings["info_first"].format(first_name=str(user['first_name']))

    if user['last_name'] is not None:
        text += strings["info_last"].format(last_name=str(user['last_name']))

    if user['username'] is not None:
        text += strings["info_username"].format(username="@" + str(user['username']))

    text += strings['info_link'].format(user_link=str(await user_link(user['user_id'])))

    if user['user_id'] == OWNER_ID:
        text += strings["father"]
    elif user['user_id'] in SUDO:
        text += strings['sudo_crown']
    else:
        text += strings["gbanned"] + gban_stat

    await event.reply(text)
