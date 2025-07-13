import asyncio
import logging
from aiogram import Dispatcher
from src.bot.bot_instance import bot
from src.bot.handlers import router


# Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     filename='logs/bot.log',
#     filemode='a'
# )

# # Вывод логов в консоль
# console = logging.StreamHandler()
# console.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# console.setFormatter(formatter)
# logging.getLogger('').addHandler(console)


async def main():
    """Главная функция запуска бота"""
    # Инициализация диспетчера
    dp = Dispatcher()
    
    # Подключение роутера с обработчиками
    dp.include_router(router)
    
    # Удаление вебхука и запуск бота
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    # try:
        # Запуск бота
        asyncio.run(main())
    # except (KeyboardInterrupt, SystemExit):
    #     # Корректное завершение работы
    #     # logging.info("Бот остановлен")
    # except Exception as e:
    #     # Логирование ошибок
    #     # logging.error(f"Непредвиденная ошибка: {e}", exc_info=True)