from aiogram import Bot
from config.config import config
from aiogram.client.session.aiohttp import AiohttpSession
from PROXY import PROXY
# Инициализация бота с токеном из конфигурации
session = AiohttpSession(proxy=PROXY)
bot = Bot(token=config.token, session=session)