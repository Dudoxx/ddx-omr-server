# ddx-omr-server

Scores checkbox crops with the open-weight
[`hermitkk/omr-checkbox-classifier`](https://huggingface.co/hermitkk/omr-checkbox-classifier)
(AGPL-3.0) and returns one raw probability per box. Port **11513**.

**Licence: AGPL-3.0-or-later** (see `LICENSE`, `NOTICE`). This service is a
separate work. Sentinel calls it over REST only and stays proprietary. Never
import code from here into Sentinel, and never add a dependency on
`ddx-py-patterns` or any other proprietary Sentinel package.

The service takes **no decision**. Ticked, empty or unsure is decided by the
caller; this service only reports `p`.

## Run

```sh
uv sync                        # .venv from uv.lock
./scripts/fetch-weights.sh     # pinned revision, SHA-256 verified, into models/
cp .env.example .env           # set DDX_OMR_API_KEY and OMR_SOURCE_URL
./start.sh --port 11513        # exec uvicorn; refuses a bound port
./status.sh                    # what is actually listening
./stop.sh                      # stops only its own pid
```

Startup refuses when `DDX_OMR_API_KEY` or `OMR_SOURCE_URL` is empty, or when
the weights file is missing or its SHA-256 differs from `OMR_MODEL_SHA256`.

## API

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | none | `status, app, version, model_loaded, model_sha256, model_revision` |
| `GET /source` | none | `license, source_url` — AGPL §13 source offer |
| `POST /v1/omr/read` | `X-API-Key` | score boxes |

`POST /v1/omr/read`

```json
{"image_png_b64": "...", "otsu": true, "pad": 0.35,
 "boxes": [{"id": "r1c1", "x": 120, "y": 340, "w": 22, "h": 22}]}
```

Answer: `{"scores": [{"id": "r1c1", "p": 0.9871}], "ms": 4.2,
"model": {"name", "revision", "sha256"}}` — exactly one score per box, in
request order.

| Status | `error_code` | When |
|---|---|---|
| 401 | `MISSING_API_KEY` | no `X-API-Key` |
| 403 | `INVALID_API_KEY` | wrong key |
| 413 | `TOO_MANY_BOXES` | boxes > `OMR_MAX_BOXES` |
| 422 | `UNDECODABLE_IMAGE` | not base64 / not an image / too large |
| 422 | `BOX_OUTSIDE_PAGE` | a box cannot be cropped — never dropped silently |

Preprocessing per box: crop with `pad` × size on each side, Otsu threshold
(optional), resize to 64×64, normalise to [-1, 1], one batched ONNX CPU run,
sigmoid.

## Configuration

All keys are in `.env.example`: `DDX_OMR_API_KEY`, `HOST`, `OMR_PORT`,
`LOG_LEVEL`, `CORS_ORIGINS` (empty = fail closed), `OMR_MODEL_PATH`,
`OMR_MODEL_SHA256`, `OMR_MODEL_REVISION`, `OMR_MAX_BOXES` (2000),
`OMR_MAX_IMAGE_BYTES`, `OMR_DEFAULT_PAD` (0.35), `OMR_DEFAULT_OTSU` (true),
`OMR_SOURCE_URL`. `DDX_SETTINGS_OVERLAY` is sourced after `.env`.

## Smoke

`../ddx-api-harness/scripts/smoke-omr.sh` — real HTTP: health, source, key
probes, and one 9-box page (one ticked, eight empty).
