"""
Send a local file to WeChat via the ilink API.

Required env vars (from .env):
  ILINK_TOKEN   – ilink auth token (keep secret, never commit)
  WECHAT_UID    – target WeChat user UID

ilink flow:
  1. POST /bot/getuploadurl  → upload_url + upload_params
  2. POST upload_url (multipart, AES-ECB encrypted payload) → x-encrypted-param header
  3. POST /bot/sendmessage with x-encrypted-param → delivers file to WeChat
"""
import os
import json
import struct
import hashlib
import mimetypes
import requests
from pathlib import Path

ILINK_BASE = "https://ilinkai.weixin.qq.com"
BLOCK_SIZE = 16


def _pad(data: bytes) -> bytes:
    pad_len = BLOCK_SIZE - len(data) % BLOCK_SIZE
    return data + bytes([pad_len] * pad_len)


def _aes_ecb_encrypt(key: bytes, plaintext: bytes) -> bytes:
    from Crypto.Cipher import AES
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(_pad(plaintext))


def _derive_key(token: str) -> bytes:
    return hashlib.md5(token.encode()).digest()


def send_file(file_path: str) -> bool:
    token = os.environ.get("ILINK_TOKEN", "")
    uid = os.environ.get("WECHAT_UID", "")
    if not token or not uid:
        raise EnvironmentError("ILINK_TOKEN and WECHAT_UID must be set in environment.")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_bytes = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Step 1: get upload URL
    r = requests.post(
        f"{ILINK_BASE}/bot/getuploadurl",
        headers=headers,
        json={"filename": path.name, "size": len(file_bytes)},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    upload_url: str = data["upload_url"]
    upload_params: dict = data.get("upload_params", {})

    # Step 2: encrypt and upload
    key = _derive_key(token)
    encrypted = _aes_ecb_encrypt(key, file_bytes)

    upload_resp = requests.post(
        upload_url,
        files={"file": (path.name, encrypted, mime_type)},
        data=upload_params,
        timeout=60,
    )
    upload_resp.raise_for_status()
    x_enc_param = upload_resp.headers.get("x-encrypted-param", "")

    # Step 3: send to WeChat user
    send_resp = requests.post(
        f"{ILINK_BASE}/bot/sendmessage",
        headers=headers,
        json={
            "to_user": uid,
            "msg_type": "file",
            "x_encrypted_param": x_enc_param,
            "filename": path.name,
        },
        timeout=30,
    )
    send_resp.raise_for_status()
    result = send_resp.json()
    return result.get("errcode", -1) == 0
