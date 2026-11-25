from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from config.config import config

# Инициализация бота с токеном из конфигурации
session = AiohttpSession(proxy=config.proxy_url) if config.proxy_url else None
bot = Bot(token=config.token, session=session) if session else Bot(token=config.token)
