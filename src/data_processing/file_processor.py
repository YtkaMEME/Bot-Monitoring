import pandas as pd
from typing import List, Tuple, Optional
from .models import Question, AnalysisError


def get_columns_to_drop(df: pd.DataFrame) -> int:
    """
    Получение количества столбцов для удаления
    
    Args:
        df: DataFrame с данными
        
    Returns:
        Количество столбцов для удаления
    """
    counter = -1
    
    for elem in df.columns:
        counter += 1
        if str(elem).split(" ")[0] == "Страница":
            return counter
    
    return 0


def read_file(path: str) -> pd.DataFrame:
    """
    Чтение Excel таблицы
    
    Args:
        path: путь к файлу
        
    Returns:
        DataFrame с данными из файла
    """
    df = pd.read_excel(path, engine="openpyxl")
    
    num_colum_to_drop = get_columns_to_drop(df)
    
    if num_colum_to_drop > 0:
        columns_to_drop = df.columns[:num_colum_to_drop]
        df = df.drop(columns=columns_to_drop)
    
    new_names = df.iloc[0]
    df.columns = new_names
    df = df.drop(0)
    
    return df


def table_validation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Валидация исходной таблицы
    
    Args:
        df: DataFrame с данными
        
    Returns:
        Проверенный и обработанный DataFrame
    """
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


def create_questions_list(df: pd.DataFrame) -> List[Question]:
    """
    Создание готового массива вопросов
    
    Args:
        df: DataFrame с данными
        
    Returns:
        Список вопросов
    """
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
        
        if first != 0 and last != 0:
            type_q = "".join(name[first + 1:last])
            name = "".join(name[0:first])
        else:
            type_q = "Неизвестный"
            
        df.columns.values[i] = name

        data_series = df.iloc[:, i]
        data = pd.DataFrame({
            'value': data_series
        }, index=data_series.index)
        
        new_question = Question(name, type_q, data, id_quest)
        questions_list.append(new_question)
        
        i += 1
    
    return questions_list 