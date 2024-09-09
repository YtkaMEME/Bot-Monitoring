from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram import Router
import json
from file_change import main_data_analytics
import help_file
import os

router = Router()
bot = help_file.bot


class MainState(StatesGroup):
    file = State()
    mood = State()
    mood_number = State()
    nps = State()
    nps_number = State()
    csi = State()
    csi_number = State()
    start_process = State()
    num_person = State()
    change_del_list = State()
    add_del_list = State()
    put_away_del_list = State()
    change_users_list = State()
    add_users_list = State()
    put_away_users_list = State()


def get_keyboard():
    kb = [
        [
            KeyboardButton(text="Да", reply_markup=ReplyKeyboardRemove()),
            KeyboardButton(text="Нет", reply_markup=ReplyKeyboardRemove()),
        ],
    ]
    keyboard = ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        input_field_placeholder="Выбери вариант",
    )

    return keyboard


async def start_process(state, message):
    user_data = await state.get_data()

    (path, doc) = user_data["file"]
    mood = False
    nps = False
    csi = False
    num_person = user_data["person_number"]

    os.makedirs(os.path.dirname(path), exist_ok=True)

    await bot.download(file=doc, destination=path)

    if "mood_number" in user_data:
        mood = user_data["mood_number"]

    if "nps_number" in user_data:
        nps = user_data["nps_number"]

    if "csi_number" in user_data:
        csi = user_data["csi_number"]

    await state.clear()

    (excel_path, csv_path) = await main_data_analytics(path, mood, nps, csi, message, num_person)

    os.remove(path)

    return excel_path, csv_path


async def question_repeated(state, number):
    user_data = await state.get_data()

    if "mood_number" in user_data:
        if int(user_data["mood_number"]) == int(number):
            return True

    if "nps_number" in user_data:
        if int(user_data["nps_number"]) == int(number):
            return True

    if "csi_number" in user_data:
        if int(user_data["csi_number"]) == int(number):
            return True

    return False


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("Мяувет! \U0001F638")
    await message.answer("Если хочешь начать работу - отправь мне файл выгрузку с анкетолога в формате .xlsx")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отмена прошла успешно, вы можете заново отправить файл", reply_markup=ReplyKeyboardRemove())


@router.message(F.document)
async def get_doc(message: Message, state: FSMContext):
    await state.clear()
    document = message.document
    doc_name = document.file_name

    if ".xlsx" not in doc_name:
        await message.answer("Проверьте отправленный файл, он должен соответствовать формату .xlsx")
        return

    file_path = f'./downloads/{doc_name}'

    await state.update_data(file=(file_path, document))

    await state.set_state(MainState.num_person)
    await message.answer(f"Введите количество участников, прошедших опрос", reply_markup=ReplyKeyboardRemove())


@router.message(MainState.mood, F.text == "Да")
@router.message(MainState.nps, F.text == "Да")
@router.message(MainState.csi, F.text == "Да")
async def yes_quest(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state != MainState.csi:
        await message.answer(f"Введите номер вопроса!", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(f"Введите номер вопроса первого CSI вопроса", reply_markup=ReplyKeyboardRemove())
    if current_state == MainState.csi:
        await state.set_state(MainState.csi_number)
    elif current_state == MainState.nps:
        await state.set_state(MainState.nps_number)
    elif current_state == MainState.mood:
        await state.set_state(MainState.mood_number)


@router.message(MainState.mood, F.text == "Нет")
@router.message(MainState.nps, F.text == "Нет")
@router.message(MainState.csi, F.text == "Нет")
async def no_quest(message: Message, state: FSMContext):
    current_state = await state.get_state()
    keyboard = get_keyboard()

    if current_state == MainState.csi:
        await state.set_state(MainState.start_process)
        await message.answer(f"Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())
        (excel_path, csv_path) = await start_process(state, message)
        chat_id = message.from_user.id
        await bot.send_document(chat_id=chat_id, document=FSInputFile(excel_path))
        await bot.send_document(chat_id=chat_id, document=FSInputFile(csv_path))
        os.remove(excel_path)
        os.remove(csv_path)

    elif current_state == MainState.nps:
        await state.set_state(MainState.csi)
        await message.answer("Присутствуют ли CSI вопросы?", reply_markup=keyboard)

    elif current_state == MainState.mood:
        await state.set_state(MainState.nps)
        keyboard = get_keyboard()
        await message.answer("Присутствует ли NPS вопрос?", reply_markup=keyboard)


@router.message(MainState.num_person)
@router.message(MainState.nps_number)
@router.message(MainState.mood_number)
@router.message(MainState.csi_number)
async def handle_number(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Вы ввели не цифру, повторите ввод!")
        return

    if int(message.text) == 0:
        await message.answer('Вы ввели "0", а это неправильно, так что повторите ввод')
        return

    number_repeated = await question_repeated(state, message.text)
    if number_repeated:
        await message.answer("Введенные вами вопросы не могут совпадать!\nПовторите ввод номера вопроса")
        return

    current_state = await state.get_state()

    keyboard = get_keyboard()
    number = int(message.text)

    if current_state == MainState.num_person:
        await state.update_data(person_number=number)
        await state.set_state(MainState.mood)
        await message.answer("Присутствует вопрос про настроение?", reply_markup=keyboard)

    elif current_state == MainState.mood_number:
        await state.update_data(mood_number=number)
        await state.set_state(MainState.nps)
        await message.answer("Присутствуют ли NPS вопросы?", reply_markup=keyboard)

    elif current_state == MainState.nps_number:
        await state.update_data(nps_number=number)
        await state.set_state(MainState.csi)
        await message.answer("Присутствуют ли CSI вопросы?", reply_markup=keyboard)

    elif current_state == MainState.csi_number:
        await state.update_data(csi_number=[number, number + 1])
        await message.answer(f"Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())

        (excel_path, csv_path) = await start_process(state, message)

        chat_id = message.from_user.id

        await bot.send_document(chat_id=chat_id, document=FSInputFile(excel_path))
        await bot.send_document(chat_id=chat_id, document=FSInputFile(csv_path))

        os.remove(csv_path)
        os.remove(excel_path)


@router.message(Command("change_del_list"))
async def change_list_to_del(message: Message, state: FSMContext):
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

    allowed_user_ids = help_file.get_allowed_user_ids()

    if user_id not in allowed_user_ids:
        await message.answer("У вас нет доступа к этой функции.")
        return

    with open('list_to_del.json', 'r', encoding='utf-8') as file:
        str_to_del = json.load(file)

    await message.answer(f"Ваш список мусора имеет следующий вид:\n{', '.join(str_to_del)}")
    await state.set_state(MainState.change_del_list)
    await message.answer("Выберите действие которое вы хотите произвести", reply_markup=keyboard)


@router.message(MainState.change_del_list, F.text == "Удалить")
@router.message(MainState.change_del_list, F.text == "Добавить")
async def list_to_del(message: Message, state: FSMContext):
    await message.answer("ВНИМАНИЕ!!!\nИзменения влияют на всех пользователей", reply_markup=ReplyKeyboardRemove())
    if message.text == "Удалить":
        await state.set_state(MainState.put_away_del_list)
        await message.answer("Введите мусор который необходимо убрать из списка \n Сообщение должно иметь вид: "
                             "\nМусор1, Мусор2, Мусор3 ...")
    elif message.text == "Добавить":
        await state.set_state(MainState.add_del_list)
        await message.answer("Введите мусор который необходимо добавить в список \n Сообщение должно иметь вид: "
                             "\nМусор1, Мусор2, Мусор3 ...")


@router.message(MainState.put_away_del_list)
@router.message(MainState.add_del_list)
async def add_put_del_list(message: Message, state: FSMContext):
    with open('list_to_del.json', 'r', encoding='utf-8') as file:
        str_to_del = json.load(file)

    current_state = await state.get_state()
    if current_state == MainState.put_away_del_list:
        message_list = message.text.split(", ")
        for elem in message_list:
            if elem in str_to_del:
                str_to_del.remove(elem)
    elif current_state == MainState.add_del_list:
        message_list = message.text.split(", ")
        for elem in message_list:
            str_to_del.append(elem)

    with open('list_to_del.json', 'w', encoding='utf-8') as file:
        json.dump(str_to_del, file, ensure_ascii=False, indent=4)

    await message.answer(f"Список был изменен и теперь имеет следующий вид:\n{', '.join(str_to_del)}")

    await state.clear()


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
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

    with open('admins.json', 'r', encoding='utf-8') as file:
        admins_users = json.load(file)

    user_id = message.from_user.id
    if user_id not in admins_users:
        await message.answer("Вы не администратор, вам сюда нельзя!!!")
        return

    await state.set_state(MainState.change_users_list)

    await message.answer("Выберите действие которое вы хотите произвести", reply_markup=keyboard)


@router.message(MainState.change_users_list, F.text == "Удалить")
@router.message(MainState.change_users_list, F.text == "Добавить")
async def users_list(message: Message, state: FSMContext):
    if message.text == "Удалить":
        await state.set_state(MainState.put_away_users_list)
        await message.answer("Отправьте id пользователя которого необходимо удалить", reply_markup=ReplyKeyboardRemove())
    elif message.text == "Добавить":
        await state.set_state(MainState.add_users_list)
        await message.answer("Отправьте id пользователя которого необходимо добавить", reply_markup=ReplyKeyboardRemove())


@router.message(MainState.put_away_users_list)
@router.message(MainState.add_users_list)
async def add_put_users_list(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Вы ввели не цифру, повторите ввод!")
        return

    if int(message.text) == 0:
        await message.answer('Вы ввели "0", а это неправильно, так что повторите ввод')
        return

    user_id = int(message.text)

    user_list = help_file.get_allowed_user_ids()

    current_state = await state.get_state()
    if current_state == MainState.put_away_users_list:
        if user_id in user_list:
            user_list.remove(user_id)
    elif current_state == MainState.add_users_list:
        user_list.append(user_id)

    with open('allowed_user_ids.json', 'w', encoding='utf-8') as file:
        json.dump(user_list, file, ensure_ascii=False, indent=4)

    await message.answer(f"Список пользователей с особым доступом был изменен")

    await state.clear()


@router.message(Command("get_my_id"))
async def get_my_id(message: Message):
    user_id = message.from_user.id
    await message.answer(f"{user_id}")
