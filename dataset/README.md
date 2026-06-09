# Dataset directory — IPinYou / Adobe DevCraft RTB logs

The live ADPULSE dashboard streams **real bid requests** from the IPinYou
dataset. The raw logs are multi-GB and are **git-ignored** (only this README is
tracked). Download them and place the `.txt` files **directly in this folder**.

## Where to get it
Kaggle dataset: `adobe-devcraft-real-time-bidding` (the `/dataset/` folder).
```bash
# option A — Kaggle CLI
kaggle datasets download -d <owner>/adobe-devcraft-real-time-bidding
unzip adobe-devcraft-real-time-bidding.zip -d .

# option B — download the zip from the Kaggle UI and extract here
```

## Expected layout
```
dataset/
├── imp.06.txt … imp.12.txt     # impression logs (24 cols)  ← stream source
├── clk.06.txt … clk.12.txt     # click logs       (used for REAL click labels)
├── conv.06.txt … conv.12.txt   # conversion logs  (used for REAL conversion labels)
└── bid.06.txt … bid.12.txt     # raw bid log (20 cols) — optional, also streamable
```
The reader (`bidder.submission.code/python/data_source.py`) **auto-detects**
the column layout (20-col `bid.*` vs 24-col `imp.*`) and, when `clk.*`/`conv.*`
are present, computes **real** click/conversion/win-loss by joining BidIDs.

## How the backend picks files
- `DATASET_DIR`  — defaults to this folder (`ADPULSE/dataset`).
- `DATASET_DAYS` — comma-separated days to replay, e.g. `06` or `06,07,08`.
  Defaults to `06`, streamed line-by-line and looped forever (O(1) memory).
- `OUTCOME_MODE` — `model` (default) or `real`. Real display CTR is ~0.06%, so
  ground-truth clicks are too sparse to render live; `model` simulates
  clicks/conversions from the models' predicted probabilities for visibility.
  `real` uses the true clk/conv labels (authentic but quiet — good for validation).
  **Win/loss is ALWAYS real** (resolved against the historical `Payingprice`).
- `DEMO_BID_SCALE` — scales `base_bid` so bids are competitive with the real
  market price (median ~55). Default `8000` → ~44% win rate. Set to `1` for the
  faithful submission bidder.

If this folder has no log files, the backend automatically falls back to the
**synthetic generator** so the demo always runs (e.g. on Railway).

## Run on real data
```bash
cd bidder.submission.code/python
DATASET_DAYS=06 PORT=5050 ./venv/bin/python app.py
# health check shows the active source:
curl -s localhost:5050/api/health | python -m json.tool   # → "data_source": {"mode":"real", ...}
```
