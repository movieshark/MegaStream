# MegaStream

Experimental mega.co.nz streaming client for Kodi. Supports the playback of public files for now.

## How does it work?

The content stored on mega(.co).nz is encrypted using AES-128 (CTR mode), therefore Kodi's built-in player can't play it out of the box. This addon contains a small web server that does the decryption on-the-fly. All you have to do is playing this URL as a regular HTTP stream in Kodi:

`http://127.0.0.1:<choosen_port>/decrypt?url=<mega_url>`

You may change the port in the addon settings. The default is `3456`. If the port or the bind address is changed you need to re-enable the addon or restart Kodi for the changes to take effect.

For now the web server is running all the time when the addon is enabled. In the future I plan to make it start only when needed with a proper API or if anyone is interested in contributing, feel free to do so. This is just a proof of concept for now.

## Can I bypass the Mega transfer limits with this?

No. The addon uses the same API as the web client, so the same limits apply (usually around 5 GB per 4 hours per IP in my experience, but it always differs). You can provide a `proxy` query parameter to the URL to use a proxy server for the download. Premium accounts are also supported (untested), for that you either need to set `Mega SID` in the addon settings or provide a `sid` query parameter to the URL. In that case the downloads will be done using the session ID of the given account.

## What platforms are supported?

The addon is written in Python, so it should work on all platforms where Kodi is available. It requires Python 3 for now, but support for Python 2 should be trivial to add. The web server is using the `bottle` library, so it should work on all platforms where it is available. The addon was tested on Linux.

## Safety considerations

The addon exposes a webserver with a user controllable URL. While there is an attempt to restrict access to mega links only and the server is bound to localhost by default, it is still a potential security risk. Use at your own risk. All communication uses plain HTTP for now except the API requests. Yes, even the requested files are downloaded over plain HTTP.