"""Authenticated routes: POST /v1/omr/read.

The service returns raw probabilities only. Whether a box counts as ticked,
empty or unsure is decided by the caller (Sentinel's confidence code), so no
caller logic crosses the AGPL boundary.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ddx_omr_server.api.settings import Settings
from ddx_omr_server.core.model import CheckboxModel
from ddx_omr_server.core.preprocess import Box, ImageError, crop_box, decode_page


class ErrorResponse(BaseModel):
    error_code: str
    message: str


class BoxIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=200)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class ReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_png_b64: str = Field(min_length=1)
    otsu: bool | None = None
    pad: float | None = Field(default=None, ge=0.0, le=2.0)
    boxes: list[BoxIn]


class Score(BaseModel):
    id: str
    p: float


class ModelOut(BaseModel):
    name: str
    revision: str
    sha256: str


class ReadResponse(BaseModel):
    scores: list[Score]
    ms: float
    model: ModelOut


def _error(code: int, error_code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=code,
        detail=ErrorResponse(error_code=error_code, message=message).model_dump(),
    )


def make_key_guard(config: Settings) -> Callable[..., object]:
    """Build the X-API-Key dependency: 401 when absent, 403 when wrong."""

    async def require_key(x_api_key: str | None = Header(default=None)) -> None:
        if x_api_key is None or not x_api_key.strip():
            raise _error(
                status.HTTP_401_UNAUTHORIZED, "MISSING_API_KEY", "The X-API-Key header is required."
            )
        if x_api_key != config.api_key:
            raise _error(
                status.HTTP_403_FORBIDDEN, "INVALID_API_KEY", "The X-API-Key header does not match."
            )

    return require_key


def build_router(config: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/omr", dependencies=[Depends(make_key_guard(config))])

    @router.post(
        "/read",
        response_model=ReadResponse,
        responses={
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
        tags=["omr"],
    )
    def read(body: ReadRequest, request: Request) -> ReadResponse:
        """Score every box in one batched run. Exactly one score per box, in order."""
        started = time.perf_counter()
        if len(body.boxes) > config.max_boxes:
            raise _error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "TOO_MANY_BOXES",
                f"{len(body.boxes)} boxes exceed OMR_MAX_BOXES={config.max_boxes}.",
            )
        try:
            page = decode_page(body.image_png_b64, config.max_image_bytes)
        except ImageError as exc:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "UNDECODABLE_IMAGE", str(exc)
            ) from exc

        pad = config.default_pad if body.pad is None else body.pad
        otsu = config.default_otsu if body.otsu is None else body.otsu
        crops: list[np.ndarray] = []
        for box in body.boxes:
            crop = crop_box(page, Box(box.x, box.y, box.w, box.h), pad, otsu)
            if crop is None:
                # One score per box is the contract; a box we cannot crop fails
                # the request instead of being silently dropped.
                raise _error(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "BOX_OUTSIDE_PAGE",
                    f"box {box.id!r} lies outside the {page.shape[1]}x{page.shape[0]} page.",
                )
            crops.append(crop)

        model: CheckboxModel = request.app.state.model
        batch = np.stack(crops).astype(np.float32) if crops else np.zeros((0, 64, 64), np.float32)
        probs = model.probabilities(batch)
        scores = [
            Score(id=box.id, p=round(min(max(float(p), 0.0), 1.0), 4))
            for box, p in zip(body.boxes, probs, strict=True)
        ]
        return ReadResponse(
            scores=scores,
            ms=round((time.perf_counter() - started) * 1000, 2),
            model=ModelOut(
                name=model.info.name, revision=model.info.revision, sha256=model.info.sha256
            ),
        )

    return router
