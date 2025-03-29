import os
import asyncio
from typing import Tuple, Optional, List, Any
import pandas as pd
from aiogram.types import Message

from .file_processor import read_file, table_validation, create_questions_list
from .analyzer import analyze_questions
from .models import AnalysisError


async def process_data(
    path: str,
    mood_number: Optional[int] = None,
    nps_number: Optional[int] = None,
    csi_numbers: Optional[List[int]] = None,
    message: Optional[Message] = None,
    num_persons: int = 1
) -> Tuple[str, str]:
    """
    Обработка данных из файла анкеты
    
    Args:
        path: путь к файлу Excel
        mood_number: номер вопроса о настроении
        nps_number: номер вопроса NPS
        csi_numbers: номера вопросов CSI
        message: объект сообщения для отправки уведомлений
        num_persons: количество участников
        
    Returns:
        Кортеж с путями к файлам Excel и CSV
    """
    # Получаем имя файла для создания выходных файлов
    name = path.split("/")[-1].split(".")[0]
    excel_path = f'./{name}_modified.xlsx'
    csv_path = f'./{name}_modified.csv'
    
    # Чтение и валидация данных из файла
    df = read_file(path)
    df = table_validation(df)
    
    # Создание списка вопросов
    questions_list = create_questions_list(df)
    
    try:
        # Анализ вопросов
        result = analyze_questions(questions_list, mood_number, nps_number, csi_numbers, num_persons)
        
        # Сохранение результатов
        result.to_excel(excel_path)
        result.to_csv(csv_path)
        
        # Отправка сообщения о пропущенных вопросах
        if message and result.skipped_questions:
            await message.answer(f"Были пропущены следующие вопросы{result.skipped_questions}")
        
    except AnalysisError as e:
        if message:
            await message.answer(f"{e}")
        if os.path.exists(path):
            os.remove(path)
        raise
    except Exception as e:
        if message:
            await message.answer(f"Произошла какая-то ошибка \U0001F63F\nНо ведь у меня лапки\U0001F43E")
        if os.path.exists(path):
            os.remove(path)
        raise
    
    return excel_path, csv_path 