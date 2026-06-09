# ADPULSE — production container
# Python 3.9 mirrors the local env the .pkl models were verified under
# (scikit-learn 1.2.2 pickles), eliminating any unpickling ABI risk.
FROM python:3.9-slim

# libgomp1 is required at runtime by lightgbm's compiled wheel
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so this layer caches across code changes
COPY bidder.submission.code/python/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project (models, frontend, region/city tables, code).
# .dockerignore excludes venv, the multi-GB dataset, caches, and .git.
COPY . /app

# Hugging Face Spaces expects the app on 7860; Render/Railway/Fly inject their
# own $PORT at runtime, which overrides this default.
ENV PORT=7860
EXPOSE 7860

# app.py resolves all paths relative to its own location, so run from there.
WORKDIR /app/bidder.submission.code/python
CMD ["python", "app.py"]
