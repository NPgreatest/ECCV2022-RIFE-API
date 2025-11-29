import subprocess
import json
import re


def safe_run(cmd):
    """
    Run command safely, raise error on failure.
    """
    print("RUNNING:", " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if p.returncode != 0:
        print("STDOUT:", out.decode("utf-8", errors="ignore"))
        print("STDERR:", err.decode("utf-8", errors="ignore"))
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    return out.decode("utf-8", errors="ignore")


def get_video_duration(path):
    """
    Get video duration using ffprobe.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]
    out = safe_run(cmd).strip()
    return float(out)


def get_video_fps(path):
    """
    Get FPS using ffprobe (best-effort).
    """
    cmd = [
        "ffprobe", "-v", "0",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "csv=p=0",
        path
    ]
    out = safe_run(cmd).strip()

    # r_frame_rate returns like "16/1"
    if "/" in out:
        num, den = out.split("/")
        return float(num) / float(den)
    return float(out)
