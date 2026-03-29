"""
music_helper.py - Royalty-free background music for stock videos.
Source: SoundCloud search via yt-dlp (NCS / copyright-free)
Falls back to local background.mp3 if download fails.
"""

import os
import random
import subprocess

FALLBACK = "background.mp3"
TMP_MUSIC = "_bg_music.mp3"

# mood → SoundCloud search queries
MOOD_QUERIES = {
    "upbeat":    ["NCS phonk aggressive no copyright",
                  "NCS release trap beat energetic no copyright",
                  "NCS electronic upbeat 2024 no copyright",
                  "phonk drift no copyright free use NCS",
                  "NCS gaming music energetic no copyright"],
    "dramatic":  ["NCS dark phonk no copyright free",
                  "NCS cinematic dark instrumental no copyright",
                  "NCS aggressive phonk 2024 no copyright",
                  "NCS dark electronic no copyright free use",
                  "dark phonk no copyright NCS release"],
    "calm":      ["lofi hip hop no copyright NCS chill",
                  "NCS lofi chill beats no copyright 2024",
                  "chillhop no copyright free use beats",
                  "NCS ambient chill no copyright instrumental",
                  "lofi study beats NCS no copyright free"],
    "corporate": ["NCS motivational no copyright inspiring",
                  "NCS future bass uplifting no copyright",
                  "NCS corporate background music no copyright",
                  "NCS electronic motivational 2024 free",
                  "uplifting background music NCS no copyright"],
}

VIDEO_MOODS = {
    "trending_gainer": "upbeat",
    "trending_loser":  "dramatic",
    "dca":             "calm",
    "loss":            "dramatic",
    "buffett":         "corporate",
}


def _ffmpeg_bin() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def get_music(video_type: str = "dca") -> str:
    """Download a random NCS track from SoundCloud, return local path."""
    mood    = VIDEO_MOODS.get(video_type, "calm")
    queries = MOOD_QUERIES.get(mood, ["NCS instrumental no copyright"])
    query   = f"ytsearch1:{random.choice(queries)}"

    # Temizle
    for f in [TMP_MUSIC, TMP_MUSIC.replace(".mp3", "")]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

    try:
        import yt_dlp
        ydl_opts = {
            "format":          "bestaudio/best",
            "outtmpl":         TMP_MUSIC.replace(".mp3", ""),
            "postprocessors":  [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
            "ffmpeg_location": _ffmpeg_bin(),
            "quiet":           True,
            "no_warnings":     True,
        }
        print(f"  Downloading music ({mood})...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([query])
        if os.path.exists(TMP_MUSIC):
            print("  Music ready.")
            return TMP_MUSIC
    except Exception as e:
        print(f"  Music download error: {e}")

    if os.path.exists(FALLBACK):
        print(f"  Music: fallback {FALLBACK}")
        return FALLBACK

    print("  Music: none available")
    return None


def mix_music_into_video(video_path: str, music_path: str,
                          out_path: str = None, volume: float = 0.08) -> str:
    """
    Mix background music into video using ffmpeg.
    If video has original audio, both are mixed. Otherwise music only.
    """
    video_path = os.path.abspath(video_path)
    music_path = os.path.abspath(music_path)
    if out_path is None:
        out_path = video_path.replace(".mp4", "_music.mp4")
    out_path = os.path.abspath(out_path)

    has_orig = _has_audio(video_path)
    if has_orig:
        fc = (f"[1:a]volume={volume}[bg];"
              f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[out]")
    else:
        fc = f"[1:a]volume={volume}[out]"

    cmd = [
        _ffmpeg_bin(), "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", music_path,
        "-filter_complex", fc,
        "-map", "0:v",
        "-map", "[out]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and os.path.exists(out_path):
        try: os.remove(video_path)
        except: pass
        return out_path
    else:
        print(f"  ffmpeg error: {result.stderr[-300:].decode(errors='ignore')}")
        return _compress_only(video_path, out_path)


def _has_audio(path: str) -> bool:
    """Video'da ses stream'i var mı?"""
    try:
        r = subprocess.run(
            [_ffmpeg_bin(), "-i", path],
            capture_output=True
        )
        return "Audio:" in r.stderr.decode(errors="ignore")
    except Exception:
        return False


def _video_duration(path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    try:
        ffprobe = _ffmpeg_bin().replace("ffmpeg", "ffprobe")
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
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
        [_ffmpeg_bin(), "-y", "-i", src,
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
