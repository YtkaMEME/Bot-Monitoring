import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.data_processing.models import AnalysisResult, Question, format_excel_decimal_separator
from src.utils.division_df import (
    divider_column_names,
    multi_division_df,
    process_result_with_divider,
)


class MultipleDividersTest(unittest.TestCase):
    def test_single_divider_keeps_original_column(self):
        result = AnalysisResult()
        result.data_frames = [pd.DataFrame({"Номер вопроса": ["D1_1"]})]

        process_result_with_divider(result, "Женщины")

        self.assertEqual(result.data_frames[0].columns.tolist(), ["Номер вопроса", "Разделитель"])
        self.assertEqual(result.data_frames[0]["Разделитель"].iloc[0], "Женщины")

    def test_divider_values_remain_separate(self):
        answers = [
            ["Женщины | Москва", "Женщины | Москва", "Мужчины", "Мужчины"],
            ["18-25", "26-30", "18-25", "26-30"],
            ["Онлайн", "Очно", "Онлайн", "Очно"],
        ]
        questions = [
            Question(
                name=f"Вопрос {index}",
                type_q="Одиночный выбор",
                data=pd.DataFrame({"value": [None, None, *values]}),
                id=f"D1_{index}",
            )
            for index, values in enumerate(answers, start=1)
        ]
        weights = pd.DataFrame({"ones": [1] * 6})

        for divisions in ([1, 2], [1, 2, 3]):
            with self.subTest(divisions=divisions):
                groups = multi_division_df(questions, weights, divisions)
                self.assertTrue(groups)
                self.assertTrue(all(len(key) == len(divisions) for key in groups))
                self.assertIn(tuple(values[0] for values in answers[:len(divisions)]), groups)
                self.assertEqual(len(divider_column_names(divisions)), len(divisions))

    def test_all_export_sheets_have_two_divider_columns(self):
        columns = divider_column_names([1, 2])
        results = []
        for values in (("Женщины | Москва", "18-25"), ("Мужчины", "26-30"), ("Общее", "")):
            result = AnalysisResult()
            result.data_frames = [pd.DataFrame({
                "Номер вопроса": ["D1_3"],
                "Вопрос": ["Оценка"],
                "Шкала": ["Оценка"],
                "Оценка": ["Да"],
                "Количество": [1.5],
                "Процент": [0.25],
            })]
            result.nps_frame = pd.DataFrame({
                "Шкала": ["Итог"], "Количество": [1.5], "Процент": [0.25],
            })
            result.tr_frame = pd.DataFrame({
                "Категория": ["TR (%)"], "Количество": [1.5], "Процент": [0.25],
            })
            result.roti_frame = pd.DataFrame({
                "Оценка": ["Среднее ROTI"], "Количество": [""], "Процент": [0.25],
            })
            result.csi_frame = pd.DataFrame({
                "Параметр": ["Итого:"], "CSI по параметру": [2.5],
            })
            result.free_answers_frame = pd.DataFrame({"Ответ": ["Комментарий"]})
            results.append(process_result_with_divider(result, dict(zip(columns, values))))

        combined = AnalysisResult()
        combined.data_frames = [frame for result in results for frame in result.data_frames]
        for name in ("nps_frame", "tr_frame", "roti_frame", "csi_frame", "free_answers_frame"):
            setattr(combined, name, pd.concat([getattr(result, name) for result in results], ignore_index=True))

        summary = combined.build_summary()
        self.assertIn("NPS Разделитель 1 (вопрос 1)=Женщины | Москва | Разделитель 2 (вопрос 2)=18-25", summary)
        self.assertIn("TR Общее", summary)
        self.assertIn("ROTI Общее", summary)
        self.assertIn("CSI Общее", summary)

        with tempfile.TemporaryDirectory() as directory:
            excel_path = str(Path(directory) / "result.xlsx")
            csv_path = str(Path(directory) / "result.csv")
            combined.to_excel_division(excel_path)
            combined.to_csv(csv_path)
            format_excel_decimal_separator(excel_path)

            workbook = load_workbook(excel_path)
            for worksheet in workbook.worksheets:
                headers = [cell.value for cell in worksheet[1]]
                self.assertEqual(headers[-2:], columns)
                self.assertNotIn("Разделитель", headers)
                self.assertEqual(worksheet.cell(2, len(headers) - 1).value, "Женщины | Москва")
                self.assertEqual(worksheet.cell(2, len(headers)).value, "18-25")
                self.assertEqual(worksheet.cell(4, len(headers) - 1).value, "Общее")

            csv = pd.read_csv(csv_path)
            self.assertEqual(csv.columns[-2:].tolist(), columns)
            self.assertEqual(csv.iloc[0][columns[0]], "Женщины | Москва")
            self.assertEqual(csv.iloc[0][columns[1]], "18-25")


if __name__ == "__main__":
    unittest.main()
