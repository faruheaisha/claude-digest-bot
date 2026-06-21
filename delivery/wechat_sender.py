"""
Send a local file to WeChat via the ilink API.

Ported from wechat-claude-code dist/wechat/upload.js + send.js.

Required env vars (from .env):
  ILINK_TOKEN   – full botToken string  e.g. "xxxxxxxxxxxx@im.bot:<secret>"
  WECHAT_UID    – target WeChat user UID e.g. "xxxxxxxxxx@im.wechat"
"""
import base64
import hashlib
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode, quote

import requests
from Crypto.Cipher import AES

CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
ILINK_BASE   = "https://ilinkai.weixin.qq.com"
BLOCK        = 16


# ── AES-ECB PKCS7 ────────────────────────────────────────────────────────────

def _pad(data: bytes) -> bytes:
    n = BLOCK - len(data) % BLOCK
    return data + bytes([n] * n)


def _aes_ecb_encrypt(key: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_ECB).encrypt(_pad(data))


def _aes_padded_size(raw: int) -> int:
    return raw + (BLOCK - raw % BLOCK)


# ── ilink API client ──────────────────────────────────────────────────────────

def _make_headers(token: str) -> dict:
    uin = base64.b64encode(secrets.token_bytes(4)).decode()
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "AuthorizationType": "ilink_bot_token",
        "X-WECHAT-UIN": uin,
    }


def _api(path: str, token: str, body: dict, timeout: int = 15) -> dict:
    r = requests.post(
        f"{ILINK_BASE}/{path}",
        headers=_make_headers(token),
        json=body,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


# ── upload ────────────────────────────────────────────────────────────────────

def _upload_file(token: str, to_user_id: str, file_path: str) -> dict:
    path = Path(file_path)
    plaintext = path.read_bytes()
    raw_size   = len(plaintext)
    raw_md5    = hashlib.md5(plaintext).hexdigest()
    file_size  = _aes_padded_size(raw_size)

    file_key   = secrets.token_hex(16)       # 32-hex string
    aes_key    = secrets.token_bytes(16)     # 16 raw bytes
    aes_key_hex = aes_key.hex()             # 32-hex string

    # determine media_type: 1=image, 3=file
    img_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}
    media_type = 1 if path.suffix.lower() in img_exts else 3

    # Step 1 – get upload URL
    resp = _api("ilink/bot/getuploadurl", token, {
        "filekey":      file_key,
        "media_type":   media_type,
        "to_user_id":   to_user_id,
        "rawsize":      raw_size,
        "rawfilemd5":   raw_md5,
        "filesize":     file_size,
        "no_need_thumb": True,
        "aeskey":       aes_key_hex,
        "base_info": {
            "channel_version": "2.0.0",
            "bot_agent":       "claude-digest-bot",
        },
    })

    if not resp.get("upload_full_url") and not resp.get("upload_param"):
        raise RuntimeError(f"getuploadurl failed: {resp}")

    # Step 2 – encrypt and upload to CDN
    encrypted = _aes_ecb_encrypt(aes_key, plaintext)

    if resp.get("upload_full_url"):
        cdn_url = resp["upload_full_url"]
    else:
        cdn_url = (
            f"{CDN_BASE_URL}/upload"
            f"?encrypted_query_param={quote(resp['upload_param'])}"
            f"&filekey={file_key}"
        )

    cdn_resp = requests.post(
        cdn_url,
        data=encrypted,
        headers={"Content-Type": "application/octet-stream"},
        timeout=60,
    )
    cdn_resp.raise_for_status()

    enc_query_param = cdn_resp.headers.get("x-encrypted-param")
    if not enc_query_param:
        raise RuntimeError("CDN upload succeeded but x-encrypted-param header missing")

    # aes_key sent to ilink = base64( hex_string_bytes ), NOT base64(raw_bytes)
    aes_key_b64 = base64.b64encode(aes_key_hex.encode()).decode()

    return {
        "media_type":        media_type,
        "enc_query_param":   enc_query_param,
        "aes_key_b64":       aes_key_b64,
        "file_name":         path.name,
        "file_size":         file_size,
        "raw_size":          raw_size,
    }


# ── send ──────────────────────────────────────────────────────────────────────

def send_file(file_path: str) -> bool:
    token  = os.environ.get("ILINK_TOKEN", "")
    uid    = os.environ.get("WECHAT_UID", "")
    bot_id = token.split(":")[0] if ":" in token else token

    if not token or not uid:
        raise EnvironmentError("ILINK_TOKEN and WECHAT_UID must be set in environment.")

    media = _upload_file(token, uid, file_path)

    client_id = f"digest-{int(time.time() * 1000)}"

    if media["media_type"] == 1:  # image
        item = {
            "type": 2,
            "image_item": {
                "media": {
                    "encrypt_query_param": media["enc_query_param"],
                    "aes_key":             media["aes_key_b64"],
                    "encrypt_type":        1,
                },
                "mid_size": media["file_size"],
            },
        }
    else:  # file
        item = {
            "type": 4,
            "file_item": {
                "media": {
                    "encrypt_query_param": media["enc_query_param"],
                    "aes_key":             media["aes_key_b64"],
                    "encrypt_type":        1,
                },
                "file_name": media["file_name"],
                "len":       str(media["raw_size"]),
            },
        }

    # ilink sendmessage returns {} on success (no ret field), raises on HTTP error
    _api("ilink/bot/sendmessage", token, {
        "msg": {
            "from_user_id":  bot_id,
            "to_user_id":    uid,
            "client_id":     client_id,
            "message_type":  2,   # BOT
            "message_state": 2,   # FINISH
            "context_token": "",
            "item_list":     [item],
        }
    })
    return True
