"""
models.py
---------
Postgres schema mirroring the existing data/database.json structure.

The column names deliberately match the JSON keys the frontend already
consumes (harvestDate, lastScan, verificationEvents). This keeps
static/js/app.js working unchanged: the storage swaps from a file to
Postgres, but every API response keeps its exact shape.

Why this migration matters: data/database.json lives on the filesystem,
and free hosts (Render, Railway, Fly) give you an EPHEMERAL filesystem.
Every redeploy and every container restart resets that file to whatever
is committed in git. Batches created during a demo would vanish on the
next push. save_database() also rewrites the entire file per request, so
two concurrent writes silently drop one.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Index,
)
from sqlalchemy.orm import relationship

db = SQLAlchemy()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _display_now() -> str:
    """The frontend renders dates as strings like '02 Sep 2026, 20:10'."""
    return datetime.now().strftime("%d %b %Y, %H:%M")


class Batch(db.Model):
    __tablename__ = "batches"

    id = Column(String(40), primary_key=True)        # "HC-DEMO-001"
    hive = Column(String(20))
    location = Column(String(120))
    qty = Column(Float)
    date = Column(String(40))                        # display string, as before
    quality = Column(String(60), default="Verified Demo")

    # Real timestamp for ordering. The display string above is kept
    # verbatim for API compatibility; this is what we actually sort by.
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hive": self.hive or "",
            "location": self.location or "",
            "qty": self.qty,
            "date": self.date,
            "quality": self.quality,
        }


class Bottle(db.Model):
    __tablename__ = "bottles"

    token = Column(String(40), primary_key=True)     # public QR token
    code = Column(String(20))                        # PRIVATE lid code
    batch = Column(String(40), ForeignKey("batches.id"))
    harvest = Column(String(40))
    hive = Column(String(20))
    product = Column(String(120), default="Honey")
    origin = Column(String(120))
    harvest_date = Column("harvestDate", String(40))
    moisture = Column(Float)
    status = Column(String(20), default="ACTIVE")
    scans = Column(Integer, default=0, nullable=False)
    last_scan = Column("lastScan", String(40))
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    events = relationship(
        "VerificationEvent", back_populates="bottle",
        cascade="all, delete-orphan", order_by="VerificationEvent.id",
    )

    def to_dict(self, include_code: bool = False) -> dict:
        """
        Matches the JSON shape the frontend expects.

        `code` is the private lid secret and is excluded by default. The
        old public_database() stripped it on the way out; here it is
        opt-in instead, so forgetting to strip it is not possible.
        """
        data = {
            "token": self.token,
            "batch": self.batch,
            "harvest": self.harvest,
            "hive": self.hive or "",
            "product": self.product,
            "origin": self.origin or "",
            "harvestDate": self.harvest_date,
            "moisture": self.moisture,
            "status": self.status,
            "scans": self.scans or 0,
            "lastScan": self.last_scan,
            "verificationEvents": [e.to_dict() for e in self.events],
        }
        if include_code:
            data["code"] = self.code
        return data


class VerificationEvent(db.Model):
    """One scan. Previously a nested array inside the bottle record."""

    __tablename__ = "verification_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bottle_token = Column(String(40), ForeignKey("bottles.token"),
                          nullable=False)
    time = Column(String(40))
    result = Column(String(30))
    session = Column(String(30))
    note = Column(Text)
    tx_hash = Column(String(80))                     # Sepolia tx, if written
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    bottle = relationship("Bottle", back_populates="events")

    __table_args__ = (Index("ix_event_bottle", "bottle_token"),)

    def to_dict(self) -> dict:
        data = {
            "time": self.time,
            "result": self.result,
            "session": self.session,
            "note": self.note or "",
        }
        if self.tx_hash:
            data["tx_hash"] = self.tx_hash
        return data


class Gateway(db.Model):
    __tablename__ = "gateways"

    id = Column(String(30), primary_key=True)
    apiary = Column(String(120))
    backhaul = Column(String(30))
    network = Column(String(30))
    status = Column(String(20), default="ONLINE")
    battery = Column(Float)
    signal = Column(String(20))
    last_seen = Column("lastSeen", String(40))
    hives = Column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "apiary": self.apiary,
            "backhaul": self.backhaul,
            "network": self.network,
            "status": self.status,
            "battery": self.battery,
            "signal": self.signal,
            "lastSeen": self.last_seen,
            "hives": self.hives,
        }


class Device(db.Model):
    __tablename__ = "devices"

    id = Column(String(30), primary_key=True)
    hive = Column(String(20))
    gateway = Column(String(30), ForeignKey("gateways.id"))
    status = Column(String(20), default="ONLINE")
    last_reading = Column("lastReading", String(40))
    battery = Column(Float)

    readings = relationship(
        "Reading", back_populates="device", cascade="all, delete-orphan",
        order_by="Reading.id",
    )

    def to_dict(self, include_readings: bool = True) -> dict:
        data = {
            "id": self.id,
            "hive": self.hive,
            "gateway": self.gateway,
            "status": self.status,
            "lastReading": self.last_reading,
            "battery": self.battery,
        }
        if include_readings:
            data["readings"] = [r.to_dict() for r in self.readings]
        return data


class Reading(db.Model):
    """
    One sensor sample. Previously capped at the last 50 per device by
    slicing a list. Here we keep everything and slice at query time --
    Postgres has no trouble with it, and the full series is what makes
    weight-drop analysis possible.
    """

    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(30), ForeignKey("devices.id"), nullable=False)
    time = Column(String(40))
    temperature = Column(Float)
    humidity = Column(Float)
    weight = Column(Float)
    activity = Column(Float)
    prediction = Column(JSON)                        # ML output, if available
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    device = relationship("Device", back_populates="readings")

    __table_args__ = (Index("ix_reading_device_time", "device_id", "created_at"),)

    def to_dict(self) -> dict:
        data = {
            "time": self.time,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "weight": self.weight,
            "activity": self.activity,
        }
        if self.prediction:
            data["prediction"] = self.prediction
        return data


class HarvestRecord(db.Model):
    """
    The Harvest Integrity Engine's records.

    These were the last thing still living in browser localStorage, which
    meant a mismatch detected on one device was invisible everywhere else
    -- and gone entirely if the user cleared site data. For a problem
    statement about traceability, that was the weakest point in the build.

    Shape matches what static/js/app.js already constructs, so the
    frontend needs only its storage calls swapped for fetch().
    """

    __tablename__ = "harvest_records"

    id = Column(String(40), primary_key=True)        # "HI-..."
    time = Column(String(40))
    hives = Column(JSON)                             # [{hive, before, after}]
    drop = Column(Float)                             # total pre-post weight drop
    extracted = Column(Float)                        # honey actually extracted
    recorded = Column(Float)                         # weight recorded by operator
    moisture = Column(Float)
    status = Column(String(20))                      # OK | MISMATCH
    reasons = Column(JSON)                           # list[str]
    block_hash = Column("blockHash", String(80))
    tx_hash = Column(String(80))                     # Sepolia tx, if written
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (Index("ix_harvest_status", "status"),)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.time,
            "hives": self.hives or [],
            "drop": self.drop,
            "extracted": self.extracted,
            "recorded": self.recorded,
            "moisture": self.moisture,
            "status": self.status,
            "reasons": self.reasons or [],
            "blockHash": self.block_hash,
            "tx_hash": self.tx_hash,
        }


class Meta(db.Model):
    """Single-row table holding what used to be the JSON file's header."""

    __tablename__ = "meta"

    key = Column(String(40), primary_key=True)
    value = Column(Text)
