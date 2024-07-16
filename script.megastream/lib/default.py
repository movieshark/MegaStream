from sys import argv
from urllib.parse import parse_qsl

import xbmc
from megastream import get_file_info, init_and_play
from xbmcgui import ListItem

if __name__ == "__main__":
    params = dict(parse_qsl(argv[2].replace("?", "")))
    action = params.get("action")
    if action == "play":
        xbmc.executebuiltin("Dialog.Close(busydialog)")
        mega_url = params.get("url")
        if not mega_url:
            raise ValueError("Missing 'url' parameter")
        user_agent = params.get("user_agent")
        if not user_agent:
            raise ValueError("Missing 'user_agent' parameter")
        sid = params.get("sid")
        proxy = params.get("proxy")
        info = get_file_info(mega_url, {"User-Agent": user_agent}, sid=sid, proxy=proxy)
        listitem = ListItem(info["data"]["at"]["n"])
        init_and_play(mega_url, user_agent, listitem=listitem, sid=sid, proxy=proxy)
