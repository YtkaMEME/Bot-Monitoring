import os
import re
import time
from typing import Any

import requests

from config.config import config


BASE_URL = "https://apiv2.anketolog.ru"
SURVEY_LIST_URL = f"{BASE_URL}/survey/manage/list"
SURVEY_REPORT_CREATE_URL = f"{BASE_URL}/survey/report/create"
SURVEY_REPORT_LIST_URL = f"{BASE_URL}/survey/report/list"
SURVEY_FOLDER_LIST_URL = f"{BASE_URL}/survey/folder/list"

REPORT_FORMAT = "excel"
SURVEY_FOLDER = "Мои анкеты"
TIMEOUT = 60
DOWNLOAD_TIMEOUT = 120
POLL_INTERVAL = 7
MAX_POLLS = 80
DOWNLOAD_RETRIES = 12
DOWNLOAD_RETRY_DELAY = 5


class AnketologError(Exception):
    """Ошибка при формировании отчета в Anketolog."""


def _headers() -> dict[str, str]:
    api_key = os.getenv("ANKETOLOG_TOKEN")
    if not api_key:
        raise AnketologError("Не найден `ANKETOLOG_TOKEN` в `.env`.")

    return {
        "x-anketolog-apikey": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\\\|?*]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:150]


def normalize_survey_name(name: str) -> str:
    name = (name or "").strip().lower()
    name = re.sub(r"\s+", " ", name)
    return name


def get_extension(report_format: str) -> str:
    mapping = {
        "excel": "xlsx",
        "csv": "csv",
        "spss": "sav",
        "fpdf": "pdf",
        "fword": "docx",
        "pdf": "pdf",
        "word": "docx",
        "word2": "docx",
        "excelchart": "xlsx",
    }
    return mapping.get(report_format, "bin")


def get_survey_folders() -> Any:
    response = requests.post(
        SURVEY_FOLDER_LIST_URL,
        headers=_headers(),
        json={},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def flatten_folder_names(folder_tree: Any) -> list[str]:
    names: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(folder_tree)
    return names


def get_survey_list_all() -> list[dict[str, Any]]:
    response = requests.post(
        SURVEY_LIST_URL,
        headers=_headers(),
        json={},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise AnketologError(f"Ожидался список анкет, но пришло: {type(data)}")
    return data


def get_survey_list() -> list[dict[str, Any]]:
    surveys = get_survey_list_all()

    surveys_by_id: dict[int, dict[str, Any]] = {}
    for survey in surveys:
        survey_id = survey.get("id")
        if survey_id is not None:
            surveys_by_id[survey_id] = survey

    return list(surveys_by_id.values())


def find_survey_by_name(surveys: list[dict[str, Any]], survey_name: str) -> dict[str, Any]:
    exact_matches = []
    partial_matches = []
    normalized_search = normalize_survey_name(survey_name)

    for survey in surveys:
        current_name = (survey.get("settings") or {}).get("name")
        if not current_name:
            continue

        normalized_current_name = normalize_survey_name(current_name)

        if current_name == survey_name or normalized_current_name == normalized_search:
            exact_matches.append(survey)
        elif normalized_search in normalized_current_name:
            partial_matches.append(survey)

    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(exact_matches) > 1:
        raise AnketologError(
            "Найдено несколько анкет с точным совпадением: "
            + ", ".join([f'{s.get("id")}:{(s.get("settings") or {}).get("name")}' for s in exact_matches])
        )

    if len(partial_matches) == 1:
        return partial_matches[0]

    if len(partial_matches) > 1:
        raise AnketologError(
            "Найдено несколько анкет с частичным совпадением: "
            + ", ".join([f'{s.get("id")}:{(s.get("settings") or {}).get("name")}' for s in partial_matches])
        )

    raise AnketologError(f'Анкета с названием "{survey_name}" не найдена.')


def get_folder_hint() -> str:
    try:
        folder_names = flatten_folder_names(get_survey_folders())
    except requests.RequestException:
        return ""

    if not folder_names:
        return ""

    return f" Доступные папки: {', '.join(folder_names[:20])}."


def locate_survey_by_name(survey_name: str) -> dict[str, Any]:
    surveys = get_survey_list()
    if not surveys:
        raise AnketologError("Не удалось получить список анкет из Anketolog.")

    try:
        return find_survey_by_name(surveys, survey_name)
    except AnketologError as error:
        message = str(error)
        if "не найдена" in message:
            raise AnketologError(message + get_folder_hint())
        raise


def create_report(survey_id: int) -> dict[str, Any]:
    response = requests.post(
        SURVEY_REPORT_CREATE_URL,
        headers=_headers(),
        json={"survey_id": survey_id, "format": REPORT_FORMAT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise AnketologError("Не удалось создать отчет: неверный формат ответа.")
    return data


def get_report_list(survey_id: int) -> list[dict[str, Any]]:
    response = requests.post(
        SURVEY_REPORT_LIST_URL,
        headers=_headers(),
        json={"survey_id": survey_id},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise AnketologError("Не удалось получить список отчетов.")
    return data


def find_report_by_id(report_list: list[dict[str, Any]], report_id: int) -> dict[str, Any] | None:
    for report in report_list:
        if report.get("id") == report_id:
            return report
    return None


def wait_until_report_ready(survey_id: int, report_id: int) -> dict[str, Any]:
    for _ in range(MAX_POLLS):
        report_list = get_report_list(survey_id)
        report = find_report_by_id(report_list, report_id)

        if not report:
            time.sleep(POLL_INTERVAL)
            continue

        status = report.get("status")
        url = report.get("url")

        if status == "complete" and url:
            return report

        if status == "fail":
            raise AnketologError("Формирование отчета завершилось с ошибкой.")

        time.sleep(POLL_INTERVAL)

    raise AnketologError("Отчет не стал готовым за отведенное время.")


def download_file(url: str, filename: str) -> str:
    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
        "Referer": "https://anketolog.ru/",
        "Connection": "keep-alive",
    }

    last_error: Exception | None = None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            with requests.Session() as session:
                with session.get(
                    url,
                    headers=browser_headers,
                    stream=True,
                    allow_redirects=True,
                    timeout=DOWNLOAD_TIMEOUT,
                ) as response:
                    response.raise_for_status()
                    with open(filename, "wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                file_obj.write(chunk)
            return filename
        except requests.RequestException as error:
            last_error = error
            if attempt == DOWNLOAD_RETRIES:
                break
            time.sleep(DOWNLOAD_RETRY_DELAY)

    raise AnketologError(f"Не удалось скачать отчет по ссылке: {last_error}")


def download_report_by_survey_name(survey_name: str) -> tuple[str, str]:
    survey = locate_survey_by_name(survey_name)
    survey_id = survey.get("id")
    survey_real_name = (survey.get("settings") or {}).get("name") or survey_name

    report = create_report(survey_id)
    report_id = report.get("id")
    report_status = report.get("status")
    report_url = report.get("url")

    if report_status == "complete" and report_url:
        ready_format = report.get("format", REPORT_FORMAT)
        ext = get_extension(ready_format)
        filename = os.path.join(config.download_dir, f"{sanitize_filename(survey_real_name)}_{survey_id}.{ext}")
        return download_file(report_url, filename), survey_real_name

    ready_report = wait_until_report_ready(survey_id, report_id)
    ready_url = ready_report.get("url")
    ready_format = ready_report.get("format", REPORT_FORMAT)

    if not ready_url:
        raise AnketologError("Отчет помечен как готовый, но URL отсутствует.")

    ext = get_extension(ready_format)
    filename = os.path.join(config.download_dir, f"{sanitize_filename(survey_real_name)}_{survey_id}.{ext}")
    return download_file(ready_url, filename), survey_real_name
