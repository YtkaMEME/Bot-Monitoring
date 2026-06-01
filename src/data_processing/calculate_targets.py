import os
from .models import Question
import pandas as pd
from typing import List, Dict

import sqlite3
import json

from config.config import config


def _connect_monitoring_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.monitoring_db_path), exist_ok=True)
    conn = sqlite3.connect(config.monitoring_db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_form_data_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS form_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menCount TEXT,
            womenCount TEXT,
            artSchools TEXT,
            ageGroups TEXT
        )
    ''')


def _ensure_calculation_results_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sampleSize INTEGER,
            targetPol TEXT,
            targetAge TEXT,
            targetArt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _normalize_weight_value(value, dimension_index: int) -> str:
    text = "" if pd.isna(value) else str(value).strip().lower()
    if dimension_index == 0:
        if any(part in text for part in ["муж", "парень", "male"]) or text in {"м", "m"}:
            return "мужской"
        if any(part in text for part in ["жен", "дев", "female"]) or text in {"ж", "f"}:
            return "женский"
    return text


def rake_weights(
    df: pd.DataFrame,
    targets: Dict[str, Dict[str, float]],
    sample_size,
    max_iterations: int = 50,
    tolerance: float = 1e-4
) -> pd.DataFrame:
    """
    Выполняет итеративное взвешивание (raking) по заданным признакам.

    Args:
        df (pd.DataFrame): DataFrame с колонками признаков и колонкой 'Вес'
        targets (Dict[str, Dict[str, float]]): словарь, где ключ — название признака, а значение — target distribution
        max_iterations (int): максимум итераций
        tolerance (float): порог отклонения для завершения

    Returns:
        pd.DataFrame с обновлённой колонкой 'Вес'
    """
    weights = df['Вес'].copy()

    for iteration in range(max_iterations):
        prev_weights = weights.copy()

        for col, target_dist in targets.items():
            total_weight = weights.sum()
            if total_weight == 0:
                raise ValueError("Сумма весов равна нулю. Проверьте совпадение групп на сайте и в выгрузке.")
            # Текущие доли
            actuals = weights.groupby(df[col]).sum() / total_weight
            for category, target_share in target_dist.items():
                actual_share = actuals.get(category, 0)
                if actual_share == 0:
                    multiplier = 0
                else:
                    multiplier = target_share / actual_share
                # Применяем коэффициент к нужным строкам
                weights[df[col] == category] *= multiplier


        # Проверка сходимости
        max_diff = (weights - prev_weights).abs().max()
        if max_diff < tolerance:
            print(f"Сошлось за {iteration + 1} итераций (max_diff = {max_diff:.6f})")
            break
    else:
        print("Предупреждение: достигнут максимум итераций без полной сходимости.")

    df['Вес'] = weights
    return df


def save_calculation_results(sample_size, target_pol, target_age, target_art):
    conn = _connect_monitoring_db()
    cursor = conn.cursor()

    _ensure_calculation_results_table(cursor)

    cursor.execute('''
        INSERT INTO calculation_results (sampleSize, targetPol, targetAge, targetArt)
        VALUES (?, ?, ?, ?)
    ''', (
        sample_size,
        json.dumps(target_pol, ensure_ascii=False),
        json.dumps(target_age, ensure_ascii=False),
        json.dumps(target_art, ensure_ascii=False)
    ))

    conn.commit()
    conn.close()


# Подключение к базе и чтение данных
def fetch_form_data():
    conn = _connect_monitoring_db()
    cursor = conn.cursor()

    _ensure_form_data_table(cursor)
    cursor.execute("SELECT menCount, womenCount, artSchools, ageGroups FROM form_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    try:
        men_count = int(row[0])
        women_count = int(row[1])

        artSchools_data = json.loads(row[2])
        ageGroups_data = json.loads(row[3])

        art_school_labels = [str(item['name']) for item in artSchools_data]
        art_school_distribution = [int(item['count']) for item in artSchools_data]

        age_group_labels = [str(item['range']) for item in ageGroups_data]
        age_group_distribution = [int(item['count']) for item in ageGroups_data]
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Данные формы в mini app заполнены некорректно.") from error

    return men_count, women_count, art_school_labels, art_school_distribution, age_group_labels, age_group_distribution


def count_matches_against_targets(question_dfs: List[Question], target_distributions: List[Dict[str, float]]) -> \
List[Dict[str, int]]:
    """
    Подсчитывает количество записей в каждом вопросе, соответствующих ключам из словаря target_distributions.

    Args:
        question_dfs (List[pd.DataFrame]): список DataFrame'ов, каждый из которых представляет отдельный вопрос
        target_distributions (List[Dict[str, float]]): список словарей с возможными значениями и их долями

    Returns:
        List[Dict[str, int]]: список словарей с количеством соответствий по каждому значению
    """
    result = []
    question_dfs = [q.data for q in question_dfs]
    for idx, (df, target_dict) in enumerate(zip(question_dfs, target_distributions)):
        
        counts = {}
        series = df.squeeze().apply(lambda value: _normalize_weight_value(value, idx))
        for key in target_dict:
            counts[key] = (series == key).sum()
        result.append(counts)

    return result


def calculate_raw_weights_from_questions(
        questions: List[Question],
        question_numbers: List[int],
        targets: List[Dict[str, float]], sample_size
):
    real_count = count_matches_against_targets(questions, targets)
    question_map = {int(q.id.split("_")[1]): q for q in questions}
    missing_questions = [num for num in question_numbers if num not in question_map]
    if missing_questions:
        raise ValueError(f"В выгрузке не найдены вопросы для взвешивания: {missing_questions}")

    selected_questions = [question_map[num] for num in question_numbers]
    df = pd.DataFrame({'ID_ответа': selected_questions[0].data.index})

    for idx, q in enumerate(selected_questions):
        df[q.name] = q.data["value"].apply(lambda value: _normalize_weight_value(value, idx)).values

    def calc_row_weight(row):
        weight = 1.0
        for i, q in enumerate(selected_questions):
            val = row[q.name]

            target = targets[i].get(val, 0) * sample_size
            actual = real_count[i].get(val, 1)

            if actual == 0 or target == 0:
                local_weight = 0
            else:
                local_weight = target / actual
            weight *= local_weight
        return weight

    # Шаг 1: начальные веса
    df['Вес'] = df.apply(calc_row_weight, axis=1)
    df['Вес'] = pd.to_numeric(df['Вес'], errors='coerce').fillna(0).astype(float)

    # Шаг 2: нормализуем сумму весов до sample_size
    weight_sum = df['Вес'].sum()
    if weight_sum == 0:
        raise ValueError("Не удалось рассчитать веса: группы на сайте не совпали с ответами в выгрузке.")
    df['Вес'] *= sample_size / weight_sum

    # Шаг 3: применяем итеративное взвешивание (RAKING)
    rake_targets = {
        selected_questions[0].name: targets[0],
        selected_questions[1].name: targets[1],
        selected_questions[2].name: targets[2],
    }

    df = rake_weights(df, rake_targets, sample_size)

    # Шаг 4: сохранить в том формате, как ждет дальнейший код
    shifted_weights_df = df[['Вес']].rename(columns={'Вес': 'ones'})
    return shifted_weights_df
