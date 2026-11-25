import pandas as pd

from src.data_processing.models import Question


def divider_column_names(divisions):
    return [
        f"Разделитель {index} (вопрос {number})"
        for index, number in enumerate(divisions, start=1)
    ]


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

def process_result_with_divider(result, key):
    divider_values = key if isinstance(key, dict) else {"Разделитель": key}

    def add_divider(df):
        if isinstance(df, pd.DataFrame):
            for column, value in divider_values.items():
                df[column] = value

    dfs = result.data_frames if isinstance(result.data_frames, list) else [result.data_frames]
    for df in dfs:
        add_divider(df)
    for name in ("free_answers_frame", "csi_frame", "nps_frame", "roti_frame", "tr_frame"):
        add_divider(getattr(result, name, None))
    return result

def multi_division_df(
    questions_list,
    weights,
    divisions,
    prefix=()
):
    """
    Рекурсивно разбивает данные по нескольким вопросам
    """
    if not divisions:
        return {prefix: (questions_list, weights)}

    current_division = divisions[0]
    result = {}

    dict_div, dict_weights = division_df(questions_list, current_division, weights)

    for value, q_list in dict_div.items():
        w_list = dict_weights[value]
        # рекурсивно вызываем для оставшихся делений
        sub_result = multi_division_df(q_list, w_list, divisions[1:], prefix=(*prefix, value))
        result.update(sub_result)

    return result
