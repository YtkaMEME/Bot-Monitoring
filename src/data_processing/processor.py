import os
from typing import Tuple, Optional, List, Any
from aiogram.types import Message

from .calculate_targets import fetch_form_data, save_calculation_results, \
    calculate_weights_from_questions
from .file_processor import read_file, table_validation, create_questions_list
from .analyzer import analyze_questions
from .models import AnalysisError
from .prepare_target_distributions import prepare_target_distributions


async def process_data(
    path: str,
    mood_number: Optional[int] = None,
    nps_number: Optional[int] = None,
    csi_numbers: Optional[List[int]] = None,
    message: Optional[Message] = None,
    type_analyze = "standard",
    question_numbers_weights:Optional[List[int]] = None
) -> Tuple[str, str]:
    """
    Обработка данных из файла анкеты
    
    Args:
        path: путь к файлу Excel
        mood_number: номер вопроса о настроении
        nps_number: номер вопроса NPS
        csi_numbers: номера вопросов CSI
        message: объект сообщения для отправки уведомлений
        
    Returns:
        Кортеж с путями к файлам Excel и CSV
    """
    # Получаем имя файла для создания выходных файлов
    name = path.split("/")[-1].split(".")[0]
    excel_path = f'./{name}_modified.xlsx'
    csv_path = f'./{name}_modified.csv'
    
    # Чтение и валидация данных из файла
    df = read_file(path)
    df = table_validation(df)
    # Создание списка вопросов
    questions_list = create_questions_list(df)

    if type_analyze == "weighted":
        (male_count, female_count, art_school_labels, art_school_distribution,
         age_group_labels, age_group_distribution) = fetch_form_data()

        # Параметры дисперсионного расчёта
        confidence_level = 0.95
        p = 0.5
        E = 0.05

        # Получаем таргетные распределения
        target_pol, target_age, target_art, sample_size = prepare_target_distributions(
            male_count, female_count,
            age_group_distribution, age_group_labels,
            art_school_distribution, art_school_labels,
            confidence_level, p, E)
        save_calculation_results(sample_size, target_pol, target_age, target_art)
        questions_list = calculate_weights_from_questions(questions_list, question_numbers_weights,
                                                      [target_pol, target_age, target_art], sample_size)

    first_question = questions_list[0]
    total_rows = len(first_question.data)

    num_persons = total_rows - 2

    try:
        # Анализ вопросов
        if type_analyze == "standard":
            result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons)
        else:
            result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, sample_size)

        
        # Сохранение результатов
        result.to_excel(excel_path)
        result.to_csv(csv_path)
        
        # Отправка сообщения о пропущенных вопросах
        if message and result.skipped_questions:
            await message.answer(f"Были пропущены следующие вопросы{result.skipped_questions}")
        
    except AnalysisError as e:
        if message:
            await message.answer(f"{e}")
        if os.path.exists(path):
            os.remove(path)
        raise
    except Exception as e:
        if message:
            await message.answer(f"Произошла какая-то ошибка \U0001F63F\nНо ведь у меня лапки\U0001F43E")
        if os.path.exists(path):
            os.remove(path)
        raise
    
    return excel_path, csv_path

