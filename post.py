"""Render an HTML design to an image and publish it to Instagram.

Usage:
  python post.py render posts/my-post.html            -> posts/my-post.jpg
  python post.py render-video posts/my-reel.html 14    -> posts/my-reel.mp4 (14 seconds)
  python post.py publish <public-image-url> "caption"  -> posts it to Instagram
  python post.py publish-reel <public-video-url> "caption"  -> posts it as a Reel
  python post.py check                                 -> confirms the token works

Needs the IG_ACCESS_TOKEN environment variable (from Meta's "Generate access tokens").
"""
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from PIL import Image

API = "https://graph.instagram.com/v23.0"
CHROME = os.environ.get("CHROME_PATH", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
WIDTH, HEIGHT = 1080, 1350  # Instagram 4:5 portrait, the largest feed size
REEL_WIDTH, REEL_HEIGHT, FPS = 1080, 1920, 30  # Reels are 9:16

# Injected into each video frame: freeze every CSS animation at the frame's time.
FREEZE = """<script>addEventListener("load",()=>{const t=parseFloat(location.hash.slice(1))*1000;
document.getAnimations().forEach(a=>{a.pause();a.currentTime=t})})</script>"""


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


def screenshot(url, png, width, height):
    subprocess.run(
        [CHROME, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         f"--window-size={width},{height + 200}", f"--screenshot={png}", url],
        check=True, capture_output=True,
    )


def render_video(html_path, seconds):
    html = Path(html_path).resolve()
    mp4 = html.with_suffix(".mp4")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        page = tmp / "page.html"
        page.write_text(html.read_text().replace(
            "<head>", f'<head><base href="{html.parent.as_uri()}/">{FREEZE}', 1))

        def frame(i):
            png = tmp / f"{i:05d}.png"
            screenshot(f"{page.as_uri()}#{i / FPS}", png, REEL_WIDTH, REEL_HEIGHT)
            Image.open(png).convert("RGB").crop((0, 0, REEL_WIDTH, REEL_HEIGHT)).save(png)

        total = int(seconds * FPS)
        with ThreadPoolExecutor(os.cpu_count()) as pool:
            for done, _ in enumerate(pool.map(frame, range(total)), 1):
                print(f"\rframe {done}/{total}", end="", file=sys.stderr)
        print(file=sys.stderr)
        # Reels want H.264 + AAC, so add a silent audio track.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", tmp / "%05d.png",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "slow", "-crf", "18",
             "-c:a", "aac", "-movflags", "+faststart", mp4],
            check=True,
        )
    print(mp4)
    return mp4


def wait_until_ready(container, tries):
    for _ in range(tries):
        status = api("GET", container, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status == "ERROR":
            sys.exit("Instagram could not process the media.")
        time.sleep(5)
    sys.exit("Instagram took too long to process the media.")


def publish_reel(video_url, caption):
    container = api("POST", "me/media", media_type="REELS", video_url=video_url, caption=caption)["id"]
    wait_until_ready(container, tries=60)
    media_id = api("POST", "me/media_publish", creation_id=container)["id"]
    link = api("GET", media_id, fields="permalink").get("permalink")
    print(f"Posted: {link}")


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
    elif cmd == "render-video" and len(args) == 2:
        render_video(args[0], float(args[1]))
    elif cmd == "publish" and len(args) == 2:
        publish(*args)
    elif cmd == "publish-reel" and len(args) == 2:
        publish_reel(*args)
    else:
        print(__doc__)
