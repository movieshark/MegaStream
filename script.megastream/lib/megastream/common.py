from base64 import urlsafe_b64decode
from json import loads
from re import match
from struct import pack, unpack

import requests
from Cryptodome.Cipher import AES

from .constants import MEGA_API


def get_file_info(url, headers, sid=None, proxy=None):
    match_url = match(
        r"^https?://mega(?:\.co)?\.nz/file/([A-Za-z0-9_-]+)[#!]([A-Za-z0-9_-]+)$",
        url,
    )
    if not match_url:
        raise ValueError("Invalid MEGA URL")
    file_id, file_key = match_url.groups()
    key = urlsafe_b64decode(file_key + "==")
    key = key.ljust(4 * ((len(key) + 3) // 4), b"\0")
    key = list(unpack(f"!{len(key)//4}L", key))
    iv = key[4:6] + [0, 0]
    key_len = len(key)
    if key_len == 4:
        k = [key[0], key[1], key[2], key[3]]
    elif key_len == 8:
        k = [key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7]]
    else:
        raise ValueError("Invalid key, please verify your MEGA url.")
    key = pack("!4L", *k)
    iv = pack("!4L", *iv)

    json_data = [{"a": "g", "g": 1, "p": file_id}]
    params = {"id": 0, "lang": "en", "domain": "meganz"}
    if sid:
        params["sid"] = sid
    if proxy:
        r = requests.post(
            MEGA_API, headers=headers, json=json_data, proxies=proxy, params=params
        ).json()
    else:
        r = requests.post(
            MEGA_API, headers=headers, json=json_data, params=params
        ).json()
    if not isinstance(r[0], dict) or "at" not in r[0] or "g" not in r[0]:
        raise ValueError("Mega API response is invalid")
    cipher = AES.new(key, AES.MODE_CBC, b"\0" * 16)
    plaintext = cipher.decrypt(urlsafe_b64decode(r[0]["at"] + "=="))
    r[0]["at"] = loads(plaintext.replace(b"\0", b"")[4:].decode())

    return {
        "data": r[0],
        "key": key,
        "iv": iv,
    }
