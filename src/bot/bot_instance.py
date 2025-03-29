from aiogram import Bot
from config.config import config

# Инициализация бота с токеном из конфигурации
bot = Bot(token=config.token) 