import os
import json
import sqlite3
from pathlib import Path
from typing import List, Any, Optional


class Config:
    """Конфигурация приложения"""
    
    def __init__(self) -> None:
        self.project_root: Path = Path(__file__).resolve().parents[1]
        self._load_env_file(self.project_root / ".env")

        # Токен бота, загружаем из переменной окружения или из файла
        self.token: str = os.getenv("BOT_TOKEN") or self._load_token()
        self.yandex_disk_token: str = os.getenv("YANDEX_DISK_TOKEN", "")
        self.yandex_reports_folder: str = os.getenv("YANDEX_REPORTS_FOLDER", "disk:/Anketolog Reports")
        self.monitoring_db_path: str = os.path.abspath(
            os.getenv(
                "MONITORING_DB_PATH",
                str(self.project_root.parent / "TelegramMiniAppMonitoring" / "data" / "db.sqlite"),
            )
        )
        self.mini_app_url: str = os.getenv("MINI_APP_URL", "")
        
        # Пути к JSON файлам
        self.allowed_users_file: str = str(self.project_root / "config" / "allowed_users.json")
        self.admin_users_file: str = str(self.project_root / "config" / "admins.json")
        self.trash_list_file: str = str(self.project_root / "config" / "list_to_del.json")
        
        # Создаем директорию для временных файлов если не существует
        self.download_dir: str = str(self.project_root / "downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Загружаем списки пользователей и мусорных слов
        self.allowed_users: List[int] = self._load_json(self.allowed_users_file, [])
        self.admin_users: List[int] = self._load_json(self.admin_users_file, [])
        self.trash_list: List[str] = self._load_json(self.trash_list_file, [])
        self._sync_allowed_users_from_db_or_seed()

    def _load_env_file(self, env_path: Path) -> None:
        """Простая загрузка переменных окружения из .env"""
        if not os.path.exists(env_path):
            return

        try:
            with open(env_path, "r", encoding="utf-8") as env_file:
                for raw_line in env_file:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            # Если .env недоступен, продолжаем без него
            return
    
    def _load_token(self) -> str:
        """Загрузка токена из файла"""
        try:
            # Пытаемся импортировать токен из файла TOKEN.py
            import sys
            sys.path.append(str(self.project_root))
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
        self._save_allowed_users_to_db()

    def refresh_allowed_users(self) -> None:
        """Обновление списка разрешенных пользователей из общей SQLite базы."""
        users = self._load_allowed_users_from_db()
        if users is None:
            return

        if users or not self.allowed_users:
            self.allowed_users = users
            with open(self.allowed_users_file, 'w', encoding='utf-8') as file:
                json.dump(self.allowed_users, file, ensure_ascii=False, indent=4)
        else:
            self._save_allowed_users_to_db()
    
    def save_admin_users(self) -> None:
        """Сохранение списка администраторов"""
        with open(self.admin_users_file, 'w', encoding='utf-8') as file:
            json.dump(self.admin_users, file, ensure_ascii=False, indent=4)
    
    def save_trash_list(self) -> None:
        """Сохранение списка мусорных слов"""
        with open(self.trash_list_file, 'w', encoding='utf-8') as file:
            json.dump(self.trash_list, file, ensure_ascii=False, indent=4)

    def _connect_monitoring_db(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.monitoring_db_path), exist_ok=True)
        conn = sqlite3.connect(self.monitoring_db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_allowed_users_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _load_allowed_users_from_db(self) -> Optional[List[int]]:
        try:
            conn = self._connect_monitoring_db()
            self._ensure_allowed_users_table(conn)
            rows = conn.execute("SELECT id FROM allowed_users ORDER BY id").fetchall()
            conn.close()
        except sqlite3.Error:
            return None

        return [int(row[0]) for row in rows]

    def _save_allowed_users_to_db(self) -> None:
        try:
            conn = self._connect_monitoring_db()
            self._ensure_allowed_users_table(conn)
            with conn:
                conn.execute("DELETE FROM allowed_users")
                conn.executemany(
                    "INSERT OR IGNORE INTO allowed_users (id) VALUES (?)",
                    [(int(user_id),) for user_id in self.allowed_users],
                )
            conn.close()
        except sqlite3.Error:
            return

    def _sync_allowed_users_from_db_or_seed(self) -> None:
        users_from_db = self._load_allowed_users_from_db()
        if users_from_db:
            self.allowed_users = users_from_db
            with open(self.allowed_users_file, 'w', encoding='utf-8') as file:
                json.dump(self.allowed_users, file, ensure_ascii=False, indent=4)
            return

        if self.allowed_users:
            self._save_allowed_users_to_db()


# Создаем экземпляр конфигурации
config = Config()
