import asyncio
import logging
import os
import sys
from random import shuffle
import movie_handler

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

# Bot token can be obtained via https://t.me/BotFather
TOKEN = os.getenv('BOT_TOKEN')

dp = Dispatcher()
mh = movie_handler.MovieHandler()
EMOJI_POOL = ['\U0001F608', '\U0001F60E', '\U0001F60B', '\U0001F643', '\U0001F607']


def emoji_pool() -> list[str]:
    shuffle(EMOJI_POOL)
    return EMOJI_POOL


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    await message.answer(f"Привет, {message.from_user.full_name}! \n\n"
                         f"Я бот, который поможет тебе найти фильмы по запросу.\n"
                         f"Настоятельная просьба не искать запрещённый в рф контент,"
                         f" так как не гарантируется, что в ответ вы получите хоть что-то.\n"
                         f"Напиши /help для вывода списка доступных команд.")


@dp.message(Command(commands=['help']))
async def command_help_handler(message: Message) -> None:
    """
    Handler for the `/help` command.
    """
    help_text = (
        "Доступные команды:\n\n"
        "/start - Начать работу с ботом.\n"
        "/help - Показать это сообщение.\n\n"
        "Чтобы найти фильм, просто напишите его название в чат. Бот предложит подходящие варианты!"
    )
    await message.answer(help_text)


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    try:
        text = message.text
        lst, meta = await mh.get_links_by_query(text)
        if len(lst) == 0:
            await message.answer(f"Без фильмов на сегодня \n {html.bold('Ничего не найдено')}")
        else:
            await message.answer(str(meta) + "\n\nВозможно вы искали что-то из этого \n"
                                 + '\n'.join([f'{i + 1}. {html.link(meta.title or str(text), film)} {emoji}'
                                              for i, (film, emoji) in enumerate(zip(lst, emoji_pool()))]))
    except TypeError:
        await message.answer("Убил..")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
