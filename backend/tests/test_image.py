"""Image detector and endpoint tests (loads the real classifier once)."""
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from app.detectors import image_detector as det
from app.main import app
from app.schemas import AnalysisResult
from app.utils.image_io import load_image

client = TestClient(app)


def _photo(size=(320, 240)) -> Image.Image:
    rng = np.random.default_rng(1)
    base = np.linspace(0, 255, size[0], dtype=np.float32)[None, :, None].repeat(size[1], 0).repeat(3, 2)
    return Image.fromarray(np.clip(base + rng.normal(0, 12, base.shape), 0, 255).astype(np.uint8))


def _bytes(img: Image.Image, fmt="JPEG", **kw) -> bytes:
    b = io.BytesIO()
    img.save(b, format=fmt, **kw)
    return b.getvalue()


def test_label_mapping_by_name():
    assert det._ai_index({0: "artificial", 1: "human"}) == 0
    assert det._ai_index({0: "Real", 1: "Fake"}) == 1


def test_endpoint_valid_image_schema():
    r = client.post("/api/analyze/image", files={"file": ("a.jpg", _bytes(_photo()), "image/jpeg")})
    assert r.status_code == 200, r.text
    res = AnalysisResult(**r.json())
    assert res.modality == "image" and 0 <= res.risk_score <= 100
    assert {"ai_model_score", "exif_missing"} <= {s.id for s in res.signals}
    assert "heatmap_png_base64" in res.artifacts and "ela_png_base64" in res.artifacts
    assert res.limitations and res.next_steps and res.explanation


def test_png_with_generator_metadata_is_high():
    meta = PngImagePlugin.PngInfo()
    meta.add_text("parameters", "a cat\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 123")
    r = client.post("/api/analyze/image", files={"file": ("a.png", _bytes(_photo(), "PNG", pnginfo=meta), "image/png")})
    res = AnalysisResult(**r.json())
    assert res.risk_level == "high" and "ai_generation_metadata" in {s.id for s in res.signals}


def test_software_tag_names_generator():
    im = _photo()
    ex = Image.Exif()
    ex[305] = "Midjourney"
    li = load_image(_bytes(im, "JPEG", exif=ex))
    sigs, floor = det.metadata_signals(li)
    assert "software_ai_generator" in {s.id for s in sigs} and floor >= 85


def test_camera_exif_is_reassuring():
    ex = Image.Exif()
    ex[271], ex[272] = "Canon", "EOS 80D"
    sigs, _ = det.metadata_signals(load_image(_bytes(_photo(), "JPEG", exif=ex)))
    assert next(s for s in sigs if s.id == "camera_make_model").direction == "reassuring"


def test_corrupt_and_non_image_files_rejected_cleanly():
    for payload in (b"not an image at all", _bytes(_photo())[:200]):
        r = client.post("/api/analyze/image", files={"file": ("bad.jpg", payload, "image/jpeg")})
        assert r.status_code == 400 and r.json()["code"] == "invalid_image"


def test_oversize_image_rejected():
    r = client.post("/api/analyze/image", files={"file": ("big.jpg", b"\xff\xd8" + b"0" * (11 * 1024 * 1024), "image/jpeg")})
    assert r.status_code == 413 and r.json()["code"] == "file_too_large"


def test_tiny_image_rejected():
    r = client.post("/api/analyze/image", files={"file": ("t.png", _bytes(Image.new("RGB", (8, 8)), "PNG"), "image/png")})
    assert r.status_code == 400 and r.json()["code"] == "image_too_small"


def test_missing_file():
    assert client.post("/api/analyze/image").status_code == 422


@pytest.mark.parametrize("p,deg,conf,expected", [(0.97, False, False, "high"), (0.5, False, False, "low"), (0.97, True, False, "medium"), (0.97, True, True, "low")])
def test_model_confidence(p, deg, conf, expected):
    from app.fusion import model_confidence
    assert model_confidence(p, deg, conf) == expected
