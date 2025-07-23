import re
import pandas as pd

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
