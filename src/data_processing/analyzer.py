import pandas as pd
import re
from typing import List, Tuple, Dict, Optional, Any, Union
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
    list_of_persent = [round((x/summ)*100, 0) / 100 for x in args]
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
    str_pure: str = "Требует улучшений"
) -> Optional[Question]:
    """
    Обработка вопроса с шкалой
    
    Args:
        question: вопрос для обработки
        str_so_cool: текст для высокой оценки
        str_cool: текст для средней оценки
        str_pure: текст для низкой оценки
        
    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    so_cool = [0] * 2
    cool = [0] * 2
    pure = [0] * 2

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    # Удаляем мусорные слова
    for elem in config.trash_list:
        if elem in dic:
            del dic[elem]

    if not dic:
        return None

    # Проверка на тип данных в шкале
    for key in dic:
        if not isinstance(key, int):
            error_scale = AnalysisError(
                f"Ошибка при обработке вопроса шкалы. Шкала должна содержать только числовые показатели \nОшибка "
                f"произошла при обработке вопроса номер {question.id}")
            raise error_scale

    # Распределение по категориям в зависимости от шкалы
    if int(sorted(dic.keys())[-1]) > 5:
        for key in dic:
            if int(key) > 8:
                so_cool[0] += dic[key]
                continue
            if 9 > int(key) > 6:
                cool[0] += dic[key]
                continue
            if int(key) < 7:
                pure[0] += dic[key]
                continue
    else:
        for key in dic:
            if int(key) == 5:
                so_cool[0] += dic[key]
                continue
            if int(key) == 4:
                cool[0] += dic[key]
                continue
            if int(key) < 4:
                pure[0] += dic[key]
                continue

    # Расчет процентов
    so_cool[1], cool[1], pure[1] = round_persent(so_cool[0], cool[0], pure[0])

    # Создание DataFrame для каждой категории
    if so_cool[0] != 0:
        finals_dfs.append(
            create_typical_frame(question.id, question.name, question.name, str_so_cool, so_cool[0],
                                so_cool[1]))
    if cool[0] != 0:
        finals_dfs.append(
            create_typical_frame(question.id, question.name, question.name, str_cool,
                                cool[0], cool[1]))
    if pure[0] != 0:
        finals_dfs.append(
            create_typical_frame(question.id, question.name, question.name, str_pure,
                                pure[0], pure[1]))

    if len(finals_dfs) < 1:
        return None

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question


def single_selection(question: Question) -> Optional[Question]:
    """
    Обработка вопроса с одиночным выбором
    
    Args:
        question: вопрос для обработки
        
    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    # Удаляем мусорные слова
    for elem in config.trash_list:
        if elem in dic:
            del dic[elem]

    summ = 0
    tuple_procent = []

    for key in dic:
        summ += int(dic[key])
        tuple_procent.append(dic[key])

    tuple_procent = tuple(tuple_procent)

    if tuple_procent:
        tuple_procent = round_persent(*tuple_procent)

        j = 0
        for key in dic:
            if dic[key] != 0:
                finals_dfs.append(
                    create_typical_frame(question.id, question.name, question.name, key, dic[key],
                                        tuple_procent[j]))
            j += 1

    if len(finals_dfs) < 1:
        return None

    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question


def multiple_selection(question: Question, num_person: int) -> Optional[Question]:
    """
    Обработка вопроса с множественным выбором
    
    Args:
        question: вопрос для обработки
        num_person: количество участников
        
    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    # Удаляем мусорные слова
    for elem in config.trash_list:
        if elem in dic:
            del dic[elem]

    for key in dic:
        if key != "NaN":
            procent = round((dic[key] / num_person) * 100, 0) / 100
            finals_dfs.append(
                create_typical_frame(question.id, question.name, question.name, key, dic[key], procent))

    if len(finals_dfs) < 1:
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


def matrix(question: Question) -> Optional[Question]:
    """
    Обработка вопроса с матрицей
    
    Args:
        question: вопрос для обработки
        
    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    matrix_scale = question.data.iloc[0]

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    if len(dic) < 1:
        return None

    if is_scale(dic):
        final_df = scale(question)
    else:
        final_df = single_selection(question)

    if final_df is None:
        return None

    final_df = final_df.data

    final_df['Шкала'] = matrix_scale

    finals_dfs.append(final_df)

    if len(finals_dfs) < 1:
        return None
    question.data = pd.concat(finals_dfs, ignore_index=True)
    return question


def matrix_3d(question: Question) -> Optional[Question]:
    """
    Обработка вопроса с 3D матрицей
    
    Args:
        question: вопрос для обработки
        
    Returns:
        Обработанный вопрос или None если нет данных
    """
    finals_dfs = []

    question.name = question.data.iloc[0]

    matrix_scale = question.data.iloc[1]

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    if len(dic) < 1:
        return None

    if is_scale(dic):
        final_df = scale(question)
    else:
        final_df = single_selection(question)

    if final_df is None:
        return None

    final_df = final_df.data

    final_df['Шкала'] = matrix_scale

    finals_dfs.append(final_df)

    if len(finals_dfs) < 1:
        return None
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
    answers = question.data.iloc[2:]

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


def nps_quest(question: Question) -> pd.DataFrame:
    """
    Обработка NPS вопроса
    
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

    so_cool = 0
    cool = 0
    pure = 0

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()
    if sorted(dic.keys())[-1] > 5:
        for key in dic:
            if int(key) > 8:
                so_cool += dic[key]
                continue
            if 9 > int(key) > 6:
                cool += dic[key]
                continue
            if int(key) < 7:
                pure += dic[key]
                continue

    num = so_cool + cool + pure

    so_cool_precent = so_cool / num if num > 0 else 0
    cool_precent = cool / num if num > 0 else 0
    pure_precent = pure / num if num > 0 else 0
    result_procent = (so_cool - pure) / num if num > 0 else 0

    nps_df["Количество"] = [so_cool, cool, pure, ""]
    nps_df["Процент"] = [so_cool_precent, cool_precent, pure_precent, result_procent]

    return pd.DataFrame(nps_df)


def csi_quest(question: Question) -> float:
    """
    Обработка CSI вопроса
    
    Args:
        question: вопрос для обработки
        
    Returns:
        Среднее значение ответов
    """
    average = float(question.data[2:].mean())
    return average


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
    num_person: int = 1
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

            result.nps_frame = nps_quest(question)
            continue

        # Обработка CSI вопросов
        if csi and question.id in csi:
            if question.type != "Матрица" and question.type != "Матрица 3D":
                error_csi = AnalysisError(
                    f"Ошибка в выборе номера вопросов CSI. CSI всегда является Матрицей "
                    f"или Матрицей 3D \nОшибка произошла при обработке вопроса номер {question.id}")
                raise error_csi

            criterion = question.data.iloc[0]

            if criterion in csi_pre:
                csi_pre[criterion].append(csi_quest(question))
            else:
                csi_pre[criterion] = [csi_quest(question)]
            continue

        # Обработка шкалы
        if question.type == "Шкала":
            if mood and mood == question.id:
                final_question = scale(question, "Отличное", "Хорошее", "Требует улучшений")
            else:
                final_question = scale(question)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка одиночного выбора
        elif question.type == "Одиночный выбор":
            final_question = single_selection(question)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка матрицы
        elif question.type == "Матрица":
            final_question = matrix(question)

            if final_question is not None:
                result.data_frames.append(final_question.data)
            continue

        # Обработка 3D матрицы
        elif question.type == "Матрица 3D":
            final_question = matrix_3d(question)

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
            question.name = question.data.iloc[0]
            free_question_group = free_answer(question)
            free_answers.append(free_question_group)
            continue

        # Обработка множественного выбора
        elif (question.type == "Множественный выбор" or question.type == "Выпадающий список"
              or question.type == "Выбор области" or question.type == "Множественный выпадающий список"):
            final_question = multiple_selection(question, num_person)

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