import threading
from random import randint
from re import match
from socketserver import ThreadingMixIn
from unicodedata import normalize
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import requests
import xbmc
import xbmcaddon
from bottle import default_app, hook, request, response, route
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from . import get_file_info


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
    try:
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

        try:
            data = get_file_info(url, headers, sid, proxy)
            key = data["key"]
            iv = data["iv"]
            data = data["data"]
        except ValueError as e:
            response.status = 400
            response.set_header("Content-Type", "text/plain")
            yield str(e)
            return

        url = data["g"]

        ext = data["at"]["n"].split(".")
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
            "Content-Disposition", f'attachment; filename="{data["at"]["n"]}"'
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
                response.set_header("Content-Range", f"bytes {start}-{end}/{data['s']}")
                response.set_header(
                    "Content-Length", int(data["s"]) - (start - actual_start)
                )
            else:
                yield "Invalid Range header"
        else:
            response.set_header("Content-Length", data["s"])
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
    except Exception as e:
        import traceback

        traceback.print_exc()
        response.status = 500
        response.set_header("Content-Type", "text/plain")
        yield traceback.format_exc()


class WebServerThread(threading.Thread):
    def __init__(self, httpd: WSGIServer, port: int):
        threading.Thread.__init__(self)
        self.web_killed = threading.Event()
        self.httpd = httpd
        self.port = port

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
    minport = addon.getSettingInt("minport")
    maxport = addon.getSettingInt("maxport")
    if minport > maxport or minport < 1024 or maxport > 65535:
        raise ValueError("Invalid port range")
    tries = 0
    while tries < 10:
        port = randint(minport, maxport)
        xbmc.log(f"{handle} Trying port {port} ({tries})...", xbmc.LOGINFO)
        try:
            httpd = make_server(
                addon.getSetting("webaddress"),
                port,
                app,
                server_class=ThreadedWSGIServer,
                handler_class=SilentWSGIRequestHandler,
            )
            break
        except OSError as e:
            if e.errno == 98:
                tries += 1
                xbmc.log(
                    f"{handle} Web service: port {port} already in use",
                    xbmc.LOGERROR,
                )
                return
            raise
    if tries == 10:
        xbmc.log(f"{handle} Web service: no available ports", xbmc.LOGERROR)
        raise OSError("No available ports")

    xbmc.log(f"{handle} Web service starting", xbmc.LOGINFO)
    web_thread = WebServerThread(httpd, port)
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
