import os
from typing import Tuple, Optional, List, Any

import pandas as pd
from aiogram.types import Message

from .calculate_targets import fetch_form_data, save_calculation_results, \
    calculate_weights_from_questions
from .file_processor import read_file, table_validation, create_questions_list
from .analyzer import analyze_questions
from .models import AnalysisError, Question, AnalysisResult
from .prepare_target_distributions import prepare_target_distributions


def division_df(questions_list, division):
    division = f"D1_{division}"
    for q in questions_list:
        if q.id == division:
            division_question = q.data["value"].iloc[2:]
            break
    index_dict = {}

    for idx, value in division_question.items():
        if value not in index_dict:
            index_dict[value] = []
        index_dict[value].append(idx)

    result = {}
    for value, indices in index_dict.items():
        filtered_questions = []
        for question in questions_list:
            # Получаем данные по нужным индексам
            filtered_data = question.data.loc[indices]

            # Добавляем первые 2 записи (если они есть)
            first_two = question.data.iloc[:2]

            # Объединяем и удаляем возможные дубли (если индексы пересекаются)
            new_data = pd.concat([first_two, filtered_data])

            # Пересоздаем объект Question со срезанными данными
            new_question = Question(
                name=question.name,
                type_q=question.type,
                data=new_data,
                id=question.id
            )

            filtered_questions.append(new_question)

        result[value] = filtered_questions

    return result

async def process_data(
    path: str,
    mood_number: Optional[int] = None,
    nps_number: Optional[int] = None,
    csi_numbers: Optional[List[int]] = None,
    message: Optional[Message] = None,
    type_analyze = "standard",
    question_numbers_weights:Optional[List[int]] = None,
    division = None
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
    results_list = []
    try:
        if division is not None:
            dict_division = division_df(questions_list, division)
            for key in dict_division:
                questions_list = dict_division[key]
                # Анализ вопросов
                if type_analyze == "standard":
                    result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons)
                else:
                    result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, sample_size)

                for df in result.data_frames:
                    df["Разделитель"] = key

                if hasattr(result, "free_answers_frame"):
                    result.free_answers_frame["Разделитель"] = key

                if hasattr(result, "csi_frame"):
                    result.csi_frame["Разделитель"] = key

                if hasattr(result, "nps_frame"):
                    result.nps_frame["Разделитель"] = key

                results_list.append(result)
        else:
            if type_analyze == "standard":
                result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons)
            else:
                result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, sample_size)

        if division is not None:

            data_frames_list = []
            for result in results_list:
                df_block = result.data_frames

                if isinstance(df_block, pd.DataFrame):
                    data_frames_list.append(df_block)

                elif isinstance(df_block, list):
                    for df in df_block:
                        if isinstance(df, pd.DataFrame):
                            data_frames_list.append(df)

            free_answers_list = [result.free_answers_frame for result in results_list if
                                 result.free_answers_frame is not None]
            csi_list = [result.csi_frame for result in results_list if result.csi_frame is not None]
            nps_list = [result.nps_frame for result in results_list if result.nps_frame is not None]

            # объединяем каждый блок
            merged_data_frames = data_frames_list
            merged_free_answers = pd.concat(free_answers_list, ignore_index=True)
            merged_csi = pd.concat(csi_list, ignore_index=True)
            merged_nps = pd.concat(nps_list, ignore_index=True)

            result2 = AnalysisResult()

            result2.data_frames = merged_data_frames

            if result.free_answers_frame is not None:
                result2.free_answers_frame = merged_free_answers

            if csi_numbers:
                result2.csi_frame = merged_csi
            if nps_number:
                result2.nps_frame = merged_nps

            result = result2

        # Сохранение результатов

        if division is not None:
            result.to_excel_division(excel_path)
            result.to_csv(csv_path)
        else:
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

