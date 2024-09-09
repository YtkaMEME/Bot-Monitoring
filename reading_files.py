import pandas as pd


class Question:
    def __init__(self, name, type_q, data, id):
        self.name = name
        self.type = type_q
        self.data = data
        self.id = id


# получение количества столбцов для удаления
def get_columns_to_drop(df):
    counter = -1

    for elem in df.columns:
        counter += 1
        if str(elem).split(" ")[0] == "Страница":
            return counter


# чтение excel таблицы
def read_file(path):
    df = pd.read_excel(path, engine="openpyxl")

    num_colum_to_drop = get_columns_to_drop(df)

    columns_to_drop = df.columns[:num_colum_to_drop]
    df = df.drop(columns=columns_to_drop)

    new_names = df.iloc[0]
    df.columns = new_names
    df = df.drop(0)

    return df


# валидация исходной таблицы
def table_validation(df):
    i = 0
    current_number = 1

    while i < len(df.columns):
        name = str(df.columns[i])
        if name == "nan":
            i += 1
            continue

        df.columns.values[i] = f"{name} {current_number}"

        while True:
            if i + 1 >= len(df.columns):
                break

            if str(df.columns[i + 1]) != "nan":
                break
            df.columns.values[i + 1] = f"{name} {current_number}"

            current = df.iloc[0, i]
            if pd.isna(df.iloc[0, i + 1]):
                df.iloc[0, i + 1] = current

            i += 1

        i += 1
        current_number += 1

    return df


# создание готового массива вопросоов
def create_questions_list(df):
    questions_list = []
    i = 0

    while i < len(df.columns):
        name = str(df.columns[i])

        first = 0
        last = 0

        number = int(name.split()[-1])

        id_quest = f"D1_{number}"

        for j in range(len(name) - 1, -1, -1):
            if name[j] == "(":
                first = j
            if name[j] == ")":
                last = j

            if first != 0 and last != 0:
                break

        type = "".join(name[first + 1:last])
        name = "".join(name[0:first])

        df.columns.values[i] = name

        data = df.iloc[:, i]

        new_question = Question(name, type, data, id_quest)
        questions_list.append(new_question)

        i += 1

    return questions_list
