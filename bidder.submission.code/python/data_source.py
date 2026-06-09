"""
ADPULSE — real IPinYou dataset streaming layer.

Goal: feed the live dashboard from the REAL IPinYou logs instead of synthetic
data, WITHOUT loading the multi-GB files into memory.

Design highlights (interview-relevant):
  * O(1) memory — files are read line-by-line with a generator, never loaded
    whole. The week of logs can be tens of millions of rows.
  * Auto-detects column layout: the bid log (`bid.*.txt`, ~20 cols) and the
    impression/click/conversion logs (`imp/clk/conv.*.txt`, 24 cols) have
    different schemas; we map both onto a common BidRequest param dict.
  * Real outcomes: if `clk.*`/`conv.*` are present, their BidID sets are
    preloaded (small — clicks are ~0.1%) so each streamed impression can be
    labelled with its TRUE click/conversion — no simulation.
  * Real market price: the 24-col logs carry `Payingprice` (the price the
    original auction winner paid) → a genuine second-price for WON/LOST.
  * Graceful degradation: if no dataset files exist, build_data_source()
    returns None and the caller falls back to the synthetic generator.

Column references (from the dataset PDF / the training notebook):
  24-col imp/clk/conv: BidID,Timestamp,Logtype,VisitorID,User-Agent,IP,Region,
      City,Adexchange,Domain,URL,AnonymousURLID,AdslotID,Adslotwidth,
      Adslotheight,Adslotvisibility,Adslotformat,Adslotfloorprice,CreativeID,
      Biddingprice,Payingprice,KeypageURL,AdvertiserID,UserProfileIDs
  20-col bid log:      BidID,Timestamp,VisitorID,User-Agent,IP,Region,City,
      Adexchange,Domain,URL,AnonymousURLID,AdslotID,Adslotwidth,Adslotheight,
      Adslotvisibility,Adslotformat,Adslotfloorprice,CreativeID,AdvertiserID,
      UserProfileIDs
"""

import os

_NULLS = {"", "null", "Null", "NULL", "na", "NA"}


def _nv(x):
    """Normalise a raw cell → None for null-ish, else stripped string."""
    if x is None:
        return None
    x = x.strip()
    return None if x in _NULLS else x


def _to_int(x, default=None):
    v = _nv(x)
    if v is None:
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def _parse_row(parts):
    """
    Map a tab-split row onto a (params, meta) pair, auto-detecting layout.
    Returns (None, None) for rows we can't use.
    """
    n = len(parts)
    if n >= 24:
        # imp / clk / conv layout (has Logtype, Biddingprice, Payingprice, ...)
        params = {
            "bidId": _nv(parts[0]), "timestamp": _nv(parts[1]),
            "visitorId": _nv(parts[3]), "userAgent": _nv(parts[4]),
            "ipAddress": _nv(parts[5]), "region": _to_int(parts[6], 0),
            "city": _to_int(parts[7], 0), "adExchange": _to_int(parts[8], 0),
            "domain": _nv(parts[9]), "url": _nv(parts[10]),
            "anonymousURLID": _nv(parts[11]), "adSlotID": _nv(parts[12]),
            "adSlotWidth": _to_int(parts[13], 0), "adSlotHeight": _to_int(parts[14], 0),
            "adSlotVisibility": _nv(parts[15]) or "Na", "adSlotFormat": _nv(parts[16]) or "Na",
            "adSlotFloorPrice": _to_int(parts[17], 0), "creativeID": _nv(parts[18]),
            "advertiserId": _to_int(parts[22]), "userTags": _nv(parts[23]),
        }
        meta = {"paying_price": _to_int(parts[20])}  # real market price
    elif n >= 20:
        # raw bid log layout (no Logtype / Payingprice)
        params = {
            "bidId": _nv(parts[0]), "timestamp": _nv(parts[1]),
            "visitorId": _nv(parts[2]), "userAgent": _nv(parts[3]),
            "ipAddress": _nv(parts[4]), "region": _to_int(parts[5], 0),
            "city": _to_int(parts[6], 0), "adExchange": _to_int(parts[7], 0),
            "domain": _nv(parts[8]), "url": _nv(parts[9]),
            "anonymousURLID": _nv(parts[10]), "adSlotID": _nv(parts[11]),
            "adSlotWidth": _to_int(parts[12], 0), "adSlotHeight": _to_int(parts[13], 0),
            "adSlotVisibility": _nv(parts[14]) or "Na", "adSlotFormat": _nv(parts[15]) or "Na",
            "adSlotFloorPrice": _to_int(parts[16], 0), "creativeID": _nv(parts[17]),
            "advertiserId": _to_int(parts[18]), "userTags": _nv(parts[19]),
        }
        meta = {"paying_price": None}
    else:
        return None, None

    if params["advertiserId"] is None or params["timestamp"] is None:
        return None, None
    return params, meta


def _load_bidid_set(path, limit=None):
    """Load the BidID column (col 0) of a log file into a set. Small files."""
    ids = set()
    if not os.path.exists(path):
        return ids
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if limit and i >= limit:
                break
            bid = line.split("\t", 1)[0].strip()
            if bid:
                ids.add(bid)
    return ids


class DataSource:
    """Streams real bid requests from the IPinYou logs (O(1) memory)."""

    def __init__(self, dataset_dir, days):
        self.dataset_dir = dataset_dir
        self.days = days
        self.stream_files = []   # the request stream (prefer bid.*, else imp.*)
        self.kind = None         # "bid" or "imp"
        self.clicked_ids = set()
        self.converted_ids = set()
        self._resolve()

    def _path(self, prefix, day):
        return os.path.join(self.dataset_dir, f"{prefix}.{day}.txt")

    def _resolve(self):
        for day in self.days:
            bid_p = self._path("bid", day)
            imp_p = self._path("imp", day)
            if os.path.exists(bid_p):
                self.stream_files.append(bid_p)
                self.kind = self.kind or "bid"
            elif os.path.exists(imp_p):
                self.stream_files.append(imp_p)
                self.kind = self.kind or "imp"
            # real outcome labels (join by BidID) — present for imp-based streams
            self.clicked_ids |= _load_bidid_set(self._path("clk", day))
            self.converted_ids |= _load_bidid_set(self._path("conv", day))

    @property
    def available(self):
        return len(self.stream_files) > 0

    @property
    def has_real_outcomes(self):
        return len(self.clicked_ids) > 0

    def info(self):
        return {
            "mode": "real",
            "kind": self.kind,
            "files": [os.path.basename(f) for f in self.stream_files],
            "clicked_ids": len(self.clicked_ids),
            "converted_ids": len(self.converted_ids),
            "real_outcomes": self.has_real_outcomes,
        }

    def stream(self):
        """Infinite generator of (params, meta) — loops over the files forever."""
        while True:
            for path in self.stream_files:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        for line in fh:
                            parts = line.rstrip("\n").split("\t")
                            params, meta = _parse_row(parts)
                            if params is None:
                                continue
                            bid_id = params["bidId"]
                            if self.has_real_outcomes and bid_id is not None:
                                meta["clicked"] = bid_id in self.clicked_ids
                                meta["converted"] = bid_id in self.converted_ids
                            else:
                                meta["clicked"] = None
                                meta["converted"] = None
                            yield params, meta
                except FileNotFoundError:
                    continue


def build_data_source(dataset_dir, days):
    """Return a ready DataSource if files exist, else None (→ synthetic fallback)."""
    if not os.path.isdir(dataset_dir):
        return None
    ds = DataSource(dataset_dir, days)
    return ds if ds.available else None
