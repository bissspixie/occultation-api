"""
Occultation Ledger API
-----------------------
A small backend that stores occultation events in one central place, so
your website, your Telegram alert bot, and any teammate's device can all
read and write the same list — instead of each device having its own
private copy.

Visit /docs once this is running (locally or deployed) for an interactive
page where you can try every endpoint by clicking buttons — no coding
needed to test it.
"""

import math
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = "events.db"

app = FastAPI(title="Occultation Ledger API")

# Allows your website (running in a browser, on a different address than
# this API) to call it. Fine for a school project; if this ever becomes a
# public tool, narrow this to your actual site's address instead of "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Database setup ----------

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                starmag REAL NOT NULL,
                objmag REAL,
                dur REAL,
                datetime TEXT NOT NULL,
                moon REAL,
                notes TEXT,
                created_at REAL
            )
            """
        )


init_db()


# ---------- Data shapes ----------

class EventIn(BaseModel):
    name: str
    type: str  # "lunar" or "asteroid"
    starmag: float
    objmag: Optional[float] = None
    dur: Optional[float] = None
    datetime: str  # ISO format, e.g. 2026-09-14T21:30
    moon: Optional[float] = None
    notes: Optional[str] = None


class EventOut(EventIn):
    id: str
    tier: str
    drop_before_mag: Optional[float] = None
    drop_during_mag: Optional[float] = None
    drop_delta_mag: Optional[str] = None


# ---------- Brightness-drop math ----------

def flux_from_mag(m: float) -> float:
    return 10 ** (-0.4 * m)


def combined_mag(m1: float, m2: float) -> float:
    return -2.5 * math.log10(flux_from_mag(m1) + flux_from_mag(m2))


def compute_drop(ev: EventIn):
    if ev.type == "lunar":
        return ev.starmag, None, "near-total (dark limb)"
    if ev.objmag is None:
        return ev.starmag, None, "unknown — add asteroid magnitude"
    before = combined_mag(ev.starmag, ev.objmag)
    during = ev.objmag
    return round(before, 2), round(during, 2), str(round(during - before, 2))


def tier_of(mag: float) -> str:
    if 4 <= mag <= 6:
        return "bright"
    if 9 <= mag <= 12:
        return "faint"
    return "other"


def row_to_out(row) -> EventOut:
    ev = EventIn(
        name=row["name"], type=row["type"], starmag=row["starmag"],
        objmag=row["objmag"], dur=row["dur"], datetime=row["datetime"],
        moon=row["moon"], notes=row["notes"],
    )
    before, during, drop = compute_drop(ev)
    return EventOut(
        **ev.dict(), id=row["id"], tier=tier_of(ev.starmag),
        drop_before_mag=before, drop_during_mag=during, drop_delta_mag=drop,
    )


# ---------- Routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/events", response_model=list[EventOut])
def list_events(tier: Optional[str] = None):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY datetime ASC").fetchall()
    out = [row_to_out(r) for r in rows]
    if tier and tier != "all":
        out = [e for e in out if e.tier == tier]
    return out


@app.post("/events", response_model=EventOut)
def add_event(ev: EventIn):
    event_id = str(uuid.uuid4())[:8]
    with get_db() as conn:
        conn.execute(
            """INSERT INTO events (id, name, type, starmag, objmag, dur, datetime, moon, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, ev.name, ev.type, ev.starmag, ev.objmag, ev.dur,
             ev.datetime, ev.moon, ev.notes, time.time()),
        )
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return row_to_out(row)


@app.delete("/events/{event_id}")
def delete_event(event_id: str):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Event not found")
    return {"deleted": event_id}
