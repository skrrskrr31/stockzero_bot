"""
tts_helper.py - Text-to-speech and audio/video merging utilities
Uses gTTS (Google TTS, free) + ffmpeg for merging
"""

import os
import subprocess
import tempfile


def generate_tts(text: str, out_mp3: str) -> str:
    """Generate speech MP3 from text using gTTS."""
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(out_mp3)
    return out_mp3


def merge_audio_video(video_path: str, audio_path: str, out_path: str,
                      audio_delay_ms: int = 0) -> str:
    """
    Merge silent video with audio.
    Uses moviepy (works everywhere); falls back gracefully on error.
    audio_delay_ms: delay before audio starts (milliseconds).
    """
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
        video = VideoFileClip(video_path)
        audio = AudioFileClip(audio_path)

        if audio_delay_ms > 0:
            audio = audio.set_start(audio_delay_ms / 1000.0)

        # Pad audio to video length by looping if needed, or just use as-is
        audio = audio.set_duration(min(audio.duration, video.duration))
        video = video.set_audio(audio)

        video.write_videofile(
            out_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            verbose=False,
            logger=None,
        )
        video.close()
        audio.close()
        return out_path

    except Exception as e:
        print(f"[TTS] merge failed ({e}), returning video without audio")
        return video_path


def build_narration(ticker: str, company: str, investment: float, years: int) -> str:
    """
    Short intro narration — does NOT reveal final value.
    Viewer has to watch the chart to find out.
    """
    inv_str = f"{int(investment):,}"
    return (
        f"What if you had invested {inv_str} dollars in {company} "
        f"{years} years ago? Watch the chart."
    )


def build_race_narration(sector_label: str, investment: float, years: int) -> str:
    """Short intro narration for the bar chart race — no spoilers."""
    inv_str = f"{int(investment):,}"
    return (
        f"{inv_str} dollars invested in every {sector_label} stock "
        f"{years} years ago. Which one won?"
    )


def _format_value_spoken(v: float) -> str:
    """Format a dollar value for natural speech."""
    if v >= 1_000_000:
        m = v / 1_000_000
        return f"{m:.1f} million dollars"
    elif v >= 1_000:
        k = v / 1_000
        return f"{k:.0f} thousand dollars"
    return f"{v:.0f} dollars"
