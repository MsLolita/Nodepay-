import time
import uuid
import warnings
import os
import json

from random_username.generate import generate_username
from tenacity import retry, stop_after_attempt, retry_if_not_exception_type

from core.base_client import BaseClient
from core.models.exceptions import LoginError

# Suppress the specific warning
warnings.filterwarnings("ignore", category=UserWarning, message="Curlm alread closed!")


class NodePayClient(BaseClient):
    def __init__(self, email: str = '', password: str = '', proxy: str = '', user_agent: str = ''):
        super().__init__()
        self.email = email
        self.password = password
        self.user_agent = user_agent
        self.proxy = proxy
        self.browser_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, self.proxy or ""))
        self.token_json_db = 'data/tokens_db.json'

    async def __aenter__(self):
        await self.create_session(self.proxy, self.user_agent)
        return self

    async def safe_close(self):
        await self.close_session()

    def _auth_headers(self):
        return {
            # 'accept': '*/*',
            # 'accept-language': 'en-US,en;q=0.9',
            # 'content-type': 'application/json',
            # 'origin': 'chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm',
            # 'priority': 'u=1, i',
            # 'sec-fetch-dest': 'empty',
            # 'sec-fetch-mode': 'cors',
            # 'sec-fetch-site': 'none',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://app.nodepay.ai',
            'priority': 'u=1, i',
            'referer': 'https://app.nodepay.ai/',
            'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        }

    def _ping_headers(self, access_token: str):
        headers = self._auth_headers()
        return headers.update({"Authorization": f"Bearer {access_token}"}) or headers

    async def register(self, ref_code: str, captcha_service):
        captcha_token = await captcha_service.get_captcha_token_async()
        username = generate_username()[0][:20]
        json_data = {
            'email': self.email,
            'password': self.password,
            'username': username,
            'referral_code': ref_code,
            'recaptcha_token': captcha_token
        }

        return await self.make_request(
            method='POST',
            url='https://api.nodepay.org/api/auth/register?',
            headers=self._auth_headers(),
            json_data=json_data
        )

    async def _load_token(self, email: str):
        if not os.path.exists(self.token_json_db):
            with open(self.token_json_db, mode='w') as f:
                f.write(json.dumps({}))
            return False

        with open(self.token_json_db, mode='r') as f:
            content = f.read()
            credentials = json.loads(content)
            account_info = credentials.get(email)
            if not account_info:
                return False
            return account_info.get('uid'), account_info.get('token')

    async def _save_token(self, email: str, uid: str, token: str):
        credentials = {}
        credentials[email] = {
            'uid': uid,
            'token': token
        }
        with open(self.token_json_db, mode='w') as f:
            f.write(json.dumps(credentials))

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_not_exception_type(LoginError)
    )
    async def login(self, captcha_service):
        # Check if token exists and is valid
        account_info = await self._load_token(self.email)
        if account_info:
            uid, token = account_info
            # Verify token validity
            try:
                await self.info(token)
                # print(f'{self.email} | Token is valid')
                return uid, token
            except Exception:
                # print(f'{self.email} | Token is invalid, proceed to get a new one')
                pass

        # Obtain a new token
        captcha_token = await captcha_service.get_captcha_token_async()
        headers = self._auth_headers()

        json_data = {
            'user': self.email,
            'password': self.password,
            'remember_me': True,
            'recaptcha_token': captcha_token
        }

        response = await self.make_request(
            method='POST',
            url='https://api.nodepay.org/api/auth/login',
            headers=headers,
            json_data=json_data
        )

        if not response.get("success"):
            msg = response.get("msg")
            raise LoginError(msg)

        uid = response['data']['user_info']['uid']
        token = response['data']['token']

        # Save the new token
        await self._save_token(self.email, uid, token)

        return uid, token

    async def activate(self, access_token: str):
        json_data = {}
        return await self.make_request(
            method='POST',
            url='https://api.nodepay.org/api/auth/active-account?',
            headers=self._ping_headers(access_token),
            json_data=json_data
        )

    async def info(self, access_token: str):
        response = await self.make_request(
            method='GET',
            url='https://api.nodepay.org/api/earn/info?',
            headers=self._ping_headers(access_token)
        )
        return response['data'].get('total_earning', 0)

    async def ping(self, uid: str, access_token: str):
        json_data = {
            'id': uid,
            'browser_id': self.browser_id,
            'timestamp': int(time.time()),
            'version': '2.2.7'
        }

        await self.make_request(
            method='POST',
            url='https://nw.nodepay.org/api/network/ping',
            headers=self._ping_headers(access_token),
            json_data=json_data
        )
        
        # logger.debug(f'{self.email} | Minning success')
        return await self.info(access_token)
