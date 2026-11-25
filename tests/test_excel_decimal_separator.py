import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.data_processing.models import AnalysisResult, format_excel_decimal_separator


class ExcelDecimalSeparatorTest(unittest.TestCase):
    def make_result(self, divided):
        result = AnalysisResult()
        rows = {
            "Номер вопроса": ["D1_1", "D1_1"],
            "Вопрос": ["Оценка", "Оценка"],
            "Шкала": ["Оценка", "Оценка"],
            "Оценка": ["4.5", "Обычный ответ"],
            "Количество": [2.25, 1],
            "Процент": [0.125, 0.875],
        }
        if divided:
            rows["Разделитель"] = ["Группа 1", "Группа 1"]
        result.data_frames = [pd.DataFrame(rows)]
        result.nps_frame = pd.DataFrame({
            "Шкала": ["Приверженцы"],
            "Количество": [1.5],
            "Процент": [0.125],
        })
        result.tr_frame = pd.DataFrame({
            "Категория": ["TR (%)"],
            "Количество": [2.5],
            "Процент": [0.625],
        })
        result.roti_frame = pd.DataFrame({
            "Оценка": ["5", "Среднее ROTI"],
            "Количество": [1.25, ""],
            "Процент": [0.375, 0.625],
        })
        result.csi_frame = pd.DataFrame({
            "Параметр": ["Итого:"],
            "Важность параметра": [1.75],
            "Оценка параметра": [4.5],
            "CSI по параметру": [3.625],
        })
        result.free_answers_frame = pd.DataFrame({
            "Ответ": ["«Оценка 4.5 из 5»"],
        })
        return result

    def test_all_sheets_and_csv(self):
        for divided in (False, True):
            with self.subTest(divided=divided), tempfile.TemporaryDirectory() as directory:
                excel_path = str(Path(directory) / "result.xlsx")
                csv_path = str(Path(directory) / "result.csv")
                result = self.make_result(divided)

                if divided:
                    result.to_excel_division(excel_path)
                else:
                    result.to_excel(excel_path)
                result.to_csv(csv_path)
                format_excel_decimal_separator(excel_path)

                workbook = load_workbook(excel_path)
                self.assertEqual(workbook["Sheet1"]["D2"].value, "4,5")
                self.assertEqual(workbook["Sheet1"]["E2"].value, "2,25")
                self.assertEqual(workbook["Sheet1"]["F2"].value, "12,5%")
                self.assertEqual(workbook["Sheet1"]["E3"].value, 1)
                self.assertEqual(workbook["NPS"]["B2"].value, "1,5")
                self.assertEqual(workbook["NPS"]["C2"].value, "12,50%")
                self.assertEqual(workbook["TR"]["C2"].value, "62,50%")
                self.assertEqual(workbook["ROTI"]["C2"].value, "37,50%")
                self.assertEqual(workbook["ROTI"]["C3"].value, "0,625")
                self.assertEqual(workbook["CSI"]["B2"].value, "1,75")
                self.assertEqual(workbook["CSI"]["D2"].value, "3,625")
                self.assertEqual(
                    workbook["Открытые комментарии"]["A2"].value,
                    "«Оценка 4.5 из 5»",
                )
                self.assertAlmostEqual(pd.read_csv(csv_path)["Количество"][0], 2.25)


if __name__ == "__main__":
    unittest.main()
