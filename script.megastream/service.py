import base64
import threading
from json import loads
from re import match
from socketserver import ThreadingMixIn
from struct import pack, unpack
from unicodedata import normalize
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import requests
import xbmc
import xbmcaddon
from bottle import default_app, hook, request, response, route
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

MEGA_API = "https://g.api.mega.co.nz/cs"


class SilentWSGIRequestHandler(WSGIRequestHandler):
    """Custom WSGI Request Handler with logging disabled"""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args, **kwargs):
        """Disable log messages"""
        pass


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    """Multi-threaded WSGI server"""

    allow_reuse_address = True
    daemon_threads = True
    timeout = 1


@hook("before_request")
def set_server_header():
    response.set_header("Server", request.app.config["name"])


@route("/")
def index():
    response.content_type = "text/plain"
    return request.app.config["welcome_text"]


@route("/decrypt")
def decrypt():
    url = request.query.get("url")
    if not url:
        response.status = 400
        response.set_header("Content-Type", "text/plain")
        yield "Invalid URL"
    proxy = request.query.get("proxy")
    if proxy:
        proxy = {"http": proxy, "https": proxy}
    sid = request.query.get("sid")
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        response.status = 400
        response.set_header("Content-Type", "text/plain")
        yield "User-Agent header is missing"
    headers = {"User-Agent": user_agent}

    match_url = match(
        r"^https?://mega(?:\.co)?\.nz/file/([A-Za-z0-9_-]+)[#!]([A-Za-z0-9_-]+)$",
        url,
    )
    if not match_url:
        yield "Invalid MEGA URL"
    file_id, file_key = match_url.groups()
    key = base64.urlsafe_b64decode(file_key + "==")
    key = key.ljust(4 * ((len(key) + 3) // 4), b"\0")
    key = list(unpack(f"!{len(key)//4}L", key))
    iv = key[4:6] + [0, 0]
    key_len = len(key)
    if key_len == 4:
        k = [key[0], key[1], key[2], key[3]]
    elif key_len == 8:
        k = [key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7]]
    else:
        yield "Invalid key, please verify your MEGA url."
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
        response.status = 400
        response.set_header("Content-Type", "text/plain")
        xbmc.log(f"MEGA API response error: {r}", xbmc.LOGERROR)
        yield "MEGA API response error"
    cipher = AES.new(key, AES.MODE_CBC, b"\0" * 16)
    plaintext = cipher.decrypt(base64.urlsafe_b64decode(r[0]["at"] + "=="))
    r[0]["at"] = loads(plaintext.replace(b"\0", b"")[4:].decode())

    url = r[0]["g"]

    ext = r[0]["at"]["n"].split(".")
    if len(ext) > 1:
        ext = ext[-1]
    else:
        ext = "bin"
    if ext == "bin":
        response.set_header("Content-Type", "application/octet-stream")
    elif ext in ["mp4", "webm", "mkv", "avi", "flv", "mov", "wmv", "mpg", "mpeg"]:
        response.set_header("Content-Type", f"video/{ext}")
    elif ext == "m4v":
        response.set_header("Content-Type", "video/mp4")
    elif ext in ["mp3", "wav", "flac", "ogg", "m4a", "wma", "aac"]:
        response.set_header("Content-Type", f"audio/{ext}")
    elif ext in ["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff"]:
        response.set_header("Content-Type", f"image/{ext}")
    else:
        response.set_header("Content-Type", "application/octet-stream")
    response.set_header(
        "Content-Disposition", f'attachment; filename="{r[0]["at"]["n"]}"'
    )

    range_header = request.headers.get("Range")
    if range_header:
        match_range = match(r"bytes=(\d+)-(\d+)?", range_header)
        if match_range:
            start = int(match_range.group(1))
            end = int(match_range.group(2)) if match_range.group(2) else ""
            start_block_num = start // 16
            actual_start = start_block_num * 16
            headers["Range"] = f"bytes={actual_start}-{end}"
            response.set_header("Content-Range", f"bytes {start}-{end}/{r[0]['s']}")
            response.set_header(
                "Content-Length", int(r[0]["s"]) - (start - actual_start)
            )
        else:
            yield "Invalid Range header"
    else:
        response.set_header("Content-Length", r[0]["s"])
        start_block_num = 0

    counter = Counter.new(
        128, initial_value=int.from_bytes(iv, byteorder="big") + start_block_num
    )
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    if proxy:
        r2 = requests.get(url, headers=headers, stream=True, proxies=proxy)
    else:
        r2 = requests.get(url, headers=headers, stream=True)
    response.status = r2.status_code

    first_chunk = True
    for chunk in r2.iter_content(chunk_size=256 * 1024):
        if first_chunk and range_header:
            decrypted_chunk = cipher.decrypt(chunk)[start - actual_start :]
            first_chunk = False
        else:
            decrypted_chunk = cipher.decrypt(chunk)
        yield decrypted_chunk


class WebServerThread(threading.Thread):
    def __init__(self, httpd: WSGIServer):
        threading.Thread.__init__(self)
        self.web_killed = threading.Event()
        self.httpd = httpd

    def run(self):
        while not self.web_killed.is_set():
            self.httpd.handle_request()

    def stop(self):
        self.web_killed.set()


def main_service(addon: xbmcaddon.Addon) -> WebServerThread:
    name = f"{addon.getAddonInfo('name')} v{addon.getAddonInfo('version')}"
    name = normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    handle = f"[{name}]"
    app = default_app()
    welcome_text = f"{name} Web Service"
    app.config["name"] = name
    app.config["welcome_text"] = welcome_text
    try:
        httpd = make_server(
            addon.getSetting("webaddress"),
            addon.getSettingInt("webport"),
            app,
            server_class=ThreadedWSGIServer,
            handler_class=SilentWSGIRequestHandler,
        )
    except OSError as e:
        if e.errno == 98:
            xbmc.log(
                f"{handle} Web service: port {addon.getSetting('webport')} already in use",
                xbmc.LOGERROR,
            )
            return
        raise
    xbmc.log(f"{handle} Web service starting", xbmc.LOGINFO)
    web_thread = WebServerThread(httpd)
    web_thread.start()
    return web_thread


if __name__ == "__main__":
    monitor = xbmc.Monitor()
    addon = xbmcaddon.Addon()
    web_thread = main_service(addon)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    if web_thread and web_thread.is_alive():
        web_thread.stop()
        try:
            web_thread.join()
        except RuntimeError:
            pass
    xbmc.log(f"[{addon.getAddonInfo('name')}] Web service stopped", xbmc.LOGINFO)
