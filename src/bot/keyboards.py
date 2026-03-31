from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_yes_no_keyboard() -> InlineKeyboardMarkup:
    """
    Инлайн-клавиатура с кнопками Да/Нет и Назад
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="division_yes"),
                InlineKeyboardButton(text="Нет", callback_data="division_no"),
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="back"),
            ],
        ]
    )
    return keyboard


def get_yandex_replace_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для конфликта имени файла на Яндекс.Диске.
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Заменить", callback_data="division_yes"),
                InlineKeyboardButton(text="Не сохранять", callback_data="division_no"),
            ],
            [
                InlineKeyboardButton(
                    text="Сохранить с другим названием",
                    callback_data="yandex_save_renamed",
                ),
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="back"),
            ],
        ]
    )
    return keyboard


def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    Инлайн-кнопка Назад под сообщением бота
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Назад", callback_data="back"),
            ],
        ]
    )
    return keyboard


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Основная постоянная клавиатура пользователя.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Скачать отчет из Anketolog")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
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
    # Добавляем кнопку Назад на отдельной строке
    builder.row(
        InlineKeyboardButton(
            text="Назад",
            callback_data="back"
        )
    )

    return builder.as_markup()