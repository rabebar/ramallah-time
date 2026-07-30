import base64
import hashlib
import os

import requests
from cryptography.fernet import Fernet, InvalidToken


SHIPLY_HOSTS = {
    ('palestine', 'testing'): 'https://stage.shiplylogistics.com/api/v1',
    ('palestine', 'production'): 'https://shiplylogistics.com/api/v1',
    ('jordan', 'testing'): 'https://stagejordan.shiplylogistics.com/api/v1',
    ('jordan', 'production'): 'https://jordan.shiplylogistics.com/api/v1',
}


def _fernet():
    secret = os.environ.get('SHIPPING_ENCRYPTION_KEY') or os.environ.get('SECRET_KEY')
    if not secret:
        raise RuntimeError('SHIPPING_ENCRYPTION_KEY or SECRET_KEY must be configured')
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode('utf-8')).digest())
    return Fernet(key)


def encrypt_api_key(api_key):
    return _fernet().encrypt(api_key.strip().encode('utf-8')).decode('ascii')


def decrypt_api_key(encrypted_api_key):
    if not encrypted_api_key:
        return None
    try:
        return _fernet().decrypt(encrypted_api_key.encode('ascii')).decode('utf-8')
    except InvalidToken as exc:
        raise RuntimeError('تعذر قراءة مفتاح الشحن المحفوظ') from exc


class ShiplyError(Exception):
    pass


class ShiplyClient:
    def __init__(self, api_key, country='palestine', environment='testing'):
        self.api_key = api_key
        self.base_url = SHIPLY_HOSTS.get((country, environment))
        if not self.base_url:
            raise ShiplyError('بيئة Shiply أو الدولة غير مدعومة')

    def request(self, method, path, payload=None):
        body = dict(payload or {})
        body['Shiply_API_KEY'] = self.api_key
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                json=body,
                headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
                timeout=15,
            )
        except requests.RequestException as exc:
            raise ShiplyError('تعذر الاتصال بخوادم Shiply') from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise ShiplyError('استجابة غير صالحة من Shiply') from exc

        if response.status_code >= 400:
            message = data.get('error') if isinstance(data, dict) else None
            raise ShiplyError(message or f"Shiply HTTP {response.status_code}")
        if isinstance(data, dict) and data.get('success') is False:
            errors = data.get('errors') or [data.get('error')] or ['فشلت العملية لدى Shiply']
            raise ShiplyError('، '.join(str(error) for error in errors if error))
        return data

    def cities(self):
        return self.request('POST', '/address/getCitiesAndVillages')

    def fees(self, village_id, price):
        return self.request('POST', '/parcels/fees', {
            'village_id': int(village_id),
            'price': price,
        })

    def create_parcel(self, payload):
        return self.request('POST', '/parcels/create', payload)

    def submit_parcel(self, parcel_code):
        return self.request('GET', f"/parcels/assignQRCode/{parcel_code}")

    def cancel_parcel(self, parcel_code):
        return self.request('GET', f"/parcels/cancel/{parcel_code}")

    def get_parcel(self, parcel_code):
        return self.request('GET', f"/parcels/find/{parcel_code}")

    def update_webhook(self, webhook_url):
        return self.request('PUT', '/customer/webhookURL', {
            'webhook_url': webhook_url,
        })
