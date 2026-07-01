# Sehat engine — FastAPI scoring service.
# Deployed always-on (Render/Railway/Fly in R1; AWS App Runner/ECS in R2). The
# same image runs everywhere because the engine depends only on the canonical
# schema, not on any source. ZERO live LLM calls: narration is pre-baked into the
# frozen persona JSON, so no API key is needed in this container.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code + the frozen personas + the small serve-time artifacts the API reads:
#   validation_report.json + weight_fit.json  -> /validation
#   model_card.json                           -> /model_card + /validation
#   champion.json                             -> the champion is recomputed live (pure
#                                                numpy) for the model cross-check
# (cohort.jsonl is gitignored/large and NOT needed at serve time. challenger.txt is
# NOT needed either — the challenger's PD+SHAP are pre-baked into the persona JSON,
# so no lightgbm/shap in this container.)
COPY sehat ./sehat
COPY personas ./personas
COPY artifacts/validation_report.json artifacts/weight_fit.json artifacts/model_card.json artifacts/champion.json ./artifacts/

EXPOSE 8000

# Render/Railway/Fly inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn sehat.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
