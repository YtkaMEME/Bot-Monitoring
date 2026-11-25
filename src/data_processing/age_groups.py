import math
import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

import pandas as pd

from .models import Question


@dataclass(frozen=True)
class AgeGroup:
    label: str
    start: Optional[int]
    end: Optional[int]

    def contains(self, age: int) -> bool:
        if self.start is not None and age < self.start:
            return False
        if self.end is not None and age > self.end:
            return False
        return True


def normalize_age_question_to_ranges(
    questions: List[Question],
    age_question_number: int,
    age_group_labels: Sequence[str],
) -> int:
    """
    Преобразует числовые ответы возраста в диапазоны из mini app.

    Например, если в выгрузке возраст указан как 22, а в mini app есть группа
    18-25, значение будет заменено на 18-25. Ответы, которые уже являются
    диапазонами или не попали ни в одну группу, остаются без изменений.
    """
    question = find_question_by_number(questions, age_question_number)
    if question is None or "value" not in question.data.columns:
        return 0

    age_groups = build_age_groups(age_group_labels)
    if not age_groups:
        return 0

    converted_count = 0

    def convert_value(value):
        nonlocal converted_count
        age = parse_age_value(value)
        if age is None:
            return value

        group_label = find_age_group_label(age, age_groups)
        if group_label is None:
            return value

        converted_count += 1
        return group_label

    question.data["value"] = question.data["value"].apply(convert_value)
    return converted_count


def find_question_by_number(questions: List[Question], question_number: int) -> Optional[Question]:
    question_id = f"D1_{question_number}"
    for question in questions:
        if question.id == question_id:
            return question
    return None


def build_age_groups(labels: Sequence[str]) -> List[AgeGroup]:
    groups = []
    for label in labels:
        group = parse_age_group_label(str(label))
        if group is not None:
            groups.append(group)
    return groups


def parse_age_group_label(label: str) -> Optional[AgeGroup]:
    text = normalize_dash(label).strip().lower()
    numbers = [int(number) for number in re.findall(r"\d+", text)]

    if len(numbers) >= 2:
        start, end = numbers[0], numbers[1]
        if start > end:
            start, end = end, start
        return AgeGroup(label=label, start=start, end=end)

    if len(numbers) == 1:
        number = numbers[0]
        if "+" in text or "старше" in text or "от " in text:
            return AgeGroup(label=label, start=number, end=None)
        if text.startswith("до ") or "младше" in text:
            return AgeGroup(label=label, start=None, end=number)
        return AgeGroup(label=label, start=number, end=number)

    return None


def parse_age_value(value) -> Optional[int]:
    if pd.isna(value):
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        return None

    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if re.fullmatch(r"\d+(\.0+)?", text):
            return int(float(text))

    return None


def find_age_group_label(age: int, age_groups: Sequence[AgeGroup]) -> Optional[str]:
    for group in age_groups:
        if group.contains(age):
            return group.label
    return None


def normalize_dash(text: str) -> str:
    return text.replace("–", "-").replace("—", "-").replace("−", "-")
