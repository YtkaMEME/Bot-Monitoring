import os
from typing import Tuple, Optional, List, Any

import pandas as pd
from aiogram.types import Message

from .calculate_targets import fetch_form_data, save_calculation_results,   calculate_raw_weights_from_questions
from .file_processor import read_file, table_validation, create_questions_list
from .analyzer import analyze_questions
from .models import AnalysisError, AnalysisResult
from .prepare_target_distributions import prepare_target_distributions
from src.utils.cleaner import clean_dict_keys, clean_text
from src.utils.division_df import division_df, multi_division_df, process_result_with_divider

def extract_group_label(key: str, field: str) -> str:
    """
    Извлекает значение разделителя (например, «Женщины») из строки ключа,
    в которой содержится подстрока вида 'Пол=Женщины | Возраст=18-25'

    Args:
        key: строка с форматированными разделителями (например, 'Пол=Женщины | Возраст=18-25')
        field: нужное поле (например, 'Пол')

    Returns:
        Значение поля (например, 'Женщины'), либо '' если не найдено
    """
    for part in key.split(" | "):
        if part.startswith(f"{field}="):
            return part.replace(f"{field}=", "")
    return ""

async def process_data(
    path: str,
    mood_number: Optional[int] = None,
    nps_number: Optional[List[int]] = None,
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
        nps_number: номера вопросов NPS
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
    summary_text = ""
    try:
        results_list = []

        if division is not None:

            # Множественное или одиночное деление
            if len(division) == 1:
                dict_division, dict_weights = division_df(questions_list, division[0], weights)

                target_division = None
                if type_analyze != "standard" and division[0] in question_numbers_weights:
                    if division[0] == question_numbers_weights[0]:
                        target_division = target_pol
                    elif division[0] == question_numbers_weights[1]:
                        target_division = target_age
                    else:
                        target_division = target_art
                for key in dict_division:
                    q_list = dict_division[key]
                    w_list = dict_weights[key]
                    first_question = q_list[0]
                    total_rows = len(first_question.data) - 2
                    print(total_rows)
                    num = (target_division[key] * sample_size) if target_division else sample_size if type_analyze != "standard" else total_rows

                    result = analyze_questions(q_list, mood_number, nps_number, csi_numbers, num, w_list, tr_number, roti_number)
                    result = process_result_with_divider(result, key)
                    results_list.append(result)

            else:
                division_results = multi_division_df(questions_list, weights, division)

                for key, (q_list, w_list) in division_results.items():
                    # Определяем нужный target_division
                    target_division = None
                    if type_analyze != "standard" and any(d in question_numbers_weights for d in division):
                        if division[0] == question_numbers_weights[0]:
                            target_division = target_pol
                        elif division[0] == question_numbers_weights[1]:
                            target_division = target_age
                        else:
                            target_division = target_art

                    if target_division:
                        group_label = extract_group_label(key, division[0])
                        num = target_division.get(group_label, 0) * sample_size
                    else:
                        num = sample_size if type_analyze != "standard" else num_persons

                    result = analyze_questions(q_list, mood_number, nps_number, csi_numbers, num, w_list, tr_number, roti_number)
                    result = process_result_with_divider(result, key)
                    results_list.append(result)

            num_standart = num_persons if type_analyze == "standard" else sample_size
            result_standart = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_standart, weights, tr_number, roti_number)
            results_list.append(process_result_with_divider(result_standart, "Общее"))

            # Объединение результатов
            merged_data_frames = []
            for r in results_list:
                df_block = r.data_frames if isinstance(r.data_frames, list) else [r.data_frames]
                merged_data_frames.extend(df_block)

            result2 = AnalysisResult()
            result2.data_frames = merged_data_frames

            if any(r.free_answers_frame is not None for r in results_list):
                result2.free_answers_frame = pd.concat(
                    [r.free_answers_frame for r in results_list if r.free_answers_frame is not None],
                    ignore_index=True
                )

            if csi_numbers:
                result2.csi_frame = pd.concat([r.csi_frame for r in results_list if r.csi_frame is not None], ignore_index=True)
            if nps_number:
                result2.nps_frame = pd.concat([r.nps_frame for r in results_list if r.nps_frame is not None], ignore_index=True)
            if tr_number:
                result2.tr_frame = pd.concat([r.tr_frame for r in results_list if r.tr_frame is not None], ignore_index=True)
            if roti_number:
                result2.roti_frame = pd.concat([r.roti_frame for r in results_list if r.roti_frame is not None], ignore_index=True)

            result = result2
        else:
            num = num_persons if type_analyze == "standard" else sample_size
            result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num, weights, tr_number, roti_number)

        # Сохраняем результат
        if division is not None:
            result.to_excel_division(excel_path)
        else:
            result.to_excel(excel_path)
        result.to_csv(csv_path)

        if message:
            if result.skipped_questions:
                await message.answer(f"Были пропущены следующие вопросы{result.skipped_questions}")
            summary_text = result.build_summary()
            if summary_text:
                await message.answer(summary_text)

    except AnalysisError as e:
        if message:
            await message.answer(f"{e}")
        if os.path.exists(path):
            os.remove(path)
        raise

    except Exception as e:
        if message:
            await message.answer("Произошла какая-то ошибка 😿\nНо ведь у меня лапки🐾")
        if os.path.exists(path):
            os.remove(path)
        raise
    
    return excel_path, csv_path

