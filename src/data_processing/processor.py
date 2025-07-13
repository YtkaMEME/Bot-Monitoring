import os
import re
from typing import Tuple, Optional, List, Any

import pandas as pd
from aiogram.types import Message

from .calculate_targets import fetch_form_data, save_calculation_results,   calculate_raw_weights_from_questions
from .file_processor import read_file, table_validation, create_questions_list
from .analyzer import analyze_questions
from .models import AnalysisError, Question, AnalysisResult
from .prepare_target_distributions import prepare_target_distributions


def division_df(questions_list, division, weights):
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
    weights_result = {}
    for value, indices in index_dict.items():
        filtered_questions = []
        for question in questions_list:
            # Получаем данные по нужным индексам
            filtered_data = question.data.loc[indices]
            filtered_weights = weights.loc[indices]

            # Добавляем первые 2 записи (если они есть)
            first_two = question.data.iloc[:2]

            # Объединяем и удаляем возможные дубли (если индексы пересекаются)
            new_data = pd.concat([first_two, filtered_data])
            new_data = new_data.reset_index(drop=True)

            filtered_weights = pd.concat([weights.iloc[:2], filtered_weights])
            filtered_weights = filtered_weights.reset_index(drop=True)

            # Пересоздаем объект Question со срезанными данными
            new_question = Question(
                name=question.name,
                type_q=question.type,
                data=new_data,
                id=question.id
            )

            filtered_questions.append(new_question)

        result[value] = filtered_questions
        weights_result[value] = filtered_weights

    return result, weights_result

def clean_text(text: str) -> str:
    if pd.isna(text):
        return ''
    # Приведение к нижнему регистру
    text = text.lower()
    # Удаление знаков препинания (оставляем только буквы, цифры и пробелы)
    text = re.sub(r'[^\w\s]', '', text)
    # Замена множественных пробелов на один
    text = re.sub(r'\s+', ' ', text)
    # Удаление пробелов в начале и конце строки
    return text.strip()

def clean_key(key: str) -> str:
    # Приводим к нижнему регистру
    key = key.lower()
    # Удаляем всё, кроме букв, цифр и пробелов
    key = re.sub(r'[^\w\s]', '', key)
    # Заменяем множественные пробелы на один
    key = re.sub(r'\s+', ' ', key)
    # Удаляем пробелы в начале и конце строки
    return key.strip()

def clean_dict_keys(data: dict) -> dict:
    return {clean_key(k): v for k, v in data.items()}

async def process_data(
    path: str,
    mood_number: Optional[int] = None,
    nps_number: Optional[int] = None,
    csi_numbers: Optional[List[int]] = None,
    message: Optional[Message] = None,
    type_analyze = "standard",
    question_numbers_weights:Optional[List[int]] = None,
    division = None,
    tr_number: Optional[int] = None,
    roti_number: Optional[int] = None
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

    target_pol, target_age, target_art, sample_size = None, None, None, None

    length = len(questions_list[0].data)
    weights = pd.DataFrame({'ones': [1] * length})

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

        # Сохраняем оригинальные версии
        original_target_pol = target_pol.copy()
        original_target_age = target_age.copy()
        original_target_art = target_art.copy()

        original_data_columns = {}  # сохраняем оригинальные данные по вопросам

        for q in questions_list:
            number_q = int(q.id.split("_")[1])
            if number_q in question_numbers_weights:
                col_name = q.data.columns[0]
                original_data_columns[q.id] = q.data[col_name].copy()  # копируем Series
                q.data[col_name] = q.data[col_name].astype(str).apply(clean_text)

        # Применяем очистку
        target_pol = clean_dict_keys(target_pol)
        target_age = clean_dict_keys(target_age)
        target_art = clean_dict_keys(target_art)

        for q in questions_list:
            number_q = int(q.id.split("_")[1])
            if number_q in question_numbers_weights:
                col_name = q.data.columns[0]
                q.data[col_name] = q.data[col_name].astype(str).apply(clean_text)

        weights = calculate_raw_weights_from_questions(questions_list, question_numbers_weights,
                                                      [target_pol, target_age, target_art], sample_size- 1)
        
        # Восстанавливаем target словари
        target_pol = original_target_pol.copy()
        target_age = original_target_age.copy()
        target_art = original_target_art.copy()

        # Восстанавливаем данные вопросов
        for q in questions_list:
            if q.id in original_data_columns:
                col_name = q.data.columns[0]
                q.data[col_name] = original_data_columns[q.id].copy()

    first_question = questions_list[0]
    total_rows = len(first_question.data)

    num_persons = total_rows - 2
    results_list = []
    try:
        if division is not None:
            dict_division, dict_weights  = division_df(questions_list, division, weights)
            for key in dict_division:
                questions_list = dict_division[key]
                weights = dict_weights[key]

                # Анализ вопросов
                if type_analyze == "standard":
                    result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons, weights, tr_number, roti_number)
                else:
                    target_division = None
                    if division in question_numbers_weights:
                        if division == question_numbers_weights[0]:
                            target_division = target_pol
                        elif division == question_numbers_weights[1]:
                            target_division = target_age
                        else:
                            target_division = target_art
                        result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, target_division[key]*sample_size, weights, tr_number, roti_number)
                    else:
                        result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, sample_size, weights, tr_number, roti_number)


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
                result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons, weights, tr_number, roti_number)
            else:
                result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, sample_size, weights, tr_number, roti_number)

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
            tr_list = [result.tr_frame for result in results_list if result.tr_frame is not None]
            roti_list = [result.roti_frame for result in results_list if result.roti_frame is not None]

            # объединяем каждый блок
            merged_data_frames = data_frames_list
            merged_free_answers = pd.concat(free_answers_list, ignore_index=True)
            merged_csi = pd.concat(csi_list, ignore_index=True)
            merged_nps = pd.concat(nps_list, ignore_index=True)
            merged_tr = pd.concat(tr_list, ignore_index=True)
            merged_roti = pd.concat(roti_list, ignore_index=True)

            result2 = AnalysisResult()

            result2.data_frames = merged_data_frames

            if result.free_answers_frame is not None:
                result2.free_answers_frame = merged_free_answers

            if csi_numbers:
                result2.csi_frame = merged_csi
            if nps_number:
                result2.nps_frame = merged_nps
            if tr_number:
                result2.tr_frame = merged_tr
            if roti_number:
                result2.roti_frame = merged_roti

            result = result2

        # Сохранение результатов
        if division is not None:
            result.to_excel_division(excel_path)
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

