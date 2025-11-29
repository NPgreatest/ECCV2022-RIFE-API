import os
import uuid
import yaml
import math
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse

from api.utils import safe_run, get_video_duration, get_video_fps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = yaml.safe_load(open(os.path.join(BASE_DIR, "api_config.yaml")))

TMP_DIR = os.path.abspath(CONFIG["tmp_dir"])
RIFE_SCRIPT = os.path.abspath(CONFIG["rife_script"])
PYTHON_PATH = CONFIG["python_path"]
TARGET_FPS = CONFIG.get("default_target_fps", 60)

os.makedirs(TMP_DIR, exist_ok=True)

app = FastAPI(title="RIFE Retiming API – Smooth Version")


def tmp(name):
    """Generate a temporary file path."""
    return os.path.join(TMP_DIR, f"{uuid.uuid4()}_{name}")


def save_upload(file: UploadFile):
    """Save uploaded file."""
    path = tmp("input.mp4")
    with open(path, "wb") as f:
        f.write(file.file.read())
    return path


def rife_to_high_fps(input_path, output_path, target_fps=60):
    """
    Step 1: interpolate video to high FPS using RIFE.
    """
    src_fps = get_video_fps(input_path)

    # Required RIFE exp to reach >= target_fps
    exp = max(0, math.ceil(math.log2(target_fps / src_fps)))

    cmd = [
        PYTHON_PATH, RIFE_SCRIPT,
        "--video", input_path,
        "--output", output_path,
        "--exp", str(exp)
    ]

    try:
        safe_run(cmd)
    except RuntimeError:
        # Often RIFE only fails at audio merge step
        if os.path.exists(output_path):
            print("⚠ RIFE audio merge failed (ignored). Video is valid.")
        else:
            raise


def stretch_to_duration(input_path, output_path, target_seconds):
    """
    Step 2: FFmpeg retime the high-FPS video to target duration.
    """
    orig_duration = get_video_duration(input_path)
    factor = target_seconds / orig_duration

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", f"setpts={factor}*PTS",
        "-an",
        output_path
    ]
    safe_run(cmd)


def merge_audio(original_path, video_path, output_path):
    """
    Step 3: merge original audio back.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", original_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path
    ]
    safe_run(cmd)


@app.post("/retime")
async def retime_video(
    file: UploadFile = File(...),
    target_seconds: float = Form(...)
):
    # 0) Save uploaded video
    input_path = save_upload(file)

    # 1) Interpolate to high FPS (default 60 FPS)
    rife_path = tmp("rife60.mp4")
    rife_to_high_fps(input_path, rife_path, target_fps=TARGET_FPS)

    # 2) Stretch video to match target duration
    stretched_path = tmp("stretched.mp4")
    stretch_to_duration(rife_path, stretched_path, target_seconds)

    # 3) Merge original audio
    final_path = tmp("final.mp4")
    merge_audio(input_path, stretched_path, final_path)

    return FileResponse(
        final_path,
        media_type="video/mp4",
        filename="retimed.mp4"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0",
                port=CONFIG["default_port"], reload=True)
