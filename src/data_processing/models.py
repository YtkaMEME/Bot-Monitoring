from copy import deepcopy
from decimal import Decimal
import math
import re
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from openpyxl import load_workbook


_DECIMAL_TEXT = re.compile(r"[+-]?\d+\.\d+(?:[eE][+-]?\d+)?%?")
_PERCENT_FORMAT = re.compile(r"0(?:\.(0+))?%")


def format_excel_decimal_separator(excel_path: str) -> None:
    """Записывает дробные значения во всех листах XLSX с десятичной запятой."""
    workbook = load_workbook(excel_path)
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if isinstance(value, float) and not math.isfinite(value):
                        continue

                    percent_format = _PERCENT_FORMAT.fullmatch(cell.number_format)
                    if percent_format:
                        percent = Decimal(str(value)) * 100
                        places = len(percent_format.group(1) or "")
                        if places == 0 and percent != percent.to_integral_value():
                            # На основном листе показываем дробную часть процента,
                            # даже если старый формат ячейки был целым процентом.
                            places = 2
                            formatted = f"{percent:.{places}f}".rstrip("0").rstrip(".")
                        else:
                            formatted = f"{percent:.{places}f}"
                        cell.value = f"{formatted.replace('.', ',')}%"
                        cell.number_format = "@"
                    elif isinstance(value, float) and not value.is_integer():
                        cell.value = format(Decimal(str(value)), "f").replace(".", ",")
                        cell.number_format = "@"
                elif isinstance(value, str) and _DECIMAL_TEXT.fullmatch(value):
                    cell.value = value.replace(".", ",")
                    cell.number_format = "@"

    workbook.save(excel_path)


def _divider_columns(frame: pd.DataFrame) -> List[str]:
    if "Разделитель" in frame.columns:
        return ["Разделитель"]
    return [
        column for column in frame.columns
        if isinstance(column, str) and column.startswith("Разделитель ")
    ]


def _divider_groups(frame: pd.DataFrame):
    columns = _divider_columns(frame)
    for values, group in frame.groupby(columns, sort=False, dropna=False):
        if not isinstance(values, tuple):
            values = (values,)
        if columns == ["Разделитель"] or values[0] == "Общее":
            label = str(values[0])
        else:
            label = " | ".join(
                f"{column}={value}"
                for column, value in zip(columns, values)
                if pd.notna(value) and value != ""
            )
        yield label, group


class Question:
    """
    Класс для представления вопроса и его данных из анкеты
    """
    def __init__(self, name: str, type_q: str, data: pd.Series, id: str):
        """
        Инициализация вопроса
        
        Args:
            name: название вопроса
            type_q: тип вопроса
            data: данные вопроса
            id: идентификатор вопроса
        """
        self.name: str = name
        self.type: str = type_q
        self.data: pd.Series = data
        self.id: str = id

    def copy(self) -> 'Question':
        """
        Создает полную копию объекта Question.
        """
        return Question(
            name=self.name,
            type_q=self.type,
            data=deepcopy(self.data),
            id=self.id
        )

class AnalysisError(Exception):
    """
    Исключение для ошибок при анализе данных
    """
    pass


class AnalysisResult:
    """
    Результаты анализа анкеты
    """
    def __init__(self):
        self.data_frames: List[pd.DataFrame] = []
        self.nps_frame: pd.DataFrame = pd.DataFrame()
        self.csi_frame: pd.DataFrame = pd.DataFrame()
        self.tr_frame: pd.DataFrame = pd.DataFrame()
        self.roti_frame: pd.DataFrame = pd.DataFrame()
        self.free_answers_frame: pd.DataFrame = pd.DataFrame()
        self.skipped_questions: str = ""
        
    def has_data(self) -> bool:
        """Проверка наличия данных в результате анализа"""
        return len(self.data_frames) > 0
    
    def build_summary(self) -> str:
        """
        Формирует краткую текстовую сводку по основным показателям (NPS, CSI, TR, ROTI),
        с учетом возможного деления по одному или нескольким вопросам.
        """
        lines: List[str] = []

        # NPS
        if not self.nps_frame.empty:
            df = self.nps_frame
            # Если есть разделитель — группируем по нему, иначе один общий результат
            if _divider_columns(df):
                for divider, group in _divider_groups(df):
                    if group.empty:
                        continue
                    # Если есть несколько NPS-вопросов, выводим по каждому вопросу в рамках разделителя
                    if "Номер вопроса" in group.columns:
                        for qid, q_group in group.groupby("Номер вопроса"):
                            last_row = q_group.iloc[-1]
                            value = last_row.get("Процент")
                            if isinstance(value, (int, float)):
                                percent = round(float(value) * 100, 1)
                                lines.append(f"NPS {qid} {divider}: {percent:.1f}%")
                    else:
                        last_row = group.iloc[-1]
                        value = last_row.get("Процент")
                        if isinstance(value, (int, float)):
                            percent = round(float(value) * 100, 1)
                            lines.append(f"NPS {divider}: {percent:.1f}%")
            else:
                # Если есть несколько NPS-вопросов без деления — выводим каждый
                if "Номер вопроса" in df.columns:
                    for _, group in df.groupby("Номер вопроса"):
                        last_row = group.iloc[-1]
                        value = last_row.get("Процент")
                        if isinstance(value, (int, float)):
                            percent = round(float(value) * 100, 1)
                            qid = last_row.get("Номер вопроса")
                            lines.append(f"NPS {qid}: {percent:.1f}%")
                else:
                    last_row = df.iloc[-1]
                    value = last_row.get("Процент")
                    if isinstance(value, (int, float)):
                        percent = round(float(value) * 100, 1)
                        lines.append(f"NPS: {percent:.1f}%")

        # TR
        if not self.tr_frame.empty:
            df = self.tr_frame
            if _divider_columns(df):
                for divider, group in _divider_groups(df):
                    row = group[group.get("Категория") == "TR (%)"]
                    if row.empty:
                        continue
                    row = row.iloc[0]
                    value = row.get("Процент")
                    if isinstance(value, (int, float)):
                        percent = round(float(value) * 100, 1)
                        lines.append(f"TR {divider}: {percent:.1f}%")
            else:
                row = df[df.get("Категория") == "TR (%)"]
                if not row.empty:
                    row = row.iloc[0]
                    value = row.get("Процент")
                    if isinstance(value, (int, float)):
                        percent = round(float(value) * 100, 1)
                        lines.append(f"TR: {percent:.1f}%")

        # ROTI
        if not self.roti_frame.empty:
            df = self.roti_frame
            if _divider_columns(df):
                for divider, group in _divider_groups(df):
                    row = group[group.get("Оценка") == "Среднее ROTI"]
                    if row.empty:
                        continue
                    row = row.iloc[0]
                    value = row.get("Процент")
                    if isinstance(value, (int, float)):
                        lines.append(f"ROTI {divider}: {float(value):.2f}")
            else:
                row = df[df.get("Оценка") == "Среднее ROTI"]
                if not row.empty:
                    row = row.iloc[0]
                    value = row.get("Процент")
                    if isinstance(value, (int, float)):
                        lines.append(f"ROTI: {float(value):.2f}")

        # CSI
        if not self.csi_frame.empty:
            df = self.csi_frame
            if _divider_columns(df):
                for divider, group in _divider_groups(df):
                    row = group[group.get("Параметр") == "Итого:"]
                    if row.empty:
                        continue
                    row = row.iloc[0]
                    value = row.get("CSI по параметру")
                    if isinstance(value, (int, float)):
                        lines.append(f"CSI {divider}: {float(value):.2f}%")
            else:
                row = df[df.get("Параметр") == "Итого:"]
                if not row.empty:
                    row = row.iloc[0]
                    value = row.get("CSI по параметру")
                    if isinstance(value, (int, float)):
                        lines.append(f"CSI: {float(value):.2f}%")

        return "\n".join(lines)
        
    def to_excel(self, excel_path: str) -> None:
        """
        Сохранение результатов в Excel файл
        
        Args:
            excel_path: путь к файлу Excel
        """
        if not self.has_data():
            # Создаем пустой DataFrame если нет данных
            pd.DataFrame().to_excel(excel_path, index=False)
            return
            
        # Объединяем все DataFrame в один
        final_frame = pd.concat(self.data_frames, ignore_index=True)
        final_frame.to_excel(excel_path, index=False)
        
        # Добавляем дополнительные листы если есть данные
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            # Форматируем проценты в основном листе
            workbook = writer.book
            worksheet = workbook['Sheet1']
            
            # Обновляем номера в первом столбце
            new_num = 1
            if worksheet.max_row > 1:
                previous_num = int(worksheet['A2'].value.split("_")[1])
                
                for i in range(2, worksheet.max_row + 1):
                    current_cell = worksheet[f'A{i}']
                    current_num = int(current_cell.value.split("_")[1])
                    if previous_num == current_num:
                        current_cell.value = f"D1_{new_num}"
                    else:
                        previous_num = current_num
                        new_num += 1
                        current_cell.value = f"D1_{new_num}"
            
            # Форматируем проценты
            for cell in worksheet['F']:
                if cell.row > 1:
                    if cell.value is not None and isinstance(cell.value, (int, float)):
                        cell.number_format = '0%'
        
        # Добавляем NPS если есть
        if not self.nps_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.nps_frame.to_excel(writer, sheet_name='NPS', index=False)
                
                # Форматируем проценты
                workbook = writer.book
                worksheet = workbook['NPS']
                for cell in worksheet['C']:
                    if cell.row > 1:
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'
        
        # Добавляем TR если есть
        if not self.tr_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.tr_frame.to_excel(writer, sheet_name='TR', index=False)

                workbook = writer.book
                worksheet = workbook['TR']
                for cell in worksheet['C']:  # колонка "Процент"
                    if cell.row > 1:
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        # Добавляем ROTI если есть
        if not self.roti_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.roti_frame.to_excel(writer, sheet_name='ROTI', index=False)
                workbook = writer.book
                worksheet = workbook['ROTI']
                for cell in worksheet['C']:  # колонка "Процент"
                    if cell.row > 1 and worksheet.cell(cell.row, 1).value != "Среднее ROTI":
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        # Добавляем CSI если есть
        if not self.csi_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.csi_frame.to_excel(writer, sheet_name='CSI', index=False)
        
        # Добавляем свободные ответы если есть
        if not self.free_answers_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.free_answers_frame.to_excel(writer, sheet_name='Открытые комментарии', index=False)
    
    def to_csv(self, csv_path: str) -> None:
        """
        Сохранение основных результатов в CSV файл
        
        Args:
            csv_path: путь к файлу CSV
        """
        if not self.has_data():
            pd.DataFrame().to_csv(csv_path, index=False, encoding='utf-8')
            return
            
        # Читаем данные из Excel и сохраняем в CSV
        df = pd.read_excel(csv_path.replace('.csv', '.xlsx'), engine="openpyxl")
        df.to_csv(csv_path, index=False, encoding='utf-8')

    def to_excel_division(self, excel_path: str) -> None:
        """
        Сохранение результатов в Excel файл

        Args:
            excel_path: путь к файлу Excel
        """
        if not self.has_data():
            # Создаем пустой DataFrame если нет данных
            pd.DataFrame().to_excel(excel_path, index=False)
            return

        # Объединяем все DataFrame в один
        final_frame = pd.concat(self.data_frames, ignore_index=True)
        final_frame.to_excel(excel_path, index=False)

        # Добавляем дополнительные листы если есть данные
        with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
            # Форматируем проценты в основном листе
            workbook = writer.book
            worksheet = workbook['Sheet1']

            # Форматируем проценты
            for cell in worksheet['F']:
                if cell.row > 1:
                    if cell.value is not None and isinstance(cell.value, (int, float)):
                        cell.number_format = '0%'

        # Добавляем NPS если есть
        if not self.nps_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.nps_frame.to_excel(writer, sheet_name='NPS', index=False)

                # Форматируем проценты
                workbook = writer.book
                worksheet = workbook['NPS']
                for cell in worksheet['C']:
                    if cell.row > 1:
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        # Добавляем TR если есть
        if not self.tr_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.tr_frame.to_excel(writer, sheet_name='TR', index=False)

                workbook = writer.book
                worksheet = workbook['TR']
                for cell in worksheet['C']:  # колонка "Процент"
                    if cell.row > 1:
                        if cell.value is not None and isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        # Добавляем ROTI если есть
        if not self.roti_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.roti_frame.to_excel(writer, sheet_name='ROTI', index=False)
                workbook = writer.book
                worksheet = workbook['ROTI']
                for cell in worksheet['C']:  # колонка "Процент"
                    if cell.row > 1 and worksheet.cell(cell.row, 1).value != "Среднее ROTI":
                        if isinstance(cell.value, (int, float)):
                            cell.number_format = '0.00%'

        # Добавляем CSI если есть
        if not self.csi_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.csi_frame.to_excel(writer, sheet_name='CSI', index=False)

        # Добавляем свободные ответы если есть
        if not self.free_answers_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.free_answers_frame.to_excel(writer, sheet_name='Открытые комментарии', index=False)
