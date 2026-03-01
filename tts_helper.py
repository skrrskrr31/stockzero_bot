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


MUSIC_FILE = "background.mp3"
MUSIC_VOLUME = 0.25   # background music volume (0.0 - 1.0)


def merge_audio_video(video_path: str, audio_path: str, out_path: str,
                      audio_delay_ms: int = 0) -> str:
    """
    Merge silent video with TTS narration + background music.
    - TTS plays at full volume for the first few seconds
    - Background music loops under the entire video at MUSIC_VOLUME
    Falls back gracefully on error.
    """
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

        video = VideoFileClip(video_path)
        dur   = video.duration

        clips = []

        # TTS narration
        tts = AudioFileClip(audio_path)
        if audio_delay_ms > 0:
            tts = tts.set_start(audio_delay_ms / 1000.0)
        tts = tts.set_duration(min(tts.duration, dur))
        clips.append(tts)

        # Background music — loop to fill entire video
        if os.path.exists(MUSIC_FILE):
            music = AudioFileClip(MUSIC_FILE)
            # Loop if music is shorter than video
            if music.duration < dur:
                loops = int(dur / music.duration) + 1
                from moviepy.audio.fx.audio_loop import audio_loop
                music = audio_loop(music, nloops=loops)
            music = music.set_duration(dur).volumex(MUSIC_VOLUME)
            clips.append(music)

        composite = CompositeAudioClip(clips)
        video = video.set_audio(composite)

        video.write_videofile(
            out_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            verbose=False,
            logger=None,
        )
        video.close()
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
    return f"{inv_str} dollars invested. How did it change in {years} years?"


def _format_value_spoken(v: float) -> str:
    """Format a dollar value for natural speech."""
    if v >= 1_000_000:
        m = v / 1_000_000
        return f"{m:.1f} million dollars"
    elif v >= 1_000:
        k = v / 1_000
        return f"{k:.0f} thousand dollars"
    return f"{v:.0f} dollars"
