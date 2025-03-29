import os
import json
from typing import List, Dict, Any, Optional


class Config:
    """Конфигурация приложения"""
    
    def __init__(self) -> None:
        # Токен бота, загружаем из переменной окружения или из файла
        self.token: str = os.getenv("BOT_TOKEN") or self._load_token()
        
        # Пути к JSON файлам
        self.allowed_users_file: str = "config/allowed_users.json"
        self.admin_users_file: str = "config/admins.json"
        self.trash_list_file: str = "config/list_to_del.json"
        
        # Создаем директорию для временных файлов если не существует
        self.download_dir: str = "downloads"
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Загружаем списки пользователей и мусорных слов
        self.allowed_users: List[int] = self._load_json(self.allowed_users_file, [])
        self.admin_users: List[int] = self._load_json(self.admin_users_file, [])
        self.trash_list: List[str] = self._load_json(self.trash_list_file, [])
    
    def _load_token(self) -> str:
        """Загрузка токена из файла"""
        try:
            # Пытаемся импортировать токен из файла TOKEN.py
            import sys
            sys.path.append('.')
            from TOKEN import TOKEN
            return TOKEN
        except ImportError:
            raise ValueError("Токен не найден. Установите переменную окружения BOT_TOKEN или создайте файл TOKEN.py")
    
    def _load_json(self, file_path: str, default: Any) -> Any:
        """Загрузка данных из JSON файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            # Если файл не существует или поврежден, создаем новый
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(default, file, ensure_ascii=False, indent=4)
            return default
    
    def save_allowed_users(self) -> None:
        """Сохранение списка разрешенных пользователей"""
        with open(self.allowed_users_file, 'w', encoding='utf-8') as file:
            json.dump(self.allowed_users, file, ensure_ascii=False, indent=4)
    
    def save_admin_users(self) -> None:
        """Сохранение списка администраторов"""
        with open(self.admin_users_file, 'w', encoding='utf-8') as file:
            json.dump(self.admin_users, file, ensure_ascii=False, indent=4)
    
    def save_trash_list(self) -> None:
        """Сохранение списка мусорных слов"""
        with open(self.trash_list_file, 'w', encoding='utf-8') as file:
            json.dump(self.trash_list, file, ensure_ascii=False, indent=4)


# Создаем экземпляр конфигурации
config = Config() 