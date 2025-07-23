import os
import re
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup, FSInputFile, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from .states import MainState, AdminState
from .keyboards import build_keyboard, get_yes_no_keyboard
from .bot_instance import bot
from src.data_processing.processor import process_data
from config.config import config
from aiogram.types import CallbackQuery


router = Router()
OPTIONS = ["Настроение", "TR", "ROTI", "NPS", "CSI"]

def get_true_keys_iterator(state: dict[str, bool]):
    true_keys = [key for key, value in state.items() if value]
    if not true_keys:
        yield False
    else:
        for key in true_keys:
            yield key
        while True:
            yield False

async def start_process_data(state: FSMContext, message: Message) -> tuple[str, str]:
    """
    Запуск процесса обработки данных
    
    Args:
        state: FSM контекст
        message: Сообщение пользователя
        
    Returns:
        Кортеж с путями к сгенерированным файлам
    """
    user_data = await state.get_data()

    path = user_data["file_path"]
    doc = user_data["document"]
    mood = user_data.get("mood_number")
    nps = user_data.get("nps_number")
    csi = user_data.get("csi_number")
    tr = user_data.get("tr")
    roti = user_data.get("roti")
    analyze_type = user_data["analyze_type"]
    question_numbers_weights = None
    if analyze_type == "weighted":
        age = user_data["age"]
        gender = user_data["gender"]
        art_school = user_data["art_school"]
        question_numbers_weights = [gender, age, art_school]
    division = user_data.get("division")

    # Загружаем файл
    await bot.download(file=doc, destination=path)

    # Очищаем состояние
    await state.clear()

    # Обрабатываем данные
    excel_path, csv_path = await process_data(path, mood, nps, csi,
                                              message,
                                              analyze_type,
                                              question_numbers_weights, division, tr, roti)

    # Удаляем исходный файл
    if os.path.exists(path):
        os.remove(path)

    return excel_path, csv_path


async def is_question_repeated(state: FSMContext, number: int) -> bool:
    """
    Проверка повторения номера вопроса
    
    Args:
        state: FSM контекст
        number: Номер вопроса
        
    Returns:
        True если вопрос повторяется
    """
    user_data = await state.get_data()

    if "mood_number" in user_data and int(user_data["mood_number"]) == number:
        return True

    if "nps_number" in user_data and int(user_data["nps_number"]) == number:
        return True

    if "csi_number" in user_data and int(user_data["csi_number"]) == number:
        return True

    return False


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer("Мяувет! \U0001F638")
    await message.answer("Если хочешь начать работу - отправь мне файл выгрузку с анкетолога в формате .xlsx")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel"""
    await state.clear()
    await message.answer("Отмена прошла успешно, вы можете заново отправить файл", reply_markup=ReplyKeyboardRemove())


@router.message(F.document)
async def get_doc(message: Message, state: FSMContext):
    """Обработчик получения документа"""
    await state.clear()
    document = message.document
    doc_name = document.file_name

    if ".xlsx" not in doc_name:
        await message.answer("Проверьте отправленный файл, он должен соответствовать формату .xlsx")
        return

    file_path = f'{config.download_dir}/{doc_name}'
    
    # Создаем директорию, если не существует
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    await state.update_data(file_path=file_path, document=document)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Стандартный", callback_data="standard"),
            InlineKeyboardButton(text="Взвешивание", callback_data="weighted")  # исправляем здесь
        ]
    ])

    await state.set_state(MainState.type_analyze)
    await message.answer("Выберите тип обработки", reply_markup=keyboard)

@router.callback_query(MainState.type_analyze, F.data.in_(["standard", "weighted"]))
async def process_analyze_type(callback_query: CallbackQuery, state: FSMContext):
    analyze_type = callback_query.data

    await callback_query.answer()  # убирает крутилку у кнопки

    # Удаляем сообщение с инлайн-клавиатурой
    await callback_query.message.delete()

    if analyze_type == "standard":
        await state.update_data(analyze_type="standard")
        await state.set_state(MainState.division)
        await callback_query.message.answer("Хотите ли вы разделять выгрузку по какому либо вопросу?", reply_markup=get_yes_no_keyboard())
    else:
        await state.update_data(analyze_type="weighted")
        await state.set_state(MainState.gender)
        await callback_query.message.answer("Введите номер вопроса определяющего Пол участника",
                                            reply_markup=ReplyKeyboardRemove())


# --- Обработка нажатий по чекбоксам ---
@router.callback_query(F.data.startswith("toggle__"))
async def callback_toggle(query: types.CallbackQuery, state: FSMContext):
    index = int(query.data.replace("toggle__", ""))
    option = OPTIONS[index]

    # переключаем значение
    user_data = await state.get_data()
    user_data = user_data["checkbox_state"]
    user_data[option] = not user_data.get(option, False)
    

    # обновляем сообщение
    await state.update_data(checkbox_state=user_data)
    markup = build_keyboard(user_data, OPTIONS)
    await query.message.edit_reply_markup(reply_markup=markup)
    await query.answer()

# --- Подтверждение выбора ---
@router.callback_query(F.data == "confirm")
async def callback_confirm(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    user_data = user_data["checkbox_state"]
    current_data_iterator = get_true_keys_iterator(user_data)
    current_data = next(current_data_iterator)

    if not current_data:
        await callback_query.message.answer("Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())

        excel_path, csv_path = await start_process_data(state, callback_query.message)
        chat_id = callback_query.message.chat.id
        await bot.send_document(chat_id=chat_id, document=FSInputFile(excel_path))
        await bot.send_document(chat_id=chat_id, document=FSInputFile(csv_path))
        await callback_query.message.delete()

        # Удаляем временные файлы
        if os.path.exists(excel_path):
            os.remove(excel_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)
        return
    
    await state.update_data(iterator=current_data_iterator)
    await state.set_state(MainState.checkbox_menu_numbers)        
    await state.update_data(current_data = current_data)
    await callback_query.message.answer(f"Введите номер вопроса {current_data}!", reply_markup=ReplyKeyboardRemove())
    await callback_query.message.delete()


@router.message(MainState.division, F.text == "Да")
async def yes_quest(message: Message, state: FSMContext):
    """Обработчик ответа 'Да' на вопросы о наличии специальных вопросов"""
    current_state = await state.get_state()
    await message.answer("Введите номер/номера вопроса/вопросов!", reply_markup=ReplyKeyboardRemove())
    
    if current_state == MainState.division:
        await state.set_state(MainState.division_number)

@router.message(MainState.division, F.text == "Нет")
async def no_quest(message: Message, state: FSMContext):

    await state.update_data(checkbox_state={opt: False for opt in OPTIONS})
    user_data = await state.get_data()
    user_data = user_data["checkbox_state"]
    markup = build_keyboard(user_data, OPTIONS)

    await message.answer("Выбери параметры, которые присутствуют в выгрузке:", reply_markup=markup)
    return

@router.message(MainState.gender)
@router.message(MainState.age)
@router.message(MainState.art_school)
@router.message(MainState.division_number)
@router.message(MainState.checkbox_menu_numbers)
async def handle_number(message: Message, state: FSMContext):
    """Обработчик ввода числовых значений"""

    current_state = await state.get_state()
    division_number = [1]

    if not message.text.isdigit():
        if current_state == MainState.division_number:
            text_message = message.text.strip()
            division_number = [int(num) for num in re.findall(r'\d+', text_message)]
            if not isinstance(division_number[0], int):
                await message.answer("Вы ввели не цифру, повторите ввод!")
        else:
            await message.answer("Вы ввели не цифру, повторите ввод!")
            return
    
    number = 1    

    if not current_state == MainState.division_number:
        number = int(message.text)
        if number == 0 or 0 in division_number:
            await message.answer('Вы ввели "0", а это неправильно, так что повторите ввод')
            return
        # Проверка на повторение номера вопроса
        if await is_question_repeated(state, number):
            await message.answer("Введенные вами вопросы не могут совпадать!\nПовторите ввод номера вопроса")
            return
    else:
        len_division = len(division_number)
        if len_division == 1:
            number = int(message.text)
            division_number = [number]

    keyboard = get_yes_no_keyboard()

    if current_state == MainState.gender:
        await state.update_data(gender=number)
        await state.set_state(MainState.age)
        await message.answer("Введите номер вопроса определяющего Возраст участника",
                             reply_markup=ReplyKeyboardRemove())
        return
    
    elif current_state == MainState.age:
        await state.update_data(age=number)
        await state.set_state(MainState.art_school)
        await message.answer("Введите номер вопроса определяющего Арт школу участника",
                             reply_markup=ReplyKeyboardRemove())
        return

    elif current_state == MainState.art_school:
        await state.update_data(art_school=number)
        await state.set_state(MainState.division)
        await message.answer("Хотите ли вы разделять выгрузку по какому либо вопросу?", reply_markup=keyboard)
        return

    elif current_state == MainState.division_number:
        await state.update_data(division=division_number)
        await state.set_state(MainState.checkbox_menu)

        await state.update_data(checkbox_state={opt: False for opt in OPTIONS})
        user_data = await state.get_data()
        user_data = user_data["checkbox_state"]
        markup = build_keyboard(user_data, OPTIONS)

        await message.answer("Выбери параметры, которые присутствуют в выгрузке:", reply_markup=markup)
        return
    
    data_state = await state.get_data()
    old_current_data = data_state["current_data"]
    current_data_iterator = data_state["iterator"]
    current_data = next(current_data_iterator)
    await state.update_data(current_data=current_data)

    if old_current_data == "Настроение":
        await state.update_data(mood_number=number)
    elif old_current_data == "CSI":
        await state.update_data(csi_number=[number, number + 1])
        await message.answer("Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())

        excel_path, csv_path = await start_process_data(state, message)
        chat_id = message.from_user.id
        await bot.send_document(chat_id=chat_id, document=FSInputFile(excel_path))
        await bot.send_document(chat_id=chat_id, document=FSInputFile(csv_path))
            
        # Удаляем временные файлы
        if os.path.exists(excel_path):
            os.remove(excel_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)
    elif old_current_data == "NPS":
        await state.update_data(nps_number=number)
    elif old_current_data == "TR":
        await state.update_data(tr=number)
    elif old_current_data == "ROTI":
        await state.update_data(roti=number)
    elif not current_data:
        await message.answer("Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())

        excel_path, csv_path = await start_process_data(state, message)
        chat_id = message.from_user.id
        await bot.send_document(chat_id=chat_id, document=FSInputFile(excel_path))
        await bot.send_document(chat_id=chat_id, document=FSInputFile(csv_path))
            
        # Удаляем временные файлы
        if os.path.exists(excel_path):
            os.remove(excel_path)
        if os.path.exists(csv_path):
            os.remove(csv_path)
        
        await state.clear()
        return
    
    if current_data:
        await message.answer(f"Введите номер вопроса {current_data}!", reply_markup=ReplyKeyboardRemove())
    

@router.message(Command("change_del_list"))
async def change_list_to_del(message: Message, state: FSMContext):
    """Обработчик команды изменения списка мусорных слов"""
    await state.clear()

    kb = [
        [
            KeyboardButton(text="Удалить", reply_markup=ReplyKeyboardRemove()),
            KeyboardButton(text="Добавить", reply_markup=ReplyKeyboardRemove()),
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Будем что-то менять?",
    )

    user_id = message.from_user.id

    # Проверка прав пользователя
    if user_id not in config.allowed_users:
        await message.answer("У вас нет доступа к этой функции.")
        return

    await message.answer(f"Ваш список мусора имеет следующий вид:\n{', '.join(config.trash_list)}")
    await state.set_state(AdminState.change_del_list)
    await message.answer("Выберите действие которое вы хотите произвести", reply_markup=keyboard)


@router.message(AdminState.change_del_list, F.text == "Удалить")
@router.message(AdminState.change_del_list, F.text == "Добавить")
async def list_to_del(message: Message, state: FSMContext):
    """Обработчик выбора действия для списка мусорных слов"""
    await message.answer("ВНИМАНИЕ!!!\nИзменения влияют на всех пользователей", reply_markup=ReplyKeyboardRemove())
    if message.text == "Удалить":
        await state.set_state(AdminState.put_away_del_list)
        await message.answer("Введите мусор который необходимо убрать из списка \n Сообщение должно иметь вид: "
                             "\nМусор1, Мусор2, Мусор3 ...")
    elif message.text == "Добавить":
        await state.set_state(AdminState.add_del_list)
        await message.answer("Введите мусор который необходимо добавить в список \n Сообщение должно иметь вид: "
                             "\nМусор1, Мусор2, Мусор3 ...")


@router.message(AdminState.put_away_del_list)
@router.message(AdminState.add_del_list)
async def add_put_del_list(message: Message, state: FSMContext):
    """Обработчик изменения списка мусорных слов"""
    current_state = await state.get_state()
    
    if current_state == AdminState.put_away_del_list:
        message_list = message.text.split(", ")
        for elem in message_list:
            if elem in config.trash_list:
                config.trash_list.remove(elem)
    elif current_state == AdminState.add_del_list:
        message_list = message.text.split(", ")
        for elem in message_list:
            config.trash_list.append(elem)

    # Сохраняем изменения в файл
    config.save_trash_list()

    await message.answer(f"Список был изменен и теперь имеет следующий вид:\n{', '.join(config.trash_list)}")
    await state.clear()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    """Обработчик команды административной панели"""
    await state.clear()

    kb = [
        [
            KeyboardButton(text="Удалить", reply_markup=ReplyKeyboardRemove()),
            KeyboardButton(text="Добавить", reply_markup=ReplyKeyboardRemove()),
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Будем что-то менять?",
    )

    user_id = message.from_user.id
    
    # Проверка прав администратора
    if user_id not in config.admin_users:
        await message.answer("Вы не администратор, вам сюда нельзя!!!")
        return

    await state.set_state(AdminState.change_users_list)
    await message.answer("Выберите действие которое вы хотите произвести", reply_markup=keyboard)


@router.message(AdminState.change_users_list, F.text == "Удалить")
@router.message(AdminState.change_users_list, F.text == "Добавить")
async def users_list(message: Message, state: FSMContext):
    """Обработчик выбора действия для изменения списка пользователей"""
    if message.text == "Удалить":
        await state.set_state(AdminState.put_away_users_list)
        await message.answer("Отправьте id пользователя которого необходимо удалить", reply_markup=ReplyKeyboardRemove())
    elif message.text == "Добавить":
        await state.set_state(AdminState.add_users_list)
        await message.answer("Отправьте id пользователя которого необходимо добавить", reply_markup=ReplyKeyboardRemove())


@router.message(AdminState.put_away_users_list)
@router.message(AdminState.add_users_list)
async def add_put_users_list(message: Message, state: FSMContext):
    """Обработчик изменения списка пользователей с доступом"""
    if not message.text.isdigit():
        await message.answer("Вы ввели не цифру, повторите ввод!")
        return

    if int(message.text) == 0:
        await message.answer('Вы ввели "0", а это неправильно, так что повторите ввод')
        return

    user_id = int(message.text)
    current_state = await state.get_state()
    
    if current_state == AdminState.put_away_users_list:
        if user_id in config.allowed_users:
            config.allowed_users.remove(user_id)
    elif current_state == AdminState.add_users_list:
        config.allowed_users.append(user_id)

    # Сохраняем изменения в файл
    config.save_allowed_users()

    await message.answer("Список пользователей с особым доступом был изменен")
    await state.clear()


@router.message(Command("get_my_id"))
async def get_my_id(message: Message):
    """Обработчик команды получения ID пользователя"""
    user_id = message.from_user.id
    await message.answer(f"{user_id}") 