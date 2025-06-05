from .models import Question
import pandas as pd
from typing import List, Dict

import sqlite3
import json

from .prepare_target_distributions import prepare_target_distributions


def save_calculation_results(sample_size, target_pol, target_age, target_art):
    DB_PATH = '/TelegramMiniAppMonitoring/data/db.sqlite'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

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
    DB_PATH = '/TelegramMiniAppMonitoring/data/db.sqlite'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT menCount, womenCount, artSchools, ageGroups FROM form_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    men_count = int(row[0])
    women_count = int(row[1])

    artSchools_data = json.loads(row[2])
    ageGroups_data = json.loads(row[3])

    art_school_labels = [item['name'] for item in artSchools_data]
    art_school_distribution = [int(item['count']) for item in artSchools_data]

    age_group_labels = [item['range'] for item in ageGroups_data]
    age_group_distribution = [int(item['count']) for item in ageGroups_data]

    return men_count, women_count, art_school_labels, art_school_distribution, age_group_labels, age_group_distribution

# Основная функция взвешивания (та же что у тебя была)
def calculate_weights_from_questions(
        questions: List[Question],
        question_numbers: List[int],
        targets: List[Dict[str, float]],
        target_sample_size
):
    question_map = {int(q.id.split("_")[1]): q for q in questions}
    selected_questions = [question_map[num] for num in question_numbers]

    actual_distributions = [
        q.data.value_counts(normalize=True).to_dict() for q in selected_questions
    ]

    df = pd.DataFrame({'ID_ответа': selected_questions[0].data.index})

    for idx, q in enumerate(selected_questions):
        df[q.name] = q.data["value"].values

    def calc_row_weight(row):
        weight = 1.0
        for i, q in enumerate(selected_questions):
            val = row[q.name]
            print(val)
            target = targets[i].get(val, 0)
            actual = actual_distributions[i].get(val, 1)
            if actual == 0:
                local_weight = 0
            else:
                local_weight = target / actual
            weight *= local_weight
        return weight

    df['Вес'] = df.apply(calc_row_weight, axis=1)

    weights_df = df.copy()
    weights_df['Вес'] = pd.to_numeric(weights_df['Вес'], errors='coerce').fillna(0).astype(float)

    scale = target_sample_size / weights_df['Вес'].sum()
    weights_series= weights_df['Вес'] * scale

    shifted_weights = pd.concat([
        pd.Series([0.0]),  # либо NaN — зависит что тебе лучше
        weights_series
    ], ignore_index=True)

    for q in questions:
        q.data["weighted"] = shifted_weights
    return questions
