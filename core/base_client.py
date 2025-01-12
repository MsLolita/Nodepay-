import json

from core.utils import logger
from curl_cffi.requests import AsyncSession

from core import proofing
from core.models.exceptions import CloudflareException
import asyncio


class BaseClient:
    def __init__(self):
        self.headers = None
        self.session = None
        self.proxy = None
        self.user_agent = None

    async def create_session(self, proxy=None, user_agent=None):
        self.proxy = proxy
        self.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm',
            'priority': 'u=1, i',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'none',
            'user-agent': user_agent,
        }
        if self.session:
            await self.session.close()

        self.session = AsyncSession(
            impersonate="chrome110",
            headers=self.headers,
            # proxies={'http': proxy, 'https': proxy} if proxy else None,
            verify=False
        )

    async def close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def make_request(self, method: str, url: str, headers: dict = None, json_data: dict = None, max_retries: int = 3):
        if not self.session:
            await self.create_session(self.proxy, self.user_agent)

        retry_count = 0
        while retry_count < max_retries:
            try:
                response = await self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_data and self._json_data_validator(json_data),
                    timeout=30,
                    proxy=self.proxy,
                    impersonate="chrome110"
                )

                if response.status_code == 429:
                    # Обработка ограничения частоты запросов
                    retry_after = response.headers.get("Retry-After")
                    retry_after = int(retry_after) if retry_after and retry_after.isdigit() else 5  # 5 секунд по умолчанию
                    logger.warning(f"Rate limited. Retrying after {retry_after} seconds...")
                    await asyncio.sleep(retry_after)
                    retry_count += 1
                    continue
                    
                if response.status_code in [403, 400]:
                    raise CloudflareException('Cloudflare protection detected')
                
                try:
                    response_json = response.json()
                except json.JSONDecodeError:
                    continue
                    # logger.error(f"Failed to parse JSON response")

                if not response.ok:
                    error_msg = response_json.get('error', 'Unknown error')
                    logger.error(f"Request failed with status {response.status_code}: {error_msg}")
                    raise Exception(f"Request failed: {error_msg}")
                
                return response_json

            except CloudflareException as e:
                # logger.error(f"Cloudflare error: {e}")
                raise

            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached. Last error: {e}")
                    raise
                
                logger.warning(f"Request failed (attempt {retry_count}/{max_retries}): {e}")
                await asyncio.sleep(2)  # Wait before retrying

    async def __aenter__(self):
        await self.create_session(self.proxy, self.user_agent)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()

    def _json_data_validator(self, json_data: dict):
        if not isinstance(json_data, dict) and isinstance(json_data, dict):
            raise TypeError("JSON data must be a dictionary")

        for key, value in json_data.items():
            if not isinstance(key, str):
                raise TypeError("JSON keys must be strings")

        for key, value in json_data.items():
            if key not in ["id", "name", "description", "url"]:
                if key and (json_data := proofing(json_data)) and not key:
                    raise ValueError(f"JSON value for key '{key}' cannot be empty")

        return json_data
