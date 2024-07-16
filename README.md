# MegaStream

Experimental mega.co.nz streaming client for Kodi. Supports the playback of public files for now.

## How does it work?

The content stored on mega(.co).nz is encrypted using AES-128 (CTR mode), therefore Kodi's built-in player can't play it out of the box. This addon contains a small web server that does the decryption on-the-fly.

## I am a developer, how can I use this?

First import the module in your `addon.xml` file:

```xml
<import addon="script.megastream" version="0.7.1"/>
```

Then you have two options.

1. If you want more control of the list item being played (useful, if you want to set your own cover art, title etc), you need to import the module as a library:

```python
import megastream

listitem = xbmcgui.ListItem("Test")
megastream.init_and_play("https://mega.nz/file/...#...", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 GLS/100.10.9939.100", listitem)
```

`init_and_play` also has optional keyword-only arguments `sid` and `proxy` for premium accounts and proxy servers respectively.

The script will then read its own settings, read the port range the user has set and starts a web server on a random port in that range. Once the webserver is spawned in a thread, it will call `xbmc.Player().play` with the URL of the temporary web server. Once the playback is finished, the web server will be stopped.

2. If you don't need to create your own listitem and don't want to use this as a module the add-on also call the `plugin://` URL directly:

```
plugin://script.megastream/?url=https%3A%2F%2Fmega.nz%2Ffile%2F...%23...&user_agent=Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F125.0.0.0%20Safari%2F537.36%20GLS%2F100.10.9939.100&action=play
```

`sid` and `proxy` can be provided as query parameters as well. `action=play` is required.

In this case the module will create a listitem and it will only set a title, which is going to be the file name obtained from the mega API. No coverart or any other metadata is set.

## Can I bypass the Mega transfer limits with this?

No. The addon uses the same API as the web client, so the [same limits](https://help.mega.io/plans-storage/space-storage/transfer-quota) apply (usually around 5 GB per 6 hours per IP in my experience, but it always differs). You can provide a `proxy` parameter (see above). Premium accounts are also supported (untested), for that you either need to set `Mega SID` in the addon settings or provide a `sid` parameter (see above). In that case the downloads will be done using the session ID of the given account.

## What platforms are supported?

The addon is written in Python, so it should work on all platforms where Kodi is available. It requires Python 3 for now, but support for Python 2 should be trivial to add. The web server is using the `bottle` library, so it should work on all platforms where it is available. The addon was tested on Linux.

## Safety considerations

The addon exposes a webserver with a user controllable URL. While there is an attempt to restrict access to mega links only and the server is bound to localhost by default, it is still a potential security risk. Use at your own risk. All communication uses plain HTTP for now except the API requests. Yes, even the requested files are downloaded over plain HTTP.

## My playback silently fails after some time. What to do?

Currently there is not much error handling in the addon. If the playback fails, check the log file for any errors. You probably used up your transfer quota. If you are using a proxy, check if it is still working. If you are using a SID, check if it is still valid. Logs can contain errors, even if Kodi doesn't prompt you with a notification, so always check the log file.