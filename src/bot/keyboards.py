from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

def build_keyboard(user_data, OPTIONS) -> InlineKeyboardMarkup:
    CHECK_CHAR = "✅"
    UNCHECK_CHAR = "⬜"
    builder = InlineKeyboardBuilder()
    # Добавляем кнопки с чекбоксами
    for i, opt in enumerate(OPTIONS):
        checked = CHECK_CHAR if user_data.get(opt) else UNCHECK_CHAR
        builder.button(
            text=f"{checked} {opt}",
            callback_data=f"toggle__{i}"
        )

    # Указываем: чекбоксы — по 2 в ряд
    builder.adjust(2)

    # Добавляем кнопку подтверждения на отдельной строке
    builder.row(
        InlineKeyboardButton(
            text="Подтвердить",
            callback_data="confirm"
        )
    )

    return builder.as_markup()