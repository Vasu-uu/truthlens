"""Image analysis: learned AI-image classifier + metadata, ELA, frequency, face checks + Grad-CAM."""
from __future__ import annotations

import io
import logging
import re
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.schemas import Signal
from app.utils import model_loader
from app.utils.image_io import LoadedImage, limit_size, png_b64

log = logging.getLogger("truthlens.image")

AI_LABEL_HINTS = ("artificial", "ai", "fake", "generated", "synthetic", "deepfake")
REAL_LABEL_HINTS = ("human", "real", "authentic", "natural")
GENERATOR_RE = re.compile(
    r"(stable[\s_-]?diffusion|midjourney|dall[\s·-]?e|firefly|comfyui|automatic1111|novelai|leonardo|ideogram|flux|sdxl|imagen|bing image creator|generative)", re.I)
EDITOR_RE = re.compile(r"(photoshop|gimp|lightroom|snapseed|canva|picsart|pixlr|facetune|affinity|paint\.net)", re.I)
AI_PARAM_KEYS = ("parameters", "prompt", "workflow", "negative_prompt", "sd-metadata", "invokeai")


def _pct(p: float) -> str:
    """Human wording for a probability that never claims certainty."""
    if p >= 0.99:
        return "over 99%"
    if p <= 0.01:
        return "under 1%"
    return f"about {p:.0%}"


def _sig(sid: str, name: str, value: Any, direction: str, weight: float, detail: str) -> Signal:
    return Signal(id=sid, name=name, category="image", value=value, direction=direction, weight=round(weight, 3), detail=detail)  # type: ignore[arg-type]


# ------------------------------------------------------------------ learned model
def _ai_index(id2label: dict[int, str]) -> int:
    """Index of the 'AI-generated' class, found by label name."""
    for i, lab in id2label.items():
        l = lab.lower()
        if any(h == l or h in l.split() or h in l for h in AI_LABEL_HINTS) and not any(h in l for h in REAL_LABEL_HINTS):
            return int(i)
    for i, lab in id2label.items():  # fall back to the class that is not 'real'
        if any(h in lab.lower() for h in REAL_LABEL_HINTS):
            return [int(j) for j in id2label if int(j) != int(i)][0]
    raise RuntimeError(f"Cannot tell which label means AI-generated: {id2label}")


def classify(img: Image.Image) -> tuple[float, dict[str, Any]]:
    """Return (P(AI-generated), context for Grad-CAM)."""
    import torch

    proc, model = model_loader.load_image_model()
    dev = next(model.parameters()).device
    inputs = proc(images=img, return_tensors="pt")
    pixel = inputs["pixel_values"].to(dev)
    with torch.no_grad():
        logits = model(pixel).logits
    probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
    ai_idx = _ai_index(model.config.id2label)
    return float(probs[ai_idx]), {"pixel": pixel, "model": model, "ai_idx": ai_idx, "proc": proc}


# ------------------------------------------------------------------ Grad-CAM
def _swin_reshape(tensor, height=7, width=7):  # noqa: ANN001
    n = tensor.size(1)
    side = int(round(n ** 0.5))
    return tensor.reshape(tensor.size(0), side, side, tensor.size(2)).permute(0, 3, 1, 2)


def _gradcam_map(ctx: dict[str, Any]) -> np.ndarray:
    """Heat map in [0,1] (HxW) for the 'AI-generated' class."""
    import torch
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

    model = ctx["model"]

    class Wrap(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.m = model

        def forward(self, x):  # noqa: ANN001
            return self.m(x).logits

    wrapped = Wrap().eval()
    if hasattr(model, "swin"):
        layer = model.swin.encoder.layers[-1].blocks[-1].layernorm_before
        rt = _swin_reshape
    elif hasattr(model, "vit"):
        layer = model.vit.encoder.layer[-1].layernorm_before
        rt = _swin_reshape
    else:
        raise RuntimeError("unsupported architecture for Grad-CAM")
    with GradCAM(model=wrapped, target_layers=[layer], reshape_transform=rt) as cam:
        out = cam(input_tensor=ctx["pixel"], targets=[ClassifierOutputTarget(ctx["ai_idx"])])
    return out[0]


def _occlusion_map(img: Image.Image, base_p: float, ctx: dict[str, Any], grid: int = 4) -> np.ndarray:
    """Fallback: how much P(AI) drops when each grid cell is blanked out."""
    import torch

    proc, model, idx = ctx["proc"], ctx["model"], ctx["ai_idx"]
    dev = next(model.parameters()).device
    small = img.resize((224, 224))
    arr = np.asarray(small).copy()
    mean = arr.mean(axis=(0, 1)).astype(np.uint8)
    heat = np.zeros((grid, grid), dtype=np.float32)
    step = 224 // grid
    for gy in range(grid):
        for gx in range(grid):
            a = arr.copy()
            a[gy * step:(gy + 1) * step, gx * step:(gx + 1) * step] = mean
            px = proc(images=Image.fromarray(a), return_tensors="pt")["pixel_values"].to(dev)
            with torch.no_grad():
                p = torch.softmax(model(px).logits, -1)[0, idx].item()
            heat[gy, gx] = max(0.0, base_p - p)
    return cv2.resize(heat, (224, 224), interpolation=cv2.INTER_CUBIC)


def heatmap_overlay(img: Image.Image, cam: np.ndarray) -> str:
    """Blend a [0,1] heat map over the image; return base64 PNG."""
    base = np.asarray(limit_size(img, 512))
    cam = cam - cam.min()
    cam = cam / (cam.max() + 1e-8)
    cam = cv2.resize(cam.astype(np.float32), (base.shape[1], base.shape[0]), interpolation=cv2.INTER_CUBIC)
    color = cv2.cvtColor(cv2.applyColorMap(np.uint8(255 * np.clip(cam, 0, 1)), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    return png_b64(np.uint8(0.55 * base + 0.45 * color))


def make_heatmap(img: Image.Image, p: float, ctx: dict[str, Any]) -> tuple[str | None, str]:
    """Return (heatmap_png_b64 | None, method)."""
    try:
        return heatmap_overlay(img, _gradcam_map(ctx)), "grad-cam"
    except Exception as exc:  # noqa: BLE001
        log.warning("grad-cam failed (%s); using occlusion", type(exc).__name__)
    try:
        return heatmap_overlay(img, _occlusion_map(img, p, ctx)), "occlusion"
    except Exception as exc:  # noqa: BLE001
        log.warning("occlusion failed (%s)", type(exc).__name__)
        return None, "none"


# ------------------------------------------------------------------ metadata
def metadata_signals(li: LoadedImage) -> tuple[list[Signal], float]:
    """EXIF / embedded-metadata signals. Returns (signals, score_floor)."""
    sigs: list[Signal] = []
    floor = 0.0
    ex = li.exif
    exif_main = dict(ex) if ex else {}
    try:
        exif_ifd = dict(ex.get_ifd(0x8769)) if ex else {}
    except Exception:  # noqa: BLE001
        exif_ifd = {}
    make, model = str(exif_main.get(271, "")).strip(), str(exif_main.get(272, "")).strip()
    software = str(exif_main.get(305, "")).strip()

    # Embedded generator parameters (PNG text chunks, e.g. Stable Diffusion / ComfyUI)
    hit_key = next((k for k in li.info if str(k).lower() in AI_PARAM_KEYS), None)
    text_blob = " ".join(str(v) for v in li.info.values())[:4000]
    if hit_key and (re.search(r"(steps:|sampler|cfg scale|seed|\"class_type\")", text_blob, re.I)):
        sigs.append(_sig("ai_generation_metadata", "Embedded AI-generation settings", str(hit_key), "suspicious", 0.9,
                         "The file carries text fields (prompt, sampler, seed) that image generators write, a strong sign it was AI-made."))
        floor = max(floor, 88)
    raw = li.raw[:200_000]
    if b"trainedAlgorithmicMedia" in raw or b"compositeWithTrainedAlgorithmicMedia" in raw:
        sigs.append(_sig("c2pa_ai_claim", "Content Credentials declare AI generation", True, "suspicious", 0.9,
                         "Signed provenance data inside the file says it was produced by a generative AI tool."))
        floor = max(floor, 90)
    elif b"c2pa" in raw or b"jumbf" in raw.lower():
        sigs.append(_sig("c2pa_present", "Content Credentials (C2PA) present", True, "neutral", 0.1,
                         "The file contains provenance data. It was not cryptographically verified here."))

    if software:
        if GENERATOR_RE.search(software):
            sigs.append(_sig("software_ai_generator", "Software tag names an AI generator", software[:50], "suspicious", 0.8,
                             "The 'Software' metadata field names an AI image generator."))
            floor = max(floor, 85)
        elif EDITOR_RE.search(software):
            sigs.append(_sig("software_editor", "Software tag shows editing", software[:50], "suspicious", 0.12,
                             "The file was saved by an image editor, so it may have been retouched (this alone is common and innocent)."))
    if make or model:
        sigs.append(_sig("camera_make_model", "Camera make/model recorded", f"{make} {model}".strip()[:50], "reassuring", 0.15,
                         "Camera details are present, which real photos usually have, though they can be copied or faked."))
    elif exif_main or exif_ifd:
        sigs.append(_sig("no_camera_info", "EXIF present but no camera make/model", None, "suspicious", 0.10,
                         "Metadata exists but names no camera, which is slightly unusual for a straight-from-camera photo."))
    else:
        sigs.append(_sig("exif_missing", "No EXIF metadata", None, "suspicious", 0.06,
                         "No camera metadata was found. This is only a weak hint: WhatsApp, Instagram and screenshots strip it from real photos too."))

    def parse(v: Any):  # noqa: ANN202
        try:
            from datetime import datetime
            return datetime.strptime(str(v)[:19], "%Y:%m:%d %H:%M:%S")
        except Exception:  # noqa: BLE001
            return None
    orig, digi, mod = parse(exif_ifd.get(36867)), parse(exif_ifd.get(36868)), parse(exif_main.get(306))
    if orig and ((digi and abs((digi - orig).total_seconds()) > 60) or (mod and mod < orig)):
        sigs.append(_sig("timestamp_inconsistent", "Inconsistent timestamps", str(orig), "suspicious", 0.12,
                         "The capture and modification times in the metadata do not line up, which can happen when a file is edited or fabricated."))
    return sigs, floor


# ------------------------------------------------------------------ ELA
def ela(img: Image.Image, quality: int = 90) -> tuple[list[Signal], str | None]:
    """Error Level Analysis. Returns (signals, ELA image as base64 PNG)."""
    work = limit_size(img, 1024)
    buf = io.BytesIO()
    work.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    re_saved = Image.open(buf).convert("RGB")
    diff = np.abs(np.asarray(work, dtype=np.int16) - np.asarray(re_saved, dtype=np.int16)).astype(np.float32)
    g = diff.mean(axis=2)
    mean, var = float(g.mean()), float(g.var())
    h, w = g.shape
    gh, gw = 8, 8
    blocks = np.array([g[i * h // gh:(i + 1) * h // gh, j * w // gw:(j + 1) * w // gw].mean() for i in range(gh) for j in range(gw)])
    cv = float(blocks.std() / (blocks.mean() + 1e-6))
    ratio = float(blocks.max() / (np.median(blocks) + 1e-6))
    scale = 255.0 / max(1.0, float(diff.max()))
    art = png_b64(np.uint8(np.clip(diff * min(scale, 20.0), 0, 255)))
    inconsistent = cv > 0.9 and ratio > 4.0
    sig = _sig("ela_regions", "Error-level consistency across regions",
               f"mean={mean:.2f}, spread={cv:.2f}", "suspicious" if inconsistent else "neutral", 0.15 if inconsistent else 0.05,
               "Some regions recompress very differently from the rest, which can indicate pasted or edited areas (weak, noisy evidence)."
               if inconsistent else "Recompression error is fairly even across the picture; ELA alone cannot prove or rule out editing.")
    return [sig], art


# ------------------------------------------------------------------ noise / frequency
def frequency_checks(img: Image.Image) -> list[Signal]:
    """Weak checks: smoothness (Laplacian variance) and periodic high-frequency peaks."""
    gray = np.asarray(limit_size(img, 512).convert("L"), dtype=np.float32)
    lap = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    n = min(gray.shape)
    crop = gray[:n, :n] * np.outer(np.hanning(n), np.hanning(n))
    mag = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(crop))))
    yy, xx = np.indices(mag.shape)
    r = np.hypot(yy - n / 2, xx - n / 2)
    rn = r / (n / 2)
    ring_mean = np.zeros_like(mag)
    for b in range(0, 50):
        m = (rn >= b / 50) & (rn < (b + 1) / 50)
        if m.any():
            ring_mean[m] = mag[m].mean()
    resid = mag - ring_mean
    hf = (rn > 0.3) & (rn < 0.95)
    z = (resid[hf] - resid[hf].mean()) / (resid[hf].std() + 1e-6)
    peak = float(np.percentile(z, 99.99))
    hf_ratio = float(np.exp(mag[(rn > 0.5) & (rn < 1.0)]).sum() / (np.exp(mag).sum() + 1e-6))
    out: list[Signal] = []
    smooth = lap < 15.0
    out.append(_sig("smoothness", "Overall sharpness / noise level", f"laplacian_var={lap:.1f}", "suspicious" if smooth else "neutral",
                    0.10 if smooth else 0.03,
                    "The picture is unusually smooth with little natural sensor noise, which is common in AI renders (but also in blurred or heavily compressed photos)."
                    if smooth else "The level of fine detail and noise looks within the normal range."))
    periodic = peak > 12.0
    out.append(_sig("spectral_peaks", "Periodic patterns in the frequency spectrum", f"peak_z={peak:.1f}, hf_share={hf_ratio:.3f}",
                    "suspicious" if periodic else "neutral", 0.12 if periodic else 0.03,
                    "The frequency spectrum has sharp repeating peaks, a known by-product of AI up-sampling (weak evidence on its own)."
                    if periodic else "No strong repeating frequency patterns were found."))
    return out


# ------------------------------------------------------------------ faces
def face_signal(img: Image.Image) -> list[Signal]:
    """Count frontal faces with a Haar cascade (informational)."""
    try:
        gray = cv2.cvtColor(np.asarray(limit_size(img, 800)), cv2.COLOR_RGB2GRAY)
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = casc.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
    except Exception:  # noqa: BLE001
        return []
    n = len(faces)
    if n == 0:
        return []
    return [_sig("faces_detected", "Faces detected", float(n), "neutral", 0.05,
                 f"{n} face(s) found. Face-swap artefacts are better caught by the classifier score than by simple checks.")]


# ------------------------------------------------------------------ orchestration
def analyze(li: LoadedImage) -> dict[str, Any]:
    """Run all checks. Returns model prob, forensic signals, floor, artifacts, notes."""
    notes: list[str] = []
    signals: list[Signal] = []
    artifacts: dict[str, Any] = {}

    p, ctx = classify(li.rgb)
    meta_sigs, floor = metadata_signals(li)
    signals += meta_sigs
    try:
        s, art = ela(li.rgb)
        signals += s
        if art:
            artifacts["ela_png_base64"] = art
    except Exception as exc:  # noqa: BLE001
        notes.append("Error-level analysis could not run on this file.")
        log.warning("ela failed: %s", type(exc).__name__)
    try:
        signals += frequency_checks(li.rgb)
    except Exception as exc:  # noqa: BLE001
        notes.append("The noise/frequency check could not run on this file.")
        log.warning("freq failed: %s", type(exc).__name__)
    signals += face_signal(li.rgb)

    hm, method = make_heatmap(li.rgb, p, ctx)
    if hm:
        artifacts["heatmap_png_base64"] = hm
        artifacts["heatmap_method"] = method
    else:
        notes.append("The attention heat map could not be generated.")
    artifacts["original_png_base64"] = png_b64(limit_size(li.rgb, 512))
    return {"model_prob": p, "forensic_signals": signals, "floor": floor, "artifacts": artifacts, "notes": notes}


def model_signal(p: float) -> Signal:
    """Signal describing the classifier output."""
    sus = p >= 0.5
    return _sig("ai_model_score", "AI-image classifier estimate", round(p, 3), "suspicious" if sus else "reassuring",
                max(0.1, min(1.0, abs(p - 0.5) * 2)),
                f"The image classifier puts the likelihood that this image is AI-generated at {_pct(p)}."
                if sus else f"The image classifier puts the likelihood that this image is AI-generated at {_pct(p)}.")
