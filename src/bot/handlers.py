import os
import re
import asyncio
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup, FSInputFile, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from .states import MainState, AdminState
from .keyboards import (
    build_keyboard,
    get_yes_no_keyboard,
    get_back_keyboard,
    get_yandex_replace_keyboard,
    get_main_keyboard,
)
from .bot_instance import bot
from src.data_processing.processor import process_data
from src.utils.yandex_disk import (
    YandexDiskError,
    build_timestamped_name,
    check_file_exists_on_yandex,
    upload_single_file_to_yandex,
)
from src.utils.anketolog import (
    download_report_by_survey_name,
    locate_survey_by_name,
    create_report,
    wait_until_report_ready,
    download_file,
    get_extension,
    sanitize_filename,
    REPORT_FORMAT,
    AnketologError,
)
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


async def send_results_to_user(chat_id: int, file_paths: list[str]) -> None:
    """
    Отправляет файлы пользователю в Telegram.
    """
    for index, file_path in enumerate(file_paths):
        reply_markup = get_main_keyboard() if index == len(file_paths) - 1 else None
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(file_path),
            reply_markup=reply_markup,
        )


async def start_uploaded_file_processing(
    state: FSMContext,
    message: Message,
    file_path: str,
    original_file_name: str,
    document=None,
) -> None:
    """
    Запускает стандартный сценарий обработки файла без повторной отправки пользователем.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    await state.clear()
    await state.update_data(
        file_path=file_path,
        document=document,
        original_file_name=original_file_name,
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Стандартный", callback_data="standard"),
            InlineKeyboardButton(text="Взвешивание", callback_data="weighted")
        ]
    ])

    await state.set_state(MainState.type_analyze)
    msg = await message.answer("Выберите тип обработки", reply_markup=keyboard)
    data = await state.get_data()
    ids = data.get("question_message_ids", [])
    ids.append(msg.message_id)
    await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)


async def upload_results_to_yandex_and_send_links(
    chat_id: int, file_paths: list[str], original_file_name: str | None = None
) -> None:
    """
    Загружает на Яндекс.Диск только xlsx и отправляет ссылку в Telegram.
    Если файл с таким именем уже есть, просит пользователя подтвердить замену.
    """
    xlsx_path = next((path for path in file_paths if path.lower().endswith(".xlsx")), None)
    if not xlsx_path:
        await bot.send_message(chat_id=chat_id, text="XLSX файл не найден, ссылка на Яндекс.Диск не создана.")
        return

    file_name = original_file_name or os.path.basename(xlsx_path)
    exists = await check_file_exists_on_yandex(file_name)
    if exists is None:
        await bot.send_message(
            chat_id=chat_id,
            text="Загрузка на Яндекс.Диск не настроена. Проверьте YANDEX_DISK_TOKEN в .env",
        )
        return

    if exists:
        raise YandexDiskError("FILE_EXISTS")

    uploaded = await upload_single_file_to_yandex(
        local_path=xlsx_path,
        overwrite=False,
        remote_name=file_name,
    )
    if not uploaded:
        await bot.send_message(
            chat_id=chat_id,
            text="Загрузка на Яндекс.Диск не настроена. Проверьте YANDEX_DISK_TOKEN в .env",
        )
        return

    uploaded_name, link = uploaded
    await bot.send_message(chat_id=chat_id, text=f"Файл загружен на Яндекс.Диск:\n{uploaded_name}: {link}")

async def ask_yandex_upload_choice(state: FSMContext, message: Message) -> None:
    await state.set_state(MainState.yandex_upload)
    msg = await message.answer(
        "Загрузить файлы на Яндекс.Диск и отправить ссылку?",
        reply_markup=get_yes_no_keyboard(),
    )
    data = await state.get_data()
    ids = data.get("question_message_ids", [])
    ids.append(msg.message_id)
    await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)


async def process_and_send_results(
    state: FSMContext, message: Message, chat_id: int, upload_to_yandex: bool
) -> None:
    proc_msg = await message.answer("Происходит обработка данных...", reply_markup=ReplyKeyboardRemove())

    excel_path, csv_path = await start_process_data(state, message)
    file_paths = [excel_path, csv_path]
    user_data = await state.get_data()
    original_file_name = user_data.get("original_file_name")

    # Сначала отправляем файлы пользователю
    await send_results_to_user(chat_id, file_paths)

    # После отправки файлов опционально загружаем на Яндекс.Диск и отправляем ссылки
    if upload_to_yandex:
        try:
            await upload_results_to_yandex_and_send_links(
                chat_id,
                [excel_path],
                original_file_name=original_file_name,
            )
        except YandexDiskError as error:
            if str(error) == "FILE_EXISTS":
                await state.update_data(
                    pending_file_paths=file_paths,
                    pending_chat_id=chat_id,
                    original_file_name=original_file_name,
                )
                await state.set_state(MainState.yandex_replace)
                msg = await message.answer(
                    "Файл с таким именем уже есть на Яндекс.Диске. Заменить?",
                    reply_markup=get_yandex_replace_keyboard(),
                )
                data = await state.get_data()
                ids = data.get("question_message_ids", [])
                ids.append(msg.message_id)
                await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)
                try:
                    await proc_msg.delete()
                except Exception:
                    pass
                return
            await bot.send_message(chat_id=chat_id, text=f"Не удалось загрузить файл на Яндекс.Диск: {error}")
        except OSError as error:
            await bot.send_message(chat_id=chat_id, text=f"Ошибка чтения файла при загрузке: {error}")

    # Удаляем все предыдущие вопросные сообщения бота
    data_state = await state.get_data()
    ids = data_state.get("question_message_ids", []) or []
    last_bot_id = data_state.get("last_bot_message_id")
    if last_bot_id and last_bot_id not in ids:
        ids.append(last_bot_id)
    for msg_id in ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception:
            pass

    try:
        await proc_msg.delete()
    except Exception:
        pass

    # Удаляем временные файлы
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)
    await state.clear()

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

    # Если файл пришел из Telegram, сначала скачиваем его локально.
    if doc is not None:
        await bot.download(file=doc, destination=path)

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

    # Проверка повтора для вопроса настроения
    if "mood_number" in user_data:
        try:
            if int(user_data["mood_number"]) == number:
                return True
        except (TypeError, ValueError):
            pass

    # Проверка повтора для NPS (один или несколько номеров)
    if "nps_number" in user_data and user_data["nps_number"]:
        nps_numbers = user_data["nps_number"]
        if isinstance(nps_numbers, list):
            if number in nps_numbers:
                return True
        else:
            try:
                if int(nps_numbers) == number:
                    return True
            except (TypeError, ValueError):
                pass

    # Проверка повтора для CSI (массив номеров или одно значение)
    if "csi_number" in user_data and user_data["csi_number"]:
        csi_numbers = user_data["csi_number"]
        if isinstance(csi_numbers, list):
            if number in csi_numbers:
                return True
        else:
            try:
                if int(csi_numbers) == number:
                    return True
            except (TypeError, ValueError):
                pass

    return False


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer("Мяувет! \U0001F638", reply_markup=get_main_keyboard())
    await message.answer("Если хочешь начать работу - отправь мне файл выгрузку с анкетолога в формате .xlsx")
    await message.answer("Если хочешь получить отчет по названию анкеты, нажми кнопку `Скачать отчет из Anketolog`.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel"""
    await state.clear()
    await message.answer(
        "Отмена прошла успешно, вы можете заново отправить файл",
        reply_markup=get_main_keyboard(),
    )


@router.message(F.text == "Скачать отчет из Anketolog")
async def get_anketolog_report_command(message: Message, state: FSMContext):
    """Запуск сценария получения отчета из Anketolog по названию анкеты."""
    await state.clear()
    await state.set_state(MainState.survey_report_name)
    await message.answer(
        "Отправьте название анкеты из Anketolog. После этого я попрошу подтвердить, что название корректно.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(MainState.survey_report_name)
async def receive_survey_report_name(message: Message, state: FSMContext):
    survey_name = (message.text or "").strip()
    if not survey_name:
        await message.answer("Название анкеты не должно быть пустым. Попробуйте еще раз.")
        return

    await state.update_data(pending_survey_name=survey_name)
    await state.set_state(MainState.survey_report_confirm)
    await message.answer(
        f"Это название анкеты:\n{survey_name}\n\nОно корректно?",
        reply_markup=get_yes_no_keyboard(),
    )


@router.message(F.document)
async def get_doc(message: Message, state: FSMContext):
    """Обработчик получения документа"""
    document = message.document
    doc_name = document.file_name

    if ".xlsx" not in doc_name:
        await message.answer("Проверьте отправленный файл, он должен соответствовать формату .xlsx")
        return

    file_path = f'{config.download_dir}/{doc_name}'
    await start_uploaded_file_processing(
        state=state,
        message=message,
        file_path=file_path,
        original_file_name=doc_name,
        document=document,
    )

@router.callback_query(MainState.type_analyze, F.data.in_(["standard", "weighted"]))
async def process_analyze_type(callback_query: CallbackQuery, state: FSMContext):
    analyze_type = callback_query.data

    await callback_query.answer()  # убирает крутилку у кнопки

    # Удаляем сообщение с инлайн-клавиатурой
    await callback_query.message.delete()

    if analyze_type == "standard":
        await state.update_data(analyze_type="standard")
        await state.set_state(MainState.division)
        msg = await callback_query.message.answer(
            "Хотите ли вы разделять выгрузку по какому либо вопросу?",
            reply_markup=get_yes_no_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(msg.message_id)
        await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)
    else:
        await state.update_data(analyze_type="weighted")
        await state.set_state(MainState.gender)
        msg = await callback_query.message.answer(
            "Введите номер вопроса определяющего Пол участника",
            reply_markup=get_back_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(msg.message_id)
        await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)


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
    data = await state.get_data()
    checkbox_state = data["checkbox_state"]
    # Формируем упорядоченный список выбранных параметров
    steps = [opt for opt in OPTIONS if checkbox_state.get(opt)]

    if not steps:
        await callback_query.message.delete()
        await ask_yandex_upload_choice(state, callback_query.message)
        return
    
    # Инициализируем шаги и индекс для прохождения специальных вопросов
    await state.update_data(steps=steps, step_index=0, current_data=steps[0])
    await state.set_state(MainState.checkbox_menu_numbers)

    msg = await callback_query.message.answer(
        f"Введите номер вопроса {steps[0]}!",
        reply_markup=get_back_keyboard()
    )
    data = await state.get_data()
    ids = data.get("question_message_ids", [])
    ids.append(msg.message_id)
    await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)
    await callback_query.message.delete()


@router.callback_query(MainState.division, F.data == "division_yes")
@router.callback_query(MainState.yandex_upload, F.data == "division_yes")
@router.callback_query(MainState.yandex_replace, F.data == "division_yes")
@router.callback_query(MainState.survey_report_confirm, F.data == "division_yes")
async def yes_quest(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик ответа 'Да' на вопросы о наличии специальных вопросов"""
    await callback_query.answer()
    await callback_query.message.delete()

    current_state = await state.get_state()
    if current_state == MainState.division:
        msg = await callback_query.message.answer(
            "Введите номер/номера вопроса/вопросов!",
            reply_markup=get_back_keyboard()
        )
        await state.set_state(MainState.division_number)
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(msg.message_id)
        await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)
        return

    if current_state == MainState.yandex_upload:
        await process_and_send_results(
            state=state,
            message=callback_query.message,
            chat_id=callback_query.message.chat.id,
            upload_to_yandex=True,
        )
        return

    if current_state == MainState.yandex_replace:
        data = await state.get_data()
        file_paths = data.get("pending_file_paths", [])
        chat_id = data.get("pending_chat_id", callback_query.message.chat.id)
        original_file_name = data.get("original_file_name")
        xlsx_path = next((path for path in file_paths if path.lower().endswith(".xlsx")), None)

        if xlsx_path:
            try:
                uploaded = await upload_single_file_to_yandex(
                    local_path=xlsx_path,
                    overwrite=True,
                    remote_name=original_file_name,
                )
                if uploaded:
                    uploaded_name, link = uploaded
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"Файл загружен на Яндекс.Диск:\n{uploaded_name}: {link}",
                    )
            except (YandexDiskError, OSError) as error:
                await bot.send_message(chat_id=chat_id, text=f"Не удалось загрузить файл на Яндекс.Диск: {error}")

        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
        await state.clear()
        return

    if current_state == MainState.survey_report_confirm:
        data = await state.get_data()
        survey_name = data.get("pending_survey_name")
        if not survey_name:
            await state.set_state(MainState.survey_report_name)
            await callback_query.message.answer("Не удалось получить название анкеты. Отправьте его еще раз.")
            return

        search_msg = await callback_query.message.answer("Начинаю поиск нужной анкеты в Anketolog...")
        handed_off_to_processing = False
        try:
            survey = await asyncio.to_thread(locate_survey_by_name, survey_name)
            survey_id = survey.get("id")
            survey_real_name = (survey.get("settings") or {}).get("name") or survey_name

            report_msg = await callback_query.message.answer(
                "Нужная анкета найдена. Начинаю формирование отчета в Anketolog..."
            )

            report = await asyncio.to_thread(create_report, survey_id)
            report_id = report.get("id")
            report_status = report.get("status")
            report_url = report.get("url")

            if report_status == "complete" and report_url:
                ready_format = report.get("format", REPORT_FORMAT)
                ext = get_extension(ready_format)
                file_path = os.path.join(
                    config.download_dir,
                    f"{sanitize_filename(survey_real_name)}_{survey_id}.{ext}",
                )
                await asyncio.to_thread(download_file, report_url, file_path)
            else:
                ready_report = await asyncio.to_thread(wait_until_report_ready, survey_id, report_id)
                ready_url = ready_report.get("url")
                ready_format = ready_report.get("format", REPORT_FORMAT)

                if not ready_url:
                    raise AnketologError("Отчет помечен как готовый, но URL отсутствует.")

                ext = get_extension(ready_format)
                file_path = os.path.join(
                    config.download_dir,
                    f"{sanitize_filename(survey_real_name)}_{survey_id}.{ext}",
                )
                await asyncio.to_thread(download_file, ready_url, file_path)

            await bot.send_document(
                chat_id=callback_query.message.chat.id,
                document=FSInputFile(file_path),
                caption=f"Отчет по анкете: {survey_real_name}",
            )
            await start_uploaded_file_processing(
                state=state,
                message=callback_query.message,
                file_path=file_path,
                original_file_name=os.path.basename(file_path),
                document=None,
            )
            handed_off_to_processing = True
        except AnketologError as error:
            await callback_query.message.answer(f"Не удалось получить отчет: {error}")
        except OSError as error:
            await callback_query.message.answer(f"Не удалось сохранить или отправить отчет: {error}")
        finally:
            try:
                await search_msg.delete()
            except Exception:
                pass
            if "report_msg" in locals():
                try:
                    await report_msg.delete()
                except Exception:
                    pass
            if "file_path" in locals() and not handed_off_to_processing and os.path.exists(file_path):
                os.remove(file_path)
            if not handed_off_to_processing:
                await state.clear()
        return


@router.callback_query(MainState.division, F.data == "division_no")
@router.callback_query(MainState.yandex_upload, F.data == "division_no")
@router.callback_query(MainState.yandex_replace, F.data == "division_no")
@router.callback_query(MainState.survey_report_confirm, F.data == "division_no")
async def no_quest(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.delete()

    current_state = await state.get_state()

    if current_state == MainState.division:
        await state.update_data(checkbox_state={opt: False for opt in OPTIONS})
        user_data = await state.get_data()
        user_data = user_data["checkbox_state"]
        markup = build_keyboard(user_data, OPTIONS)

        msg = await callback_query.message.answer(
            "Выбери параметры, которые присутствуют в выгрузке:",
            reply_markup=markup
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(msg.message_id)
        await state.update_data(last_bot_message_id=msg.message_id, question_message_ids=ids)
        return

    if current_state == MainState.yandex_upload:
        await process_and_send_results(
            state=state,
            message=callback_query.message,
            chat_id=callback_query.message.chat.id,
            upload_to_yandex=False,
        )
        return

    if current_state == MainState.yandex_replace:
        data = await state.get_data()
        file_paths = data.get("pending_file_paths", [])
        chat_id = data.get("pending_chat_id", callback_query.message.chat.id)
        await bot.send_message(
            chat_id=chat_id,
            text="Файл на Яндекс.Диск не сохранен. Исходный файл на диске оставлен без изменений.",
        )

        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
        await state.clear()
        return

    if current_state == MainState.survey_report_confirm:
        await state.set_state(MainState.survey_report_name)
        await callback_query.message.answer(
            "Хорошо, отправьте название анкеты еще раз.",
            reply_markup=get_back_keyboard(),
        )
        return


@router.callback_query(MainState.yandex_replace, F.data == "yandex_save_renamed")
async def save_renamed_to_yandex(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.delete()

    data = await state.get_data()
    file_paths = data.get("pending_file_paths", [])
    chat_id = data.get("pending_chat_id", callback_query.message.chat.id)
    original_file_name = data.get("original_file_name")
    xlsx_path = next((path for path in file_paths if path.lower().endswith(".xlsx")), None)

    if xlsx_path:
        remote_name = build_timestamped_name(original_file_name or os.path.basename(xlsx_path))
        try:
            uploaded = await upload_single_file_to_yandex(
                local_path=xlsx_path,
                overwrite=False,
                remote_name=remote_name,
            )
            if uploaded:
                uploaded_name, link = uploaded
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"Файл загружен на Яндекс.Диск:\n{uploaded_name}: {link}",
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "Исходный файл на Яндекс.Диске не был заменен. "
                        f"Сохранена новая версия с измененным названием: {uploaded_name}"
                    ),
                )
        except (YandexDiskError, OSError) as error:
            await bot.send_message(chat_id=chat_id, text=f"Не удалось загрузить файл на Яндекс.Диск: {error}")

    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)
    await state.clear()

@router.message(MainState.gender)
@router.message(MainState.age)
@router.message(MainState.art_school)
@router.message(MainState.division_number)
@router.message(MainState.checkbox_menu_numbers)
async def handle_number(message: Message, state: FSMContext):
    """Обработчик ввода числовых значений"""

    current_state = await state.get_state()
    data_state = await state.get_data()
    division_number = [1]

    # Обновляем последнее сообщение пользователя (для возможного шага Назад)
    await state.update_data(last_user_message_id=message.message_id)

    # Обработка нецифрового ввода для специальных случаев
    if not message.text.isdigit():
        # Парсинг нескольких номеров для деления
        if current_state == MainState.division_number:
            text_message = message.text.strip()
            division_number = [int(num) for num in re.findall(r'\d+', text_message)]
            if not division_number:
                await message.answer("Вы не указали ни одного номера вопроса, повторите ввод!")
                return
        # Парсинг нескольких номеров для NPS (ввод через запятую)
        elif current_state == MainState.checkbox_menu_numbers and data_state.get("current_data") == "NPS":
            # Разрешаем ввод нескольких NPS через запятую/пробелы (26, 27)
            text_message = message.text.strip()
            nps_numbers = [int(num) for num in re.findall(r'\d+', text_message)]
            if not nps_numbers:
                await message.answer("Вы не указали ни одного номера вопроса, повторите ввод!")
                return
            if 0 in nps_numbers:
                await message.answer('Вы ввели "0", а это неправильно, так что повторите ввод')
                return
            # Проверяем пересечения с уже выбранными специальными вопросами
            for num in nps_numbers:
                if await is_question_repeated(state, num):
                    await message.answer("Введенные вами вопросы не могут совпадать!\nПовторите ввод номера вопроса")
                    return

            # Сохраняем список NPS номеров
            await state.update_data(nps_number=nps_numbers)

            # Переходим к следующему спец-вопросу или запускаем обработку — та же логика, что и ниже
            steps = data_state.get("steps", [])
            step_index = data_state.get("step_index", 0)

            step_index += 1
            await state.update_data(step_index=step_index)

            if step_index < len(steps):
                next_opt = steps[step_index]
                await state.update_data(current_data=next_opt)

                last_bot_id = data_state.get("last_bot_message_id")
                if last_bot_id:
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=last_bot_id)
                    except Exception:
                        pass

                bot_msg = await message.answer(
                    f"Введите номер вопроса {next_opt}!",
                    reply_markup=get_back_keyboard()
                )
                await state.update_data(last_bot_message_id=bot_msg.message_id)
            else:
                await ask_yandex_upload_choice(state, message)
            return
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

    if current_state == MainState.gender:
        await state.update_data(gender=number)
        await state.set_state(MainState.age)
        bot_msg = await message.answer(
            "Введите номер вопроса определяющего Возраст участника",
            reply_markup=get_back_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return
    
    elif current_state == MainState.age:
        await state.update_data(age=number)
        await state.set_state(MainState.art_school)
        bot_msg = await message.answer(
            "Введите номер вопроса определяющего Арт школу участника",
            reply_markup=get_back_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    elif current_state == MainState.art_school:
        await state.update_data(art_school=number)
        await state.set_state(MainState.division)
        bot_msg = await message.answer(
            "Хотите ли вы разделять выгрузку по какому либо вопросу?",
            reply_markup=get_yes_no_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    elif current_state == MainState.division_number:
        await state.update_data(division=division_number)
        await state.set_state(MainState.checkbox_menu)

        await state.update_data(checkbox_state={opt: False for opt in OPTIONS})
        user_data = await state.get_data()
        user_data = user_data["checkbox_state"]
        markup = build_keyboard(user_data, OPTIONS)

        bot_msg = await message.answer(
            "Выбери параметры, которые присутствуют в выгрузке:",
            reply_markup=markup
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    # Обработка специальных вопросов (Настроение / TR / ROTI / NPS / CSI)
    data_state = await state.get_data()
    if current_state == MainState.checkbox_menu_numbers:
        steps = data_state.get("steps", [])
        step_index = data_state.get("step_index", 0)
        if not steps or step_index >= len(steps):
            # На всякий случай, если что-то не так со списком шагов — возвращаем к чекбоксам
            await state.set_state(MainState.checkbox_menu)
            checkbox_state = data_state.get("checkbox_state", {opt: False for opt in OPTIONS})
            markup = build_keyboard(checkbox_state, OPTIONS)
            bot_msg = await message.answer(
                "Выбери параметры, которые присутствуют в выгрузке:",
                reply_markup=markup
            )
            await state.update_data(last_bot_message_id=bot_msg.message_id)
            return

        current_opt = steps[step_index]

        # Сохраняем введённое значение в зависимости от текущего параметра
        if current_opt == "Настроение":
            await state.update_data(mood_number=number)
        elif current_opt == "CSI":
            await state.update_data(csi_number=[number, number + 1])
        elif current_opt == "NPS":
            # Если ранее уже был список NPS, дополним его, иначе создадим новый список
            existing_nps = data_state.get("nps_number") or []
            if not isinstance(existing_nps, list):
                existing_nps = [int(existing_nps)]
            if number in existing_nps:
                await message.answer("Введенные вами вопросы не могут совпадать!\nПовторите ввод номера вопроса")
                return
            existing_nps.append(number)
            await state.update_data(nps_number=existing_nps)
        elif current_opt == "TR":
            await state.update_data(tr=number)
        elif current_opt == "ROTI":
            await state.update_data(roti=number)

        # Переходим к следующему параметру или запускаем обработку
        step_index += 1
        await state.update_data(step_index=step_index)

        if step_index < len(steps):
            next_opt = steps[step_index]
            await state.update_data(current_data=next_opt)

            # Удаляем предыдущее сообщение бота с вопросом, если оно есть
            last_bot_id = data_state.get("last_bot_message_id")
            if last_bot_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=last_bot_id)
                except Exception:
                    pass

            bot_msg = await message.answer(
                f"Введите номер вопроса {next_opt}!",
                reply_markup=get_back_keyboard()
            )
            data_state = await state.get_data()
            ids = data_state.get("question_message_ids", [])
            ids.append(bot_msg.message_id)
            await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        else:
            await ask_yandex_upload_choice(state, message)
        return


@router.callback_query(F.data == "back")
async def go_back(callback_query: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки Назад: возвращает пользователя к предыдущему шагу
    и удаляет последнее сообщение бота и последнее сообщение пользователя.
    """
    await callback_query.answer()
    current_state = await state.get_state()
    data = await state.get_data()

    # Удаляем сообщение бота с инлайн-кнопками
    try:
        await callback_query.message.delete()
    except Exception:
        pass

    # Логика возврата по основным шагам диалога
    if current_state == MainState.gender:
        # Возврат к выбору типа обработки
        await state.set_state(MainState.type_analyze)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Стандартный", callback_data="standard"),
                InlineKeyboardButton(text="Взвешивание", callback_data="weighted")
            ]
        ])
        bot_msg = await callback_query.message.answer("Выберите тип обработки", reply_markup=keyboard)
        await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.age:
        await state.set_state(MainState.gender)
        bot_msg = await callback_query.message.answer(
            "Введите номер вопроса определяющего Пол участника",
            reply_markup=get_back_keyboard()
        )
        await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.art_school:
        await state.set_state(MainState.age)
        bot_msg = await callback_query.message.answer(
            "Введите номер вопроса определяющего Возраст участника",
            reply_markup=get_back_keyboard()
        )
        await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.survey_report_name:
        await state.clear()
        await callback_query.message.answer(
            "Получение отчета по названию анкеты отменено.",
            reply_markup=get_main_keyboard(),
        )
        return

    if current_state == MainState.division:
        # В зависимости от типа анализа возвращаемся либо к выбору типа,
        # либо к последнему вопросу взвешивания (арт-школа)
        analyze_type = data.get("analyze_type")
        if analyze_type == "weighted":
            await state.set_state(MainState.art_school)
            bot_msg = await callback_query.message.answer(
                "Введите номер вопроса определяющего Арт школу участника",
                reply_markup=get_back_keyboard()
            )
            await state.update_data(last_bot_message_id=bot_msg.message_id)
        else:
            await state.set_state(MainState.type_analyze)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Стандартный", callback_data="standard"),
                    InlineKeyboardButton(text="Взвешивание", callback_data="weighted")
                ]
            ])
            bot_msg = await callback_query.message.answer("Выберите тип обработки", reply_markup=keyboard)
            await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.division_number:
        await state.set_state(MainState.division)
        bot_msg = await callback_query.message.answer(
            "Хотите ли вы разделять выгрузку по какому либо вопросу?",
            reply_markup=get_yes_no_keyboard()
        )
        await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.checkbox_menu:
        # Возврат к вопросу о делении
        await state.set_state(MainState.division)
        bot_msg = await callback_query.message.answer(
            "Хотите ли вы разделять выгрузку по какому либо вопросу?",
            reply_markup=get_yes_no_keyboard()
        )
        await state.update_data(last_bot_message_id=bot_msg.message_id)
        return

    if current_state == MainState.checkbox_menu_numbers:
        # Возврат внутри последовательности специальных вопросов
        steps = data.get("steps", [])
        step_index = data.get("step_index", 0)

        if not steps:
            # Если шагов нет — возвращаемся к чекбоксам
            await state.set_state(MainState.checkbox_menu)
            checkbox_state = data.get("checkbox_state", {opt: False for opt in OPTIONS})
            markup = build_keyboard(checkbox_state, OPTIONS)
            bot_msg = await callback_query.message.answer(
                "Выбери параметры, которые присутствуют в выгрузке:",
                reply_markup=markup
            )
            data = await state.get_data()
            ids = data.get("question_message_ids", [])
            ids.append(bot_msg.message_id)
            await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
            return

        if step_index == 0:
            # На первом шаге специальных вопросов — возвращаемся к чекбоксам
            await state.set_state(MainState.checkbox_menu)
            checkbox_state = data.get("checkbox_state", {opt: False for opt in OPTIONS})
            markup = build_keyboard(checkbox_state, OPTIONS)
            bot_msg = await callback_query.message.answer(
                "Выбери параметры, которые присутствуют в выгрузке:",
                reply_markup=markup
            )
            data = await state.get_data()
            ids = data.get("question_message_ids", [])
            ids.append(bot_msg.message_id)
            await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
            return

        # Шаг назад внутри последовательности
        step_index -= 1
        last_opt = steps[step_index]

        # Очищаем сохранённое значение для этого параметра (ставим None)
        if last_opt == "Настроение":
            await state.update_data(mood_number=None)
        elif last_opt == "CSI":
            await state.update_data(csi_number=None)
        elif last_opt == "NPS":
            await state.update_data(nps_number=None)
        elif last_opt == "TR":
            await state.update_data(tr=None)
        elif last_opt == "ROTI":
            await state.update_data(roti=None)

        await state.update_data(step_index=step_index, current_data=last_opt)

        bot_msg = await callback_query.message.answer(
            f"Введите номер вопроса {last_opt}!",
            reply_markup=get_back_keyboard()
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    if current_state == MainState.yandex_upload:
        await state.set_state(MainState.checkbox_menu)
        checkbox_state = data.get("checkbox_state", {opt: False for opt in OPTIONS})
        markup = build_keyboard(checkbox_state, OPTIONS)
        bot_msg = await callback_query.message.answer(
            "Выбери параметры, которые присутствуют в выгрузке:",
            reply_markup=markup
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    if current_state == MainState.yandex_replace:
        await state.set_state(MainState.yandex_upload)
        bot_msg = await callback_query.message.answer(
            "Загрузить файлы на Яндекс.Диск и отправить ссылку?",
            reply_markup=get_yes_no_keyboard(),
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    if current_state == MainState.survey_report_confirm:
        await state.set_state(MainState.survey_report_name)
        bot_msg = await callback_query.message.answer(
            "Отправьте название анкеты из Anketolog.",
            reply_markup=get_back_keyboard(),
        )
        data = await state.get_data()
        ids = data.get("question_message_ids", [])
        ids.append(bot_msg.message_id)
        await state.update_data(last_bot_message_id=bot_msg.message_id, question_message_ids=ids)
        return

    # Если для текущего шага возврат не предусмотрен
    await callback_query.message.answer("Кнопка «Назад» недоступна на этом шаге.")

    

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