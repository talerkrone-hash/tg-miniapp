"""
=========================================================================
 bot.py — Telegram-бот для портфолио "Tim Taler — No-Code архитектор"
 ВЕРСИЯ ДЛЯ ПОСТОЯННОГО БЕСПЛАТНОГО ХОСТИНГА (Render.com, режим Webhook)
=========================================================================

ЧЕМ ЭТА ВЕРСИЯ ОТЛИЧАЕТСЯ ОТ ТОЙ, ЧТО РАБОТАЛА ЛОКАЛЬНО:

Раньше бот работал в режиме POLLING — раз в секунду сам спрашивал у
Telegram "есть новые сообщения?". Для этого нужен постоянно включённый
компьютер. Такой процесс называется "Background Worker" ("фоновый
рабочий"), и почти все бесплатные хостинги просят за него банковскую
карту — даже если по факту ничего не спишут, карта нужна just in case.

Эта версия работает в режиме WEBHOOK — вместо того чтобы бот сам
спрашивал новости, Telegram САМ стучится к боту по конкретному адресу,
когда появляется сообщение. Для этого бот превращается в маленький
веб-сайт (технически — "Web Service"), который слушает входящие запросы
на определённом порту. Именно этот тип бесплатно и БЕЗ КАРТЫ дают
такие хостинги, как Render.com.

Компромисс: бесплатный Web Service на Render "засыпает" после 15 минут
без сообщений и "просыпается" около минуты на первое сообщение после
паузы. Для бота-визитки это нормально — просто самый первый ответ после
долгого простоя придёт с небольшой задержкой.

БЕЗОПАСНОСТЬ: токен и ссылки здесь НЕ прописаны текстом в коде, а
читаются из переменных окружения через os.getenv(...). Сами значения
задаются отдельно — в закрытой панели Render (см. пошаговую инструкцию
в чате). Это специально: код этого файла может спокойно лежать в
репозитории на GitHub, не раскрывая никаких секретов.

Установка зависимостей (уже прописаны в requirements.txt):
    pip install -r requirements.txt
=========================================================================
"""

import json
import logging
import os

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ContentType, ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# =========================================================================
# 1. НАСТРОЙКИ — значения приходят из переменных окружения Render
# =========================================================================

# Токен бота от @BotFather. Задаётся в Render: Environment -> BOT_TOKEN.
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ссылка на index.html (GitHub Pages). Задаётся в Render: WEB_APP_URL.
WEB_APP_URL = os.getenv("WEB_APP_URL")

# Публичный адрес САМОГО БОТА на Render, например:
# https://tim-taler-bot.onrender.com — Render покажет его после первого
# деплоя. Задаётся в Render: BASE_WEBHOOK_URL.
BASE_WEBHOOK_URL = os.getenv("BASE_WEBHOOK_URL")

# Путь, по которому Telegram будет стучаться к нашему веб-сервису.
WEBHOOK_PATH = "/webhook"

# "Секретное слово" для проверки, что запрос пришёл именно от Telegram,
# а не от кого-то постороннего, кто угадал наш адрес. Можно оставить
# значение по умолчанию или задать своё через переменную WEBHOOK_SECRET.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "tim-taler-miniapp-secret")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# =========================================================================
# 2. Хэндлер команды /start (логика та же, что и раньше)
# =========================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🚀 Открыть портфолио",
                    web_app=WebAppInfo(url=WEB_APP_URL),
                )
            ]
        ],
        resize_keyboard=True,
    )

    await message.answer(
        "Привет! 👋\n\n"
        "Я <b>Tim Taler</b> — No-Code архитектор мобильных приложений "
        "и экосистем Telegram &amp; .gram.\n\n"
        "Нажми на кнопку «🚀 Открыть портфолио» в панели снизу, "
        "чтобы открыть моё портфолио и оставить заявку 👇",
        reply_markup=keyboard,
    )


# =========================================================================
# 3. Хэндлер данных из Mini App (логика та же, что и раньше)
# =========================================================================

@dp.message(F.content_type == ContentType.WEB_APP_DATA)
async def handle_web_app_data(message: Message) -> None:
    raw_data = message.web_app_data.data

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        await message.answer("Не удалось разобрать данные из формы 😕")
        return

    name = data.get("name", "не указано")
    phone = data.get("phone", "не указано")
    task = data.get("task", "не указано")

    await message.answer(
        "📩 <b>Новая заявка!</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📝 Задача: {task}"
    )


# =========================================================================
# 4. Настройка webhook при старте сервиса
# =========================================================================

async def on_startup(bot: Bot) -> None:
    # Говорим Telegram: "присылай обновления сюда"
    await bot.set_webhook(
        f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET,
    )


# =========================================================================
# 5. Запуск веб-сервера (вместо polling)
# =========================================================================

def main() -> None:
    dp.startup.register(on_startup)

    # Создаём веб-приложение (aiohttp) — именно оно будет "Web Service"
    # на Render, к которому будет стучаться Telegram.
    app = web.Application()

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Render сообщает, на каком порту слушать, через переменную PORT —
    # она подставляется автоматически, вписывать вручную не нужно.
    # host="0.0.0.0" (а не "127.0.0.1") обязателен на любом облачном
    # хостинге, иначе снаружи контейнера сервис будет недоступен.
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
