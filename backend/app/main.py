"""TruthLens FastAPI application."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.main_errors import ApiError
from app.utils import model_loader

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("truthlens")


def create_app() -> FastAPI:
    """Build the FastAPI app."""
    s = get_settings()
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Warm the models in a background thread so the first request is fast."""
        if s.preload_models:
            def warm() -> None:
                for fn in (model_loader.load_image_model, model_loader.load_audio_model):
                    try:
                        fn()
                    except Exception as exc:  # noqa: BLE001
                        log.warning("model warm-up failed: %s", type(exc).__name__)
                log.info("model warm-up finished")

            threading.Thread(target=warm, daemon=True).start()
        yield

    app = FastAPI(title="TruthLens", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_list + ["http://127.0.0.1:5173"],
        allow_origin_regex=r"chrome-extension://.*",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error: %s", type(exc).__name__)  # never log content
        return JSONResponse(status_code=500, content={"code": "internal_error", "message": "Something went wrong analysing this input."})

    @app.get("/api/health")
    def health() -> dict:
        """Models loaded, device and LLM provider status."""
        try:
            import torch

            cuda = torch.cuda.is_available()
            torch_v = torch.__version__
        except Exception:
            cuda, torch_v = False, None
        return {
            "status": "ok",
            "device": model_loader.get_device(),
            "cuda_available": cuda,
            "torch": torch_v,
            "models": model_loader.status(),
            "llm": {
                "provider": s.llm_provider,
                "configured": s.llm_provider == "ollama" or bool(s.llm_api_key) if s.llm_provider != "none" else False,
                "model": s.llm_model or None,
            },
            "thresholds": {"low_max": s.risk_low_max, "high_min": s.risk_high_min},
        }

    from app.routers import audio, combined, image, message, samples

    app.include_router(message.router)
    app.include_router(image.router)
    app.include_router(audio.router)
    app.include_router(combined.router)
    app.include_router(samples.router)
    return app


app = create_app()
