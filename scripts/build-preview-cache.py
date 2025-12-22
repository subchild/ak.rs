#!/usr/bin/env python3
import json
import re
import time
from urllib import request, error, parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "2025faves" / "index.html"
OUTPUT_PATH = ROOT / "2025faves" / "preview-cache.json"


def load_tracks_by_category():
    html = HTML_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"const tracksByCategory = ([\s\S]*?);\n\s*const defaultClipStart",
        html,
    )
    if not match:
        raise RuntimeError("Could not locate tracksByCategory in index.html")
    block = match.group(1)
    block = re.sub(r"/\*[\s\S]*?\*/", "", block)
    prev = None
    while prev != block:
        prev = block
        block = re.sub(r",(\s*[}\]])", r"\1", block)
    block = re.sub(r'([{\[,]\s*)([A-Za-z0-9_]+)\s*:', r'\1"\2":', block)
    return json.loads(block)


def build_preview_key(track):
    return f'{track["artist"]}||{track["title"]}'.lower()


def build_api_url(track):
    if "appleId" in track:
        return (
            "https://itunes.apple.com/lookup?id="
            + parse.quote(str(track["appleId"]))
            + "&entity=song"
        )
    query = f'{track["title"]} {track["artist"]}'
    if "album" in track:
        query += f' {track["album"]}'
    return (
        "https://itunes.apple.com/search?term="
        + parse.quote(query)
        + "&media=music&entity=song&limit=1"
    )


def fetch_json_with_retry(url, retries=3, delay_s=0.5):
    headers = {"User-Agent": "akrs-preview-cache/1.0"}
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 429 and retries > 0:
            time.sleep(delay_s)
            return fetch_json_with_retry(url, retries - 1, delay_s * 2)
        if retries > 0:
            time.sleep(delay_s)
            return fetch_json_with_retry(url, retries - 1, delay_s * 2)
        raise


def main():
    tracks_by_category = load_tracks_by_category()
    all_tracks = []
    for tracks in tracks_by_category.values():
        all_tracks.extend(tracks)

    items = {}
    for track in all_tracks:
        key = build_preview_key(track)
        if key in items:
            continue
        url = build_api_url(track)
        try:
            data = fetch_json_with_retry(url)
            resolved = data.get("results", [None])[0]
            if resolved:
                items[key] = resolved
            else:
                print(f'No preview for {track["artist"]} - {track["title"]}')
        except Exception as exc:
            print(f'Failed for {track["artist"]} - {track["title"]}: {exc}')
        time.sleep(0.35)

    payload = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "items": items,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
