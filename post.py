"""Render an HTML design to an image and publish it to Instagram.

Usage:
  python post.py render posts/my-post.html            -> posts/my-post.jpg
  python post.py publish <public-image-url> "caption"  -> posts it to Instagram
  python post.py check                                 -> confirms the token works

Needs the IG_ACCESS_TOKEN environment variable (from Meta's "Generate access tokens").
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import requests
from PIL import Image

API = "https://graph.instagram.com/v23.0"
CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
WIDTH, HEIGHT = 1080, 1350  # Instagram 4:5 portrait, the largest feed size


def token():
    t = os.environ.get("IG_ACCESS_TOKEN")
    if not t:
        sys.exit("IG_ACCESS_TOKEN is not set.")
    return t


def api(method, path, **params):
    params["access_token"] = token()
    r = requests.request(method, f"{API}/{path}", params=params, timeout=60)
    data = r.json()
    if "error" in data:
        sys.exit(f"Instagram API error: {data['error'].get('message')}")
    return data


def check():
    me = api("GET", "me", fields="user_id,username,account_type")
    print(f"Connected to @{me['username']} ({me.get('account_type')})")


def render(html_path):
    html = Path(html_path).resolve()
    png = html.with_suffix(".png")
    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={WIDTH},{HEIGHT + 200}", f"--screenshot={png}", html.as_uri()],
        check=True, capture_output=True,
    )
    # Headless Chrome's viewport is shorter than the window, so render tall and crop.
    # Instagram only accepts JPEG for image posts.
    jpg = html.with_suffix(".jpg")
    Image.open(png).convert("RGB").crop((0, 0, WIDTH, HEIGHT)).save(jpg, quality=95)
    png.unlink()
    print(jpg)
    return jpg


def publish(image_url, caption):
    container = api("POST", "me/media", image_url=image_url, caption=caption)["id"]
    for _ in range(30):
        status = api("GET", container, fields="status_code")["status_code"]
        if status == "FINISHED":
            break
        if status == "ERROR":
            sys.exit("Instagram could not process the image.")
        time.sleep(2)
    media_id = api("POST", "me/media_publish", creation_id=container)["id"]
    link = api("GET", media_id, fields="permalink").get("permalink")
    print(f"Posted: {link}")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "check":
        check()
    elif cmd == "render" and len(args) == 1:
        render(args[0])
    elif cmd == "publish" and len(args) == 2:
        publish(*args)
    else:
        print(__doc__)
