"""Measure detector performance on YOUR labelled files. Reports only what is measured.

Expected layout (any folder may be missing or empty):

  <data>/image/real/*.jpg|png|webp         <data>/image/ai/*
  <data>/audio/real/*.wav|mp3|ogg|opus|m4a <data>/audio/synthetic/*
  <data>/message/legit/*.txt               <data>/message/scam/*.txt   (one message per file)

"Positive" = ai / synthetic / scam. A file is predicted positive when its risk score is
>= --threshold (default 50). Output: counts, accuracy, precision, recall and a confusion matrix
per modality, plus evaluate_report.json. Nothing is reported for a modality with no data,
and small sample sizes are flagged: treat them as anecdotes, not accuracy claims.

Usage:  backend/.venv/Scripts/python scripts/evaluate.py --data path/to/eval_data [--threshold 50]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

IMG, AUD = {".jpg", ".jpeg", ".png", ".webp", ".heic"}, {".wav", ".mp3", ".ogg", ".opus", ".m4a"}
LAYOUT = {  # modality -> (negative folder, positive folder, extensions)
    "image": ("real", "ai", IMG),
    "audio": ("real", "synthetic", AUD),
    "message": ("legit", "scam", {".txt"}),
}


def run_one(modality: str, path: Path):
    from app.routers.audio import run_audio
    from app.routers.image import run_image
    from app.routers.message import run_message

    if modality == "image":
        return run_image(path.read_bytes())
    if modality == "audio":
        return run_audio(path.read_bytes())
    return run_message(path.read_text(encoding="utf-8"))


def metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    n = tp + fp + fn + tn
    div = lambda a, b: round(a / b, 4) if b else None  # noqa: E731
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": div(tp + tn, n),
            "precision": div(tp, tp + fp), "recall": div(tp, tp + fn)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--threshold", type=int, default=50)
    args = ap.parse_args()

    report: dict = {"threshold": args.threshold, "modalities": {}}
    for mod, (neg, pos, exts) in LAYOUT.items():
        files = {lab: sorted(p for p in (args.data / mod / lab).glob("*") if p.suffix.lower() in exts)
                 for lab in (neg, pos)} if (args.data / mod).exists() else {neg: [], pos: []}
        if not (files[neg] or files[pos]):
            print(f"[{mod}] no data found, skipped.")
            continue
        tp = fp = fn = tn = 0
        errors = []
        for label, paths in files.items():
            for p in paths:
                try:
                    res = run_one(mod, p)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{p.name}: {getattr(exc, 'message', exc)}")
                    continue
                pred = res.risk_score >= args.threshold
                actual = label == pos
                tp += pred and actual
                fp += pred and not actual
                fn += (not pred) and actual
                tn += (not pred) and not actual
        m = metrics(tp, fp, fn, tn)
        single_class = not (files[neg] and files[pos])
        if single_class:  # accuracy on one class only says how often we guessed that class: not meaningful
            m["accuracy"] = None
        m["errors"] = errors
        report["modalities"][mod] = m
        print(f"\n[{mod}] n={m['n']} (negatives: {neg}, positives: {pos})")
        print(f"  accuracy={m['accuracy']}  precision={m['precision']}  recall={m['recall']}")
        print(f"  confusion matrix (rows = actual, cols = predicted)")
        print(f"                 pred {neg:<10} pred {pos}")
        print(f"  actual {neg:<10} {tn:<14} {fp}")
        print(f"  actual {pos:<10} {fn:<14} {tp}")
        if single_class:
            print("  note: only one class present, so accuracy is not meaningful (add files for both classes).")
        if m["n"] < 30:
            print(f"  note: only {m['n']} files. Too few to say anything reliable about accuracy.")
        for e in errors:
            print("  skipped:", e)

    if not report["modalities"]:
        print("\nNo labelled data found. Create the folders shown in this script's docstring and add files.")
    out = Path("evaluate_report.json")
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
