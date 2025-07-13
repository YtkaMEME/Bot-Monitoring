import pandas as pd
import re
from typing import List, Tuple, Dict, Optional, Union
from .models import Question, AnalysisError, AnalysisResult
import sys
import os

# Добавление корневого каталога проекта в путь импорта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from config.config import config


def no_repet_persent_index(list_of_persent: List[float]) -> int:
    """
    Выбор индекса для корректировки процентов

    Args:
        list_of_persent: список процентов

    Returns:
        Индекс для корректировки
    """
    if len(list_of_persent) == 1:
        return 0

    start = 0
    current_index = 1

    while start != len(list_of_persent):
        if current_index == len(list_of_persent) - 1 and list_of_persent[current_index] != list_of_persent[start]:
            return start

        if list_of_persent[current_index] == list_of_persent[start]:
            start += 1
            current_index = 0

        current_index += 1

    return 0


def round_persent(*args: int) -> Tuple[float, ...]:
    """
    Округление процентов с учетом их суммы в 100%

    Args:
        *args: Количества для каждой категории

    Returns:
        Кортеж процентов для каждой категории
    """
    if len(args) == 0:
        return tuple([0])

    summ = sum(args)
    list_of_persent = [round((x / summ) * 100, 0) / 100 for x in args]
    persent_summ = round(sum(list_of_persent), 2)

    index_no_repet_persent = no_repet_persent_index(list_of_persent)

    if persent_summ > 1:
        list_of_persent[index_no_repet_persent] -= 0.01
    elif persent_summ < 1:
        list_of_persent[index_no_repet_persent] += 0.01

    return tuple(list_of_persent)


def create_typical_frame(
        number: str,
        name: str,
        scale_l: str,
        grade: Union[str, int],
        quantity: int,
        percent: float
) -> pd.DataFrame:
    """
    Создание типичного фрейма

    Args:
        number: номер вопроса
        name: название вопроса
        scale_l: шкала
        grade: оценка
        quantity: количество
        percent: процент

    Returns:
        DataFrame с данными
    """
    final_df = {
        "Номер вопроса": [number],
        "Вопрос": [name],
        "Шкала": [scale_l],
        "Оценка": [grade],
        "Количество": [quantity],
        "Процент": [percent]
    }

    return pd.DataFrame(final_df)


def scale(
        question: Question,
        str_so_cool: str = "Идеально",
        str_cool: str = "Нормально",
        str_pure: str = "Требует улучшений",
        weights = None
) -> Optional[Question]:
    """
    Обработка вопроса с шкалой (с учетом весов).

    Args:
        question: вопрос для обработки
        str_so_cool: текст для высокой оценки
        str_cool: текст для средней оценки
        str_pure: текст для низкой оценки

    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []
    values = question.data['value'].iloc[2:].reset_index(drop=True)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)
    # Очищаем от NaN и строим таблицу
    df = pd.DataFrame({'value': values, 'weight': weights}).dropna()

    # Пробуем привести значения к числам
    def safe_int(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    df['value'] = df['value'].apply(safe_int)
    df = df.dropna(subset=['value'])

    # После очистки — если данных нет, сразу выходим
    if df.empty:
        return None

    grouped = df.groupby('value')['weight'].sum().to_dict()

    for elem in config.trash_list:
        if elem in grouped:
            del grouped[elem]

    if not grouped:
        return None

    max_scale = max(grouped.keys())

    so_cool, cool, pure = 0, 0, 0

    for val, weight_sum in grouped.items():
        if max_scale > 5:
            if val > 8:
                so_cool += weight_sum
            elif 7 <= val <= 8:
                cool += weight_sum
            else:
                pure += weight_sum
        else:
            if val == 5:
                so_cool += weight_sum
            elif val == 4:
                cool += weight_sum
            else:
                pure += weight_sum

    total = so_cool + cool + pure

    if total == 0:
        return None

    # нормализуем проценты в твоей старой логике
    so_cool_p, cool_p, pure_p = round_persent(so_cool, cool, pure)

    # Создаём итоговые блоки
    if so_cool > 0:
        finals_dfs.append(create_typical_frame(question.id, question.name, question.name, str_so_cool, round(so_cool, 2), so_cool_p))
    if cool > 0:
        finals_dfs.append(create_typical_frame(question.id, question.name, question.name, str_cool, round(cool, 2), cool_p))
    if pure > 0:
        finals_dfs.append(create_typical_frame(question.id, question.name, question.name, str_pure, round(pure, 2), pure_p))

    if not finals_dfs:
        return None

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question


def single_selection(question: Question, weights) -> Optional[Question]:
    """
    Обработка вопроса с одиночным выбором (с учетом весов).

    Args:
        question: вопрос для обработки

    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    values = question.data['value'].iloc[2:].reset_index(drop=True)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)

    df = pd.DataFrame({'value': values, 'weight': weights}).dropna()

    # Группировка с учетом весов
    grouped = df.groupby('value')['weight'].sum().to_dict()

    # Удаляем мусорные слова
    for trash in config.trash_list:
        if trash in grouped:
            del grouped[trash]

    total_weight = sum(grouped.values())

    for key, weight_sum in grouped.items():
        percent = round((weight_sum / total_weight) * 100, 2) if total_weight > 0 else 0
        finals_dfs.append(
            create_typical_frame(question.id, question.name, question.name, key, round(weight_sum, 2), percent / 100)
        )

    if not finals_dfs:
        return None

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question

def multiple_selection(question: Question, num_person, weights) -> Optional[Question]:
    """
    Обработка вопроса с множественным выбором (с учетом весов)

    Args:
        question: вопрос для обработки

    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    values = question.data['value'].iloc[2:].reset_index(drop=True)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)


    # Собираем DataFrame
    df = pd.DataFrame({'value': values, 'weight': weights})
    df = df.dropna()

    # Суммируем веса по каждому уникальному ответу
    grouped = df.groupby('value')['weight'].sum().to_dict()

    # Удаляем мусор
    for trash in config.trash_list:
        if trash in grouped:
            del grouped[trash]

    total_weight = sum(grouped.values())

    for key, count_weight in grouped.items():
        percent = round((count_weight / num_person) * 100, 2) if total_weight > 0 else 0
        finals_dfs.append(
            create_typical_frame(question.id, question.name, question.name, key, count_weight, percent / 100)
        )

    if not finals_dfs:
        return None

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question

def is_scale(dic: Dict) -> bool:
    """
    Определение является ли вопрос шкалой

    Args:
        dic: словарь с ответами

    Returns:
        True если вопрос является шкалой
    """
    for key in dic.keys():
        if isinstance(key, int):
            return True

    return False


def matrix(question: Question, weights) -> Optional[Question]:
    """
    Обработка вопроса с матрицей (универсальная — с учетом весов).

    Args:
        question: вопрос для обработки

    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    # Первая строка — это шкала внутри матрицы
    matrix_scale = question.data['value'].iloc[0]

    # Оставляем только фактические ответы
    values = question.data['value'].iloc[2:].reset_index(drop=True)
    weights_copy = weights['ones'].iloc[2:].reset_index(drop=True)
    df = pd.DataFrame({'value': values, 'weight': weights_copy}).dropna()

    if df.empty:
        return None

    # Проверяем является ли шкалой
    def safe_int(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    df['int_value'] = df['value'].apply(safe_int)

    if df['int_value'].dropna().empty:
        # считаем это одиночным выбором
        final_question = single_selection(question, weights)
    else:
        # для шкальных — заменяем value на int_value
        question.data = pd.DataFrame({
            'value': df['int_value'],
            'weighted': df['weight']
        })

        final_question = scale(question, weights=weights)

    if final_question is None:
        return None

    final_df = final_question.data
    final_df['Шкала'] = matrix_scale

    finals_dfs.append(final_df)

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question

def matrix_3d(question: Question, weights) -> Optional[Question]:
    """
    Обработка вопроса с 3D матрицей (универсальная — с учетом весов)

    Args:
        question: вопрос для обработки

    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    # Первые две строки — название и шкала
    question.name = question.data['value'].iloc[0]
    matrix_scale = question.data['value'].iloc[1]

    # Оставляем только ответы
    values = question.data['value'].iloc[2:].reset_index(drop=True)
    df = pd.DataFrame({'value': values}).dropna()

    if df.empty:
        return None

    # Проверяем тип шкалы
    def safe_int(val):
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    df['int_value'] = df['value'].apply(safe_int)

    if df['int_value'].dropna().empty:
        # одиночный выбор
        final_question = single_selection(question, weights=weights)
    else:
        # шкала
        question.data = pd.DataFrame({
            'value': df['int_value']})
        final_question = scale(question, weights=weights)

    if final_question is None:
        return None

    final_df = final_question.data
    final_df['Шкала'] = matrix_scale

    finals_dfs.append(final_df)

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question

def capitalize_after_punctuation(text: str) -> str:
    """
    Преобразование текста с заглавной буквой после пунктуации

    Args:
        text: исходный текст

    Returns:
        Преобразованный текст
    """

    def capitalize(match):
        before = match.group(1)
        after = match.group(2)

        return before + after.upper()

    pattern = re.compile(r'([.!?]\s*)(\S)')
    return pattern.sub(capitalize, text)


def free_answer(question: Question) -> Tuple[str, List[str]]:
    """
    Обработка вопроса со свободным ответом

    Args:
        question: вопрос для обработки

    Returns:
        Кортеж с названием вопроса и списком ответов
    """
    result = [question.name, []]
    answers = question.data["value"].iloc[2:]

    for answer in answers:
        answer = str(answer)
        word_count = len(answer.split(" "))

        if word_count < 2:
            continue

        answer = answer.lower()
        answer = capitalize_after_punctuation(answer)
        if answer[-1] == ".":
            answer = answer[:-1]

        answer = f'«{answer[0].upper() + answer[1:]}»'
        result[1].append(answer)
    return result

def nps_quest(question: Question, weights) -> pd.DataFrame:
    """
    Обработка NPS вопроса с учетом весов.

    Args:
        question: вопрос для обработки

    Returns:
        DataFrame с результатами NPS
    """
    nps_df = {
        "Шкала": ["Приверженцы", "Нейтралы", "Критики", ""],
        "Количество": [],
        "Процент": []
    }

    values = question.data['value'].iloc[2:].astype(float).reset_index(drop=True)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)


    # Проверка какой тип шкалы (5-бальная или 10-бальная)
    max_value = values.max()

    so_cool = 0
    cool = 0
    pure = 0

    for val, weight in zip(values, weights):
        if max_value > 5:
            if val > 8:
                so_cool += weight
            elif 9 > val > 6:
                cool += weight
            elif val <= 6:
                pure += weight
        else:
            if val == 5:
                so_cool += weight
            elif val == 4:
                cool += weight
            elif val < 4:
                pure += weight

    total_weight = so_cool + cool + pure

    so_cool_precent = so_cool / total_weight if total_weight > 0 else 0
    cool_precent = cool / total_weight if total_weight > 0 else 0
    pure_precent = pure / total_weight if total_weight > 0 else 0
    result_procent = (so_cool - pure) / total_weight if total_weight > 0 else 0

    nps_df["Количество"] = [round(so_cool, 2), round(cool, 2), round(pure, 2), ""]
    nps_df["Процент"] = [so_cool_precent, cool_precent, pure_precent, result_procent]

    return pd.DataFrame(nps_df)

def tr_quest(question: Union[pd.DataFrame, "Question"], weights: pd.DataFrame) -> pd.DataFrame:
    """
    Обработка TR (достижение цели) с учетом весов.

    Args:
        question: объект с данными вопроса (должен содержать колонку 'value')
        weights: DataFrame с весами, колонка 'ones'

    Returns:
        DataFrame с результатами TR
    """
    tr_df = {
        "Категория": ["Достигли цели", "Не достигли", "TR (%)"],
        "Количество": [],
        "Процент": []
    }

    values = question.data['value'].iloc[2:].reset_index(drop=True).astype(str).str.strip()
    weights = weights['ones'].iloc[2:].reset_index(drop=True)

    reached = 0
    not_reached = 0

    for val, weight in zip(values, weights):
        if val.lower() == "да":
            reached += weight
        elif val.lower() == "нет":
            not_reached += weight

    total = reached + not_reached
    tr_percent = (reached / total) if total > 0 else 0

    tr_df["Количество"] = [round(reached, 2), round(not_reached, 2), ""]
    tr_df["Процент"] = [
        round(reached / total, 2) if total > 0 else 0,
        round(not_reached / total, 2) if total > 0 else 0,
        tr_percent
    ]

    return pd.DataFrame(tr_df)

def roti_quest(question: Union[pd.DataFrame, "Question"], weights: pd.DataFrame) -> pd.DataFrame:
    """
    Расчёт ROTI (Return on Time Invested) с учётом весов.

    Args:
        question: объект с данными вопроса (с колонкой 'value')
        weights: DataFrame с весами (с колонкой 'ones')

    Returns:
        DataFrame с частотным распределением, средним значением и ROTI
    """
    roti_df = {
        "Оценка": [],
        "Количество": [],
        "Процент": []
    }

    values = question.data['value'].iloc[2:].reset_index(drop=True).astype(float)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)

    score_counts = {i: 0 for i in range(1, 6)}
    total_weight = 0
    weighted_sum = 0

    for val, weight in zip(values, weights):
        val_int = int(round(val))
        if 1 <= val_int <= 5:
            score_counts[val_int] += weight
            if val_int == 4 or val_int == 5:
                weighted_sum += 1 * weight
            total_weight += 1 * weight

    for score in range(1, 6):
        count = score_counts[score]
        percent = (count / total_weight) if total_weight > 0 else 0
        roti_df["Оценка"].append(str(score))
        roti_df["Количество"].append(round(count, 2))
        roti_df["Процент"].append(round(percent, 2))

    average_score = weighted_sum / total_weight if total_weight > 0 else 0
    roti_df["Оценка"].append("Среднее ROTI")
    roti_df["Количество"].append("")
    roti_df["Процент"].append(average_score)

    return pd.DataFrame(roti_df)

def csi_quest(question: Question, weights) -> float:
    """
    Обработка CSI вопроса с учетом весов.

    Args:
        question: вопрос для обработки

    Returns:
        Средневзвешенное значение ответов
    """
    values = question.data['value'].iloc[2:].astype(float).reset_index(drop=True)
    weights = weights['ones'].iloc[2:].reset_index(drop=True)


    weighted_sum = (values * weights).sum()
    total_weight = weights.sum()

    if total_weight == 0:
        return 0.0

    average = weighted_sum / total_weight
    return round(float(average), 4)

def create_csi_df(csi_dic: Dict[str, List[float]]) -> pd.DataFrame:
    """
    Создание DataFrame для CSI

    Args:
        csi_dic: словарь с данными CSI

    Returns:
        DataFrame с результатами CSI
    """
    csi_df = {
        "Параметр": [],
        "Важность параметра": [],
        "Оценка параметра": [],
        "CSI по параметру": []
    }

    num = []

    for key in csi_dic.keys():
        csi_df["Параметр"].append(key)

        important = round(csi_dic[key][0], 2)
        csi_df["Важность параметра"].append(important)

        grade = round(csi_dic[key][1], 2)
        csi_df["Оценка параметра"].append(grade)

        csi_param = float(round(csi_dic[key][1] * csi_dic[key][0], 2))
        csi_df["CSI по параметру"].append(csi_param)

        num.append(csi_dic[key][1] * csi_dic[key][0])

    average = round(float(sum(num)) / len(num), 2) if num else 0

    csi_df["Параметр"].append("Итого:")
    csi_df["Важность параметра"].append("")
    csi_df["Оценка параметра"].append("")
    csi_df["CSI по параметру"].append(average)

    return pd.DataFrame(csi_df)

def analyze_questions(
        questions_list: List[Question],
        mood: Optional[int] = None,
        nps: Optional[int] = None,
        csi: Optional[List[int]] = None,
        num_person: int = 1,
        weights = None,
        tr: Optional[int] = None,
        roti: Optional[int] = None
) -> AnalysisResult:
    """
    Анализ вопросов из анкеты

    Args:
        questions_list: список вопросов
        mood: номер вопроса о настроении
        nps: номер вопроса NPS
        csi: номера вопросов CSI
        num_person: количество участников

    Returns:
        Результат анализа
    """
    skip_quest = ["Матрица свободных ответов", "Имя", "Дата", "Email", "Телефон", "Загрузка файла"]
    result = AnalysisResult()
    csi_pre = {}

    free_answers = []

    # Преобразуем номера вопросов в ID
    if mood:
        mood = f"D1_{mood}"

    if nps:
        nps = f"D1_{nps}"

    if tr:
        tr = f"D1_{tr}"

    if roti:
        roti = f"D1_{roti}"

    if csi:
        if len(csi) == 2:
            csi = [f"D1_{csi[0]}", f"D1_{csi[1]}"]
        else:
            csi = [f"D1_{csi[0]}"]

    for question in questions_list:
        # Обработка NPS вопроса
        if nps and nps == question.id:
            if question.type != "Шкала" and question.type != "Выпадающий список":
                error_nps = AnalysisError(
                    f"Ошибка в выборе номера вопроса NPS. NPS вcегда является Шкалой или Выпадающим списком!"
                    f"\nОшибка произошла при обработке вопроса номер {question.id}")
                raise error_nps

            result.nps_frame = nps_quest(question, weights)
            continue

        if tr and tr == question.id:
            if question.type != "Одиночный выбор":
                error_nps = AnalysisError(
                    f"Ошибка в выборе номера вопроса TR. TR вcегда является Одиночным выбором!"
                    f"\nОшибка произошла при обработке вопроса номер {question.id}")
                raise error_nps

            result.tr_frame = tr_quest(question, weights)
            continue
        
        if roti and roti == question.id:
            if question.type != "Шкала":
                error_nps = AnalysisError(
                    f"Ошибка в выборе номера вопроса ROTI. ROTI вcегда является Одиночным выбором!"
                    f"\nОшибка произошла при обработке вопроса номер {question.id}")
                raise error_nps

            result.roti_frame = roti_quest(question, weights)
            continue
              

        # Обработка CSI вопросов
        if csi and question.id in csi:
            if question.type != "Матрица" and question.type != "Матрица 3D":
                error_csi = AnalysisError(
                    f"Ошибка в выборе номера вопросов CSI. CSI всегда является Матрицей "
                    f"или Матрицей 3D \nОшибка произошла при обработке вопроса номер {question.id}")
                raise error_csi

            criterion = question.data['value'].iloc[0]

            if criterion in csi_pre:
                csi_pre[criterion].append(csi_quest(question, weights))
            else:
                csi_pre[criterion] = [csi_quest(question, weights)]
            continue

        # Обработка шкалы
        if question.type == "Шкала":
            if mood and mood == question.id:
                final_question = scale(question, "Отличное", "Хорошее", "Плохое", weights)
            else:
                final_question = scale(question, weights=weights)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка одиночного выбора
        elif question.type == "Одиночный выбор":
            final_question = single_selection(question, weights)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка матрицы
        elif question.type == "Матрица":
            final_question = matrix(question, weights)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка 3D матрицы
        elif question.type == "Матрица 3D":
            final_question = matrix_3d(question, weights)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка свободного ответа
        elif question.type == "Свободный ответ":
            free_question = free_answer(question)
            free_answers.append(free_question)
            continue

        # Пропуск специальных типов вопросов
        elif question.type in skip_quest:
            result.skipped_questions += f"\n {question.id} {question.type}: {question.name}"
            continue

        # Обработка группы свободных ответов
        elif question.type == "Группа свободных ответов":
            question.name = question.data["value"].iloc[0]
            free_question_group = free_answer(question)
            free_answers.append(free_question_group)
            continue

        # Обработка множественного выбора
        elif (question.type == "Множественный выбор" or question.type == "Выпадающий список"
              or question.type == "Выбор области" or question.type == "Множественный выпадающий список"):
            final_question = multiple_selection(question, num_person, weights)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue
        else:
            error_quest = AnalysisError(
                f"Есть проблемка...\n"
                f"Я не знаю такой тип вопроса как \"{question.type}\""
                f"\nОшибка произошла при обработке вопроса номер {question.id}")
            raise error_quest

    # Создание CSI фрейма
    if csi and csi_pre:
        result.csi_frame = create_csi_df(csi_pre)

    # Создание фрейма свободных ответов
    free_answers_df = {
        "Вопрос": [],
        "Ответ": []
    }

    for answer in free_answers:
        free_answers_df["Вопрос"].append(answer[0])
        free_answers_df["Ответ"].append("\n".join(answer[1]))

    if free_answers_df["Вопрос"]:
        result.free_answers_frame = pd.DataFrame(free_answers_df)

    return result 