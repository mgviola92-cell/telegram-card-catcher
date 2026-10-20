"""Lightweight activity-driven weighted catalog sampler for large card pools.

Avoid ORDER BY random() over every enabled character on every spawn. Keep
compact uint64 arrays of character IDs and prefix weights, build them only
on-demand, and recheck the selected record in PostgreSQL before showing it.

No background polling, external requests, image storage or cached picture
bytes. The cache is process-local and periodically refreshed from DB when
a spawn is due, so enabled/weight edits eventually become visible.
"""
from array import array
from bisect import bisect_right
import secrets
import threading
import time

CACHE_TTL_SECONDS=300
EMPTY_CACHE_TTL_SECONDS=30
MAX_CATALOG_ROWS=1_000_000
MAX_TOTAL_WEIGHT=(1<<64)-1

# Benchmark: two 8-byte arrays -> 1.6 MB per 100k character identities.
class WeightedCatalogPicker:
    def __init__(self, *,ttl=CACHE_TTL_SECONDS):
        if type(ttl) not in (int,float) or not 1<=ttl<=3600:
            raise ValueError("Cache TTL must be between 1 and 3600 seconds")
        self.ttl=float(ttl)
        self._lock=threading.Lock()
        self._ids=array("Q")
        self._totals=array("Q")
        self._last_refresh=0.0
        self._ready=False

    @property
    def count(self):
        return len(self._ids)

    @property
    def stored_bytes(self):
        return self._ids.itemsize * len(self._ids) + self._totals.itemsize * len(self._totals)

    def invalidate(self):
        with self._lock:
            self._ready=False

    def _refresh(self, db, now):
        ids=array("Q")
        totals=array("Q")
        total=0
        # Server-side named cursor fetches in pages, avoiding a temporary
        # 100k-entry dict list when running on a small Render container.
        with db.cursor(name="cardkout_weighted_catalog") as scan:
            scan.execute("""SELECT id,weight FROM characters
                WHERE enabled=true AND weight>0 ORDER BY id""")
            for row in scan:
                ident=row["id"]
                weight=row["weight"]
                if (type(ident) is not int or ident<=0
                    or type(weight) is not int or weight<=0
                    or len(ids)>=MAX_CATALOG_ROWS or total+weight>MAX_TOTAL_WEIGHT):
                    raise ValueError("Weighted catalog contains invalid or excessive entries")
                total+=weight
                ids.append(ident)
                totals.append(total)
        # Swap arrays together only after successfully loading them. On DB
        # failure keep the old cache but re-raise: don't silently stale-spawn.
        self._ids=ids
        self._totals=totals
        self._last_refresh=now
        self._ready=True

    def choose_id(self,db):
        """Pick one weighted ID. SQL caller MUST still verify enabled/weight."""
        with self._lock:
            now=time.monotonic()
            expiry=self.ttl if self._ids else EMPTY_CACHE_TTL_SECONDS
            if not self._ready or now-self._last_refresh>=expiry:
                self._refresh(db,now)
            if not self._ids:
                return None
            sampled=secrets.randbelow(self._totals[-1])
            position=bisect_right(self._totals,sampled)
            return int(self._ids[position])


active_picker=WeightedCatalogPicker()


def select_active_character(db, picker=active_picker):
    """Return a fresh enabled character row or none after bounded retries.

    Revalidate IDs because a disabled character may remain in a cached
    snapshot. If the ID is stale, reload once and try again rather than
    displaying forbidden/disabled artwork.
    """
    for _ in range(2):
        selected_id=picker.choose_id(db)
        if selected_id is None:
            return None
        row=db.execute("""SELECT * FROM characters WHERE id=%s
            AND enabled=true AND weight>0""",(selected_id,)).fetchone()
        if row is not None:
            return row
        picker.invalidate()
    return None
