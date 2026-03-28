"""
music_helper.py - Royalty-free background music for stock videos.

Source: Pixabay Music API (free, no attribution needed for YouTube)
  → https://pixabay.com/service/about/api/
  → Sign up free → API key → add as GitHub secret PIXABAY_KEY

Falls back to local background.mp3 if no key / API fails.
"""

import os
import random
import subprocess
import requests

CACHE_DIR   = "music_cache"
FALLBACK    = "background.mp3"
API_URL     = "https://pixabay.com/api/music/"

# mood → Pixabay search terms (tried in order until one returns results)
MOOD_QUERIES = {
    "upbeat":    ["upbeat corporate",  "energetic background", "motivational"],
    "dramatic":  ["dramatic cinematic","tense thriller",       "dark tension"],
    "calm":      ["calm background",   "relaxing piano",       "soft ambient"],
    "corporate": ["corporate background","professional piano", "inspiring"],
}

# Video type → mood
VIDEO_MOODS = {
    "trending_gainer": "upbeat",
    "trending_loser":  "dramatic",
    "dca":             "calm",
    "loss":            "dramatic",
    "buffett":         "corporate",
}


def _ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _pixabay_search(key: str, query: str) -> list:
    """Return list of (audio_url, title) from Pixabay music API."""
    try:
        r = requests.get(
            API_URL,
            params={
                "key":          key,
                "q":            query,
                "min_duration": 60,
                "per_page":     20,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        hits = data.get("hits", [])
        results = []
        for h in hits:
            # Pixabay music hit structure
            audio = h.get("audio", {})
            url   = audio.get("mp3", {}).get("url", "") if isinstance(audio, dict) else ""
            if not url:
                # Alternative path
                url = h.get("download", {}).get("url", "")
            if url:
                results.append((url, h.get("title", "track")))
        return results
    except Exception as e:
        print(f"  Pixabay API error: {e}")
        return []


def _download(url: str, dest: str) -> bool:
    """Download URL to dest. Returns True on success."""
    try:
        r = requests.get(url, timeout=30, stream=True)
        if r.status_code == 200:
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"  Download error: {e}")
    return False


def get_music(video_type: str = "dca") -> str:
    """
    Return path to a suitable background music MP3.
    Downloads from Pixabay if PIXABAY_KEY is set, otherwise uses fallback.
    """
    key  = os.environ.get("PIXABAY_KEY", "").strip()
    mood = VIDEO_MOODS.get(video_type, "calm")

    if key:
        _ensure_cache()
        queries = MOOD_QUERIES.get(mood, ["background music"])
        random.shuffle(queries)

        for q in queries:
            hits = _pixabay_search(key, q)
            if not hits:
                continue
            random.shuffle(hits)
            for url, title in hits[:5]:
                safe  = "".join(c if c.isalnum() else "_" for c in title)[:40]
                dest  = os.path.join(CACHE_DIR, f"{safe}.mp3")
                if os.path.exists(dest) and os.path.getsize(dest) > 10_000:
                    print(f"  Music (cached): {title} [{mood}]")
                    return dest
                print(f"  Downloading music: {title}")
                if _download(url, dest):
                    print(f"  Music ready: {title} [{mood}]")
                    return dest

    # Fallback: local background.mp3
    if os.path.exists(FALLBACK):
        print(f"  Music: fallback {FALLBACK}")
        return FALLBACK

    print("  Music: none available")
    return None


def mix_music_into_video(video_path: str, music_path: str,
                          out_path: str = None, volume: float = 0.18) -> str:
    """
    Mix background music into a silent video using ffmpeg.
    Music is looped if shorter than the video. Volume is set to `volume` (0–1).
    Returns path to output file (replaces video_path if out_path is None).
    """
    if out_path is None:
        out_path = video_path.replace(".mp4", "_music.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex",
            f"[1:a]volume={volume}[bg];"
            f"[bg]atrim=0:{_video_duration(video_path)}[bgcut]",
        "-map", "0:v",
        "-map", "[bgcut]",
        "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(out_path):
        if out_path != video_path:
            try:
                os.remove(video_path)
            except Exception:
                pass
        return out_path
    else:
        print(f"  ffmpeg music mix error: {result.stderr[-300:].decode(errors='ignore')}")
        # Fallback: compress without music
        return _compress_only(video_path, out_path)


def _video_duration(path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", path],
            capture_output=True,
        )
        import json
        info = json.loads(r.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return 30.0


def _compress_only(src: str, dst: str) -> str:
    """Compress video without audio."""
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-vcodec", "libx264", "-crf", "22", "-preset", "fast",
         "-an", dst],
        capture_output=True,
    )
    if r.returncode == 0 and os.path.exists(dst):
        try:
            os.remove(src)
        except Exception:
            pass
        return dst
    return src
