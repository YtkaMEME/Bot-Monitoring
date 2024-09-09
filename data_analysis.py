import pandas as pd
import re
import help_file


class AnalysisError(Exception):
    pass


def no_repet_persent_index(list_of_persent):
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


def round_persent(*args):
    if len(args) == 0:
        return 0

    summ = sum(args)
    list_of_persent = [round((x/summ)*100, 0) / 100 for x in args]
    persent_summ = round(sum(list_of_persent), 2)

    index_no_repet_persent = no_repet_persent_index(list_of_persent)

    if persent_summ > 1:
        list_of_persent[index_no_repet_persent] -= 0.01
    elif persent_summ < 1:
        list_of_persent[index_no_repet_persent] += 0.01

    return tuple(list_of_persent)


# Создание типичного фрэйма
def create_typical_frame(number, name, scale_l, grade, quantity, percent):
    final_df = {
        "Номер вопроса": [],
        "Вопрос": [],
        "Шкала": [],
        "Оценка": [],
        "Количество": [],
        "Процент": []
    }

    final_df["Номер вопроса"].append(number)
    final_df["Вопрос"].append(name)
    final_df["Шкала"].append(scale_l)
    final_df["Оценка"].append(grade)
    final_df["Количество"].append(quantity)
    final_df["Процент"].append(percent)

    return pd.DataFrame(final_df)


# Шкала
def scale(question, str_so_cool="Очень понравилось", str_cool="Понравилось, но можно лучше",
          str_pure="Совсем не понравилось"):
    finals_dfs = []

    so_cool = [0] * 2
    cool = [0] * 2
    pure = [0] * 2

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    str_to_del = help_file.get_trash_list()

    for elem in str_to_del:
        if elem in dic:
            del dic[elem]

    if not dic:
        return None

    # Выдача исключения
    for key in dic:
        if not isinstance(key, int):
            error_scale = AnalysisError(
                f"Ошибка при обработке вопроса шкалы. Шкала должна содержать только числовые показатели \nОшибка "
                f"произошла при обработке вопроса номер {question.id}")
            raise error_scale

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

    so_cool[1], cool[1], pure[1] = round_persent(so_cool[0], cool[0], pure[0])

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


# Одиночный выбор
def single_selection(question):
    finals_dfs = []

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    str_to_del = help_file.get_trash_list()

    for elem in str_to_del:
        if elem in dic:
            del dic[elem]

    summ = 0
    tuple_procent = []

    for key in dic:
        summ += int(dic[key])
        tuple_procent.append(dic[key])

    tuple_procent = tuple(tuple_procent)

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


# Множественный выбор
def multiple_selection(question, num_person):
    finals_dfs = []

    count_result = question.data.iloc[2:].value_counts()
    dic = count_result.to_dict()

    str_to_del = help_file.get_trash_list()

    for elem in str_to_del:
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


# Подобен ли вопрос шкале
def is_scale(dic):
    for key in dic.keys():
        if isinstance(key, int):
            return True

    return False


# Матрица
def matrix(question):
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


# 3D Матрица
def matrix_3d(question):
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


# Список сокращений
abbreviations = ["др.", "пр.", "т. п.", "т. д.", "т. е.", "т. к.", "т.п.", "т.д.", "т.е.", "т.к."]


def capitalize_after_punctuation(text):
    def capitalize(match):
        before = match.group(1)
        after = match.group(2)

        return before + after.upper()

    pattern = re.compile(r'([.!?]\s*)(\S)')
    return pattern.sub(capitalize, text)


# Свободный ответ
def free_answer(question):
    result = [question.name, []]
    answers = question.data.iloc[2:]

    for answer in answers:
        answer = str(answer)
        word_count = len(answer.split(" "))

        if word_count < 2:
            continue

        answer = answer.lower()
        answer = capitalize_after_punctuation(answer)
        answer = f'«{answer[0].upper() + answer[1:]}»'

        result[1].append(answer)

    return result


# NPS
def nps_quest(question):
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

    so_cool_precent = so_cool / num
    cool_precent = cool / num
    pure_precent = pure / num
    result_procent = (so_cool - pure) / num

    nps_df["Количество"] = [so_cool, cool, pure, ""]
    nps_df["Процент"] = [so_cool_precent, cool_precent, pure_precent, result_procent]

    return pd.DataFrame(nps_df)


# Обработчик CSI
def csi_quest(question):
    average = float(question.data[2:].mean())

    return average


# CSI DataFrame
def create_csi_df(csi_dic):
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

    average = round(float(sum(num)) / len(num), 2)

    csi_df["Параметр"].append("Итого:")
    csi_df["Важность параметра"].append("")
    csi_df["Оценка параметра"].append("")
    csi_df["CSI по параметру"].append(average)

    return pd.DataFrame(csi_df)


# Валидирование вопросов
def questions_validation(questions_list, mood=False, nps=False, csi=False, num_person=1):
    skip_quest = ["Матрица свободных ответов", "Имя", "Дата", "Email", "Телефон", "Загрузка файла"]
    answer_for_user = ""
    final_data_list = []
    nps_df = pd.DataFrame({})
    free_answers_df = {
        "Вопрос": [],
        "Ответ": []
    }
    csi_pre = {}

    free_answers = []

    if mood:
        mood = f"D1_{mood}"

    if nps:
        nps = f"D1_{nps}"

    if csi:
        if len(questions_list) < csi[1]:
            if questions_list[csi[1]].type != "Матрица 3D" and questions_list[csi[0]].type != "Матрица 3D":
                csi = [f"D1_{csi[0]}"]
            else:
                csi = [f"D1_{csi[0]}", f"D1_{csi[1]}"]
        else:
            csi = [f"D1_{csi[0]}", f"D1_{csi[1]}"]

    for question in questions_list:

        if nps:
            if nps == question.id:
                # Выдача исключения
                if question.type != "Шкала" and question.type != "Выпадающий список":
                    error_nps = AnalysisError(
                        f"Ошибка в выборе номера вопроса NPS. NPS вcегда является Шкалой или Выпадающим списком!"
                        f"\nОшибка "
                        f"произошла при обработке вопроса номер {question.id}")
                    raise error_nps

                nps_df = nps_quest(question)
                continue

        if csi:
            if question.id in csi:
                # Выдача исключения
                if question.type != "Матрица" and question.type != "Матрица 3D":
                    error_csi = AnalysisError(f"Ошибка в выборе номера вопросов CSI. CSI всегда является Матрицей "
                                              f"или Матрицей 3D \nОшибка "
                                              f"произошла при обработке вопроса номер {question.id}")
                    raise error_csi

                criterion = question.data.iloc[0]

                if criterion in csi_pre:
                    csi_pre[criterion].append(csi_quest(question))
                else:
                    csi_pre[criterion] = [csi_quest(question)]
                continue

        if question.type == "Шкала":
            if mood == question.id:
                final_question = scale(question, "Отличное", "Хорошее", "Плохое")
            else:
                final_question = scale(question)

            if final_question is not None:
                final_data_list.append(final_question.data)
            continue

        elif question.type == "Одиночный выбор":
            final_question = single_selection(question)

            if final_question is not None:
                final_data_list.append(final_question.data)
            continue

        elif question.type == "Матрица":
            final_question = matrix(question)

            if final_question is not None:
                final_data_list.append(final_question.data)
            continue

        elif question.type == "Матрица 3D":
            final_question = matrix_3d(question)

            if final_question is not None:
                final_data_list.append(final_question.data)
            continue

        elif question.type == "Свободный ответ":
            free_question = free_answer(question)
            free_answers.append(free_question)
            continue

        elif question.type in skip_quest:
            answer_for_user = f"{answer_for_user}\n {question.id} {question.type}: {question.name}"
            continue

        elif question.type == "Группа свободных ответов":
            question.name = question.data.iloc[0]
            free_question_group = free_answer(question)
            free_answers.append(free_question_group)
            continue

        elif (question.type == "Множественный выбор" or question.type == "Выпадающий список"
              or question.type == "Выбор области" or question.type == "Множественный выпадающий список"):
            final_question = multiple_selection(question, num_person)

            if final_question is not None:
                final_data_list.append(final_question.data)
            continue
        else:
            error_quest = AnalysisError(f"Есть проблемка...\n"
                                        f"Я не знаю такой тип вопроса как \"{question.type}\""
                                        f"\nОшибка "
                                        f"произошла при обработке вопроса номер {question.id}")
            raise error_quest

    if csi:
        csi_pre = create_csi_df(csi_pre)
    else:
        csi_pre = pd.DataFrame({})

    for answer in free_answers:
        free_answers_df["Вопрос"].append(answer[0])
        free_answers_df["Ответ"].append("\n".join(answer[1]))

    if len(free_answers_df) != 0:
        free_answers_df = pd.DataFrame(free_answers_df)
    else:
        free_answers_df = pd.DataFrame({})

    return final_data_list, nps_df, csi_pre, free_answers_df, answer_for_user
