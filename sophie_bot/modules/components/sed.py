import re
from collections import defaultdict, deque

from telethon import events

from sophie_bot import bot, decorator
from sophie_bot.modules.helper_func.flood import flood_limit_dec

SED_PATTERN = r'^s/((?:\\/|[^/])+)/((?:\\/|[^/])*)(/.*)?'

last_msgs = defaultdict(lambda: deque(maxlen=10))


async def doit(event, message, match):
    fr = match.group(1)
    to = match.group(2)
    to = (to
          .replace('\\/', '/')
          .replace('\\0', '\\g<0>'))
    try:
        fl = match.group(3)
        if fl is None:
            fl = ''
        fl = fl[1:]
    except IndexError:
        fl = ''

    # Build Python regex flags
    count = 1
    flags = 0
    for f in fl.lower():
        if f == 'i':
            flags |= re.IGNORECASE
        elif f == 'm':
            flags |= re.MULTILINE
        elif f == 's':
            flags |= re.DOTALL
        elif f == 'g':
            count = 0
        elif f == 'x':
            flags |= re.VERBOSE
        else:
            await message.reply('unknown flag: {}'.format(f))
            return

    def substitute(m):
        if not m.raw_text:
            return None

        s, i = re.subn(fr, to, m.raw_text, count=count, flags=flags)
        if i > 0:
            return s

    try:
        substitution = None
        if message.is_reply:
            substitution = substitute(await message.get_reply_message())
        else:
            for msg in reversed(last_msgs[message.chat_id]):
                substitution = substitute(msg)
                if substitution is not None:
                    break

        if substitution is not None:
            if not message.is_reply:
                await message.reply(substitution)
            else:
                msg = await event.get_reply_message()
                await bot.send_message(event.chat_id, substitution, reply_to=msg.id)

    except Exception as e:
        await message.reply('fuck me\n' + str(e))


@decorator.StrictCommand(SED_PATTERN)
@flood_limit_dec("sed")
async def sed(event):
    message = await doit(event, event.message, event.pattern_match)
    if message:
        last_msgs[event.chat_id].append(message)

    # Don't save sed commands or we would be able to sed those
    raise events.StopPropagation


@bot.on(events.NewMessage)
async def catch_all(event):
    last_msgs[event.chat_id].append(event.message)


@bot.on(events.MessageEdited)
async def catch_edit(event):
    for i, message in enumerate(last_msgs[event.chat_id]):
        if message.id == event.id:
            last_msgs[event.chat_id][i] = event.message
