from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def get_yes_no_keyboard() -> ReplyKeyboardMarkup:
    """
    Создание клавиатуры с кнопками Да/Нет
    
    Returns:
        Клавиатура с кнопками Да/Нет
    """
    kb = [
        [
            KeyboardButton(text="Да"),
            KeyboardButton(text="Нет"),
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выбери вариант",
    )
    return keyboard


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Создание клавиатуры для административной панели
    
    Returns:
        Клавиатура для административной панели
    """
    kb = [
        [
            KeyboardButton(text="Удалить"),
            KeyboardButton(text="Добавить"),
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
    return keyboard 