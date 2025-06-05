from typing import List, Dict, Any, Optional, Tuple
import pandas as pd


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
        self.free_answers_frame: pd.DataFrame = pd.DataFrame()
        self.skipped_questions: str = ""
        
    def has_data(self) -> bool:
        """Проверка наличия данных в результате анализа"""
        return len(self.data_frames) > 0
        
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

        # Добавляем CSI если есть
        if not self.csi_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.csi_frame.to_excel(writer, sheet_name='CSI', index=False)

        # Добавляем свободные ответы если есть
        if not self.free_answers_frame.empty:
            with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a') as writer:
                self.free_answers_frame.to_excel(writer, sheet_name='Открытые комментарии', index=False)
