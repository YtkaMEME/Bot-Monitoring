# Бот для обработки данных анкетирования

Телеграм-бот для обработки и анализа данных из анкет в формате Excel.

## Возможности

- Загрузка Excel файлов с данными анкет
- Автоматический анализ различных типов вопросов:
  - Шкала
  - Одиночный выбор
  - Множественный выбор
  - Матрица
  - Матрица 3D
  - Свободные ответы
- Поддержка NPS и CSI вопросов
- Сохранение результатов в Excel и CSV
- Административные функции для управления списками пользователей и мусорных слов

## Установка

1. Клонировать репозиторий:
   ```
   git clone <ссылка на репозиторий>
   ```

2. Установить зависимости:
   ```
   pip install -r requirements.txt
   ```

3. Настроить конфигурацию:
   - Установить токен бота в переменную окружения `BOT_TOKEN` или в файле `TOKEN.py`
   - Настроить списки пользователей в файлах `config/allowed_users.json` и `config/admins.json`
   - Настроить список мусорных слов в файле `config/list_to_del.json`

4. Создать необходимые директории:
   ```
   mkdir -p downloads logs
   ```

## Запуск

```
python main.py
```

## Использование

1. Отправить боту Excel файл с данными анкеты
2. Указать количество участников опроса
3. Ответить на вопросы о наличии специальных вопросов (настроение, NPS, CSI)
4. Получить обработанные данные в форматах Excel и CSV

## Команды

- `/start` - Начать работу с ботом
- `/cancel` - Отменить текущую операцию
- `/get_my_id` - Получить свой Telegram ID
- `/change_del_list` - Управление списком мусорных слов (требуются права)
- `/admin` - Административная панель (требуются права администратора)

## Структура проекта

```
Bot-Monitoring/
├── config/                # Конфигурация 
│   ├── allowed_users.json # Список разрешенных пользователей
│   ├── admins.json        # Список администраторов
│   ├── list_to_del.json   # Список мусорных слов
│   └── config.py          # Класс конфигурации
├── src/                   # Исходный код
│   ├── bot/               # Код бота
│   │   ├── bot_instance.py # Инициализация бота
│   │   ├── handlers.py    # Обработчики сообщений
│   │   ├── keyboards.py   # Клавиатуры
│   │   └── states.py      # Состояния FSM
│   ├── data_processing/   # Обработка данных
│   │   ├── analyzer.py    # Анализ данных
│   │   ├── file_processor.py # Обработка файлов
│   │   ├── models.py      # Модели данных
│   │   └── processor.py   # Основной процессор
│   └── utils/             # Утилиты
├── logs/                  # Логи
├── downloads/             # Временные файлы
├── TOKEN.py               # Токен бота
├── requirements.txt       # Зависимости
├── README.md              # Документация
└── main.py                # Точка входа
```

## Требования

- Python 3.8+
- aiogram 3.7.0+
- pandas 2.2.2+
- openpyxl 3.1.4+ 