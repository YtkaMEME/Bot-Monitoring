import os
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple

import aiohttp

from config.config import config


YANDEX_API_BASE = "https://cloud-api.yandex.net/v1/disk"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=120)
PUBLIC_LINK_RETRIES = 10
PUBLIC_LINK_RETRY_DELAY = 2


class YandexDiskError(Exception):
    """Ошибка при работе с API Яндекс.Диска."""


class YandexDiskClient:
    def __init__(self, token: str) -> None:
        self._token = token

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        expected_statuses: Tuple[int, ...] = (200,),
    ) -> dict:
        url = f"{YANDEX_API_BASE}{endpoint}"
        async with session.request(method, url, params=params) as response:
            if response.status not in expected_statuses:
                text = await response.text()
                raise YandexDiskError(f"{method} {endpoint}: {response.status} {text}")
            if response.content_type == "application/json":
                return await response.json()
            return {}

    async def ensure_folder(self, session: aiohttp.ClientSession, path: str) -> None:
        # Если папки нет, создаем ее
        await self._request_json(
            session,
            "PUT",
            "/resources",
            params={"path": path},
            expected_statuses=(201, 409),
        )

    async def upload_file(
        self,
        session: aiohttp.ClientSession,
        local_path: str,
        remote_path: str,
        overwrite: bool = True,
    ) -> None:
        data = await self._request_json(
            session,
            "GET",
            "/resources/upload",
            params={"path": remote_path, "overwrite": "true" if overwrite else "false"},
            expected_statuses=(200,),
        )
        href = data.get("href")
        if not href:
            raise YandexDiskError("Пустая ссылка загрузки от Яндекс.Диска")

        with open(local_path, "rb") as file_obj:
            async with session.put(href, data=file_obj) as response:
                if response.status not in (201, 202):
                    text = await response.text()
                    raise YandexDiskError(f"PUT upload href: {response.status} {text}")

    async def publish_and_get_link(self, session: aiohttp.ClientSession, remote_path: str) -> str:
        for attempt in range(1, PUBLIC_LINK_RETRIES + 1):
            resource_data = await self._request_json(
                session,
                "GET",
                "/resources",
                params={"path": remote_path},
                expected_statuses=(200,),
            )
            public_url = resource_data.get("public_url")
            if public_url:
                return public_url

            if attempt == 1:
                await self._request_json(
                    session,
                    "PUT",
                    "/resources/publish",
                    params={"path": remote_path},
                    expected_statuses=(200, 202),
                )

            if attempt < PUBLIC_LINK_RETRIES:
                await asyncio.sleep(PUBLIC_LINK_RETRY_DELAY)

        raise YandexDiskError("Не удалось получить публичную ссылку на файл")

    async def resource_exists(self, session: aiohttp.ClientSession, remote_path: str) -> bool:
        url = f"{YANDEX_API_BASE}/resources"
        async with session.get(url, params={"path": remote_path}) as response:
            if response.status == 200:
                return True
            if response.status == 404:
                return False
            text = await response.text()
            raise YandexDiskError(f"GET /resources: {response.status} {text}")

    async def upload_file_and_get_public_link(
        self,
        session: aiohttp.ClientSession,
        local_path: str,
        remote_folder: str,
        overwrite: bool = True,
        remote_name: Optional[str] = None,
    ) -> str:
        file_name = remote_name or os.path.basename(local_path)
        remote_path = f"{remote_folder.rstrip('/')}/{file_name}"
        await self.ensure_folder(session, remote_folder)
        await self.upload_file(session, local_path, remote_path, overwrite=overwrite)
        return await self.publish_and_get_link(session, remote_path)


def build_timestamped_name(file_name: str) -> str:
    base, ext = os.path.splitext(file_name)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{stamp}{ext}"


async def upload_files_to_yandex(file_paths: List[str]) -> Optional[List[Tuple[str, str]]]:
    """
    Загружает файлы на Яндекс.Диск.

    Returns:
        Список кортежей (имя_файла, публичная_ссылка) или None, если интеграция не настроена.
    """
    if not config.yandex_disk_token:
        return None

    headers = {"Authorization": f"OAuth {config.yandex_disk_token}"}
    client = YandexDiskClient(config.yandex_disk_token)
    uploaded_links: List[Tuple[str, str]] = []

    async with aiohttp.ClientSession(headers=headers, timeout=REQUEST_TIMEOUT) as session:
        for local_path in file_paths:
            link = await client.upload_file_and_get_public_link(
                session,
                local_path=local_path,
                remote_folder=config.yandex_reports_folder,
            )
            uploaded_links.append((os.path.basename(local_path), link))

    return uploaded_links


async def check_file_exists_on_yandex(file_name: str) -> Optional[bool]:
    if not config.yandex_disk_token:
        return None

    headers = {"Authorization": f"OAuth {config.yandex_disk_token}"}
    client = YandexDiskClient(config.yandex_disk_token)
    remote_path = f"{config.yandex_reports_folder.rstrip('/')}/{file_name}"
    async with aiohttp.ClientSession(headers=headers, timeout=REQUEST_TIMEOUT) as session:
        return await client.resource_exists(session, remote_path)


async def upload_single_file_to_yandex(
    local_path: str,
    overwrite: bool = True,
    remote_name: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """
    Загружает один файл на Яндекс.Диск.

    Returns:
        (имя_файла_на_диске, public_url) или None, если токен не настроен.
    """
    if not config.yandex_disk_token:
        return None

    headers = {"Authorization": f"OAuth {config.yandex_disk_token}"}
    client = YandexDiskClient(config.yandex_disk_token)
    async with aiohttp.ClientSession(headers=headers, timeout=REQUEST_TIMEOUT) as session:
        link = await client.upload_file_and_get_public_link(
            session=session,
            local_path=local_path,
            remote_folder=config.yandex_reports_folder,
            overwrite=overwrite,
            remote_name=remote_name,
        )
    uploaded_name = remote_name or os.path.basename(local_path)
    return uploaded_name, link
