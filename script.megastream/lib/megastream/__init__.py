from urllib.parse import urlencode, urljoin

import xbmc
import xbmcaddon

from .common import get_file_info
from .service import main_service


def init_and_play(mega_url, user_agent, listitem, sid=None, proxy=None):
    xbmc.executebuiltin("Dialog.Close(busydialog)")
    monitor = xbmc.Monitor()
    addon = xbmcaddon.Addon(id="script.megastream")

    web_thread = main_service(addon)

    url = "http://127.0.0.1:" + str(web_thread.port)
    params = {"url": mega_url}
    if sid:
        params["sid"] = sid
    if proxy:
        params["proxy"] = proxy

    user_agent = urlencode({"User-Agent": user_agent})

    url = urljoin(url, f"/decrypt?{urlencode(params)}|{user_agent}")

    player = xbmc.Player()
    listitem.setPath(url)
    player.play(url, listitem)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
    if web_thread and web_thread.is_alive():
        web_thread.stop()
        try:
            web_thread.join()
        except RuntimeError:
            pass
    xbmc.log(
        f"[{addon.getAddonInfo('name')}] Web service stopped on port {web_thread.port}",
        xbmc.LOGINFO,
    )
