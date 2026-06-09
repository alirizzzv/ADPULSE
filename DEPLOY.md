# Deploying ADPULSE

ADPULSE ships as a single container (Flask + Flask-SocketIO serving the API,
the live WebSocket feed, and the 3D frontend). It runs in **synthetic mode** by
default — the multi-GB IPinYou dataset is git-ignored, and the app auto-falls
back to a synthetic bid-request generator when no dataset is present, so the
live dashboard and globe work anywhere with zero data setup.

- Health check: `GET /api/health`
- The app binds `0.0.0.0:$PORT` (`PORT` injected by the platform; defaults to 7860).
- Single process by design (one background stream thread + in-memory stats).

## Run the container locally
```bash
docker build -t adpulse .
docker run --rm -p 5055:7860 -e PORT=7860 adpulse
# open http://localhost:5055/
```

## Option A — Hugging Face Spaces (free, no credit card, 16 GB RAM)
Best free option; ML-portfolio friendly. Avoids GitHub entirely.
1. huggingface.co → New → **Space** → SDK: **Docker** → blank → Create.
2. Add this front-matter to the Space's `README.md` (sets the port):
   ```
   ---
   title: ADPULSE
   emoji: 📈
   colorFrom: blue
   colorTo: indigo
   sdk: docker
   app_port: 7860
   ---
   ```
3. Push the repo to the Space's git remote (uses an HF access token):
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/adpulse
   git push space main
   ```
4. The Space builds the Dockerfile and serves at `https://<user>-adpulse.hf.space`.

## Option B — Render (free, via GitHub)
Classic web-app URL; reads `render.yaml` automatically.
1. Push the repo to GitHub (your own account).
2. render.com → **New + → Blueprint** → connect the repo → it detects
   `render.yaml` (Docker, free plan, health check `/api/health`).
3. Deploys at `https://adpulse.onrender.com` (free tier sleeps after ~15 min
   idle → first hit cold-starts in ~30–50 s).

## Option C — Railway / Fly (CLI, deploy local code without GitHub)
```bash
# Railway
railway login && railway init && railway up
# Fly
fly launch --dockerfile Dockerfile && fly deploy
```

## Environment knobs (all optional)
| Var | Default | Meaning |
|-----|---------|---------|
| `PORT` | 7860 | Bind port (platform-injected) |
| `DEMO_BID_SCALE` | 8000 | Scales bids vs market price (1 = faithful submission bidder) |
| `DEMO_OUTCOME_SCALE` | 1000 | Amplifies simulated click/conv rates for live visibility |
| `OUTCOME_MODE` | model | `model` (lively) or `real` (ground-truth labels, needs dataset) |
| `DATASET_DAYS` | 06 | Which day(s) of logs to stream if the dataset is present |
