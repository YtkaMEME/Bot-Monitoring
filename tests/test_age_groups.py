import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_processing.age_groups import (  # noqa: E402
    build_age_groups,
    find_age_group_label,
    normalize_age_question_to_ranges,
    parse_age_value,
)
from src.data_processing.models import Question  # noqa: E402


class AgeGroupsTest(unittest.TestCase):
    def test_parse_numeric_age_values(self):
        self.assertEqual(parse_age_value(18), 18)
        self.assertEqual(parse_age_value(18.0), 18)
        self.assertEqual(parse_age_value("18"), 18)
        self.assertEqual(parse_age_value("18.0"), 18)
        self.assertIsNone(parse_age_value("18-25"))
        self.assertIsNone(parse_age_value("18 лет"))

    def test_find_age_group_for_number(self):
        groups = build_age_groups(["18-25", "26-30", "31-35"])

        self.assertEqual(find_age_group_label(18, groups), "18-25")
        self.assertEqual(find_age_group_label(25, groups), "18-25")
        self.assertEqual(find_age_group_label(26, groups), "26-30")
        self.assertEqual(find_age_group_label(35, groups), "31-35")
        self.assertIsNone(find_age_group_label(36, groups))

    def test_normalize_age_question_to_ranges(self):
        question = Question(
            name="Возраст",
            type_q="Выпадающий список",
            data=pd.DataFrame({"value": [None, None, 18, 22, 26, 31, 35, 36, "18-25"]}),
            id="D1_2",
        )

        converted = normalize_age_question_to_ranges(
            [question],
            age_question_number=2,
            age_group_labels=["18-25", "26-30", "31-35"],
        )

        self.assertEqual(converted, 5)
        self.assertEqual(
            question.data["value"].tolist(),
            [None, None, "18-25", "18-25", "26-30", "31-35", "31-35", 36, "18-25"],
        )


if __name__ == "__main__":
    unittest.main()

