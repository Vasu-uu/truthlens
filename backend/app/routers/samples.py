"""Built-in demo samples so a demo never depends on uploads."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.main_errors import ApiError
from app.routers.audio import run_audio
from app.routers.image import run_image
from app.routers.message import run_message
from app.schemas import AnalysisResult

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
EXTS = {"image": {".jpg", ".jpeg", ".png", ".webp"}, "audio": {".wav", ".mp3", ".ogg", ".opus", ".m4a"}}

router = APIRouter(prefix="/api", tags=["samples"])


def _catalog() -> dict[str, dict]:
    """Build the sample catalog from disk. `expected` is the sample's provenance, not a measured result."""
    cat: dict[str, dict] = {}
    msgs = SAMPLES_DIR / "messages.json"
    if msgs.exists():
        for m in json.loads(msgs.read_text(encoding="utf-8")):
            cat[m["id"]] = {"id": m["id"], "modality": "message", "title": m["title"], "expected": m["expected"], "text": m["text"]}
    for mod, exts in EXTS.items():
        base = SAMPLES_DIR / mod
        if not base.exists():
            continue
        for sub in sorted(p for p in base.iterdir() if p.is_dir()):
            for f in sorted(sub.iterdir()):
                if f.suffix.lower() in exts:
                    sid = f"{mod}-{sub.name}-{f.stem}".lower().replace(" ", "_")
                    cat[sid] = {"id": sid, "modality": mod, "title": f.stem.replace("_", " ").title(), "expected": sub.name, "path": str(f)}
    return cat


@router.get("/samples")
def list_samples() -> list[dict]:
    """List demo samples (file paths are not exposed)."""
    return [{k: v for k, v in s.items() if k != "path"} for s in _catalog().values()]


@router.get("/samples/{sample_id}/file")
def sample_file(sample_id: str) -> FileResponse:
    """Serve a sample's raw file for previews and playback."""
    s = _catalog().get(sample_id)
    if not s or "path" not in s:
        raise ApiError(404, "sample_not_found", "No such sample file.")
    return FileResponse(s["path"])


@router.post("/analyze/sample/{sample_id}", response_model=AnalysisResult)
def analyze_sample(sample_id: str) -> AnalysisResult:
    """Analyze a built-in sample by id (catalog lookup only; no user-supplied paths)."""
    s = _catalog().get(sample_id)
    if not s:
        raise ApiError(404, "sample_not_found", "No such sample.")
    if s["modality"] == "message":
        return run_message(s["text"])
    data = Path(s["path"]).read_bytes()
    return run_image(data) if s["modality"] == "image" else run_audio(data)
