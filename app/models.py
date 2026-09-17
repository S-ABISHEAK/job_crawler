from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PIPELINE_STAGES = [
    "New",
    "Reviewed",
    "Applied",
    "Outreach Sent",
    "Replied",
    "Interview",
    "Offer",
    "Rejected",
]

LEVEL_TAGS = ["intern", "fresher", "0-1yr", "1-2yr", "2+yr", "unknown"]

WORK_MODES = ["remote", "onsite", "hybrid", "unknown"]


def utcnow() -> dt.datetime:
    """Naive UTC -- SQLite has no native timezone-aware datetime type, so
    SQLAlchemy round-trips DateTime(timezone=True) values as naive anyway.
    Keeping everything naive-UTC consistently avoids aware/naive mismatches
    when comparing a freshly computed now() against a value read back from
    the DB."""
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Posting(Base):
    __tablename__ = "postings"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # stable hash
    title: Mapped[str] = mapped_column(String, index=True)
    company: Mapped[str] = mapped_column(String, index=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    work_mode: Mapped[str] = mapped_column(String, default="unknown")

    stipend_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    stipend_parsed: Mapped[float | None] = mapped_column(Float, nullable=True)

    posted_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    level_tag: Mapped[str] = mapped_column(String, default="unknown")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    red_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    red_flag_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    pipeline_status: Mapped[str] = mapped_column(String, default="New", index=True)

    primary_source_name: Mapped[str | None] = mapped_column(String, nullable=True)

    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    dedup_key: Mapped[str] = mapped_column(String, index=True)

    source_urls: Mapped[list["SourceURL"]] = relationship(
        back_populates="posting", cascade="all, delete-orphan"
    )
    outreach_entries: Mapped[list["OutreachLog"]] = relationship(
        back_populates="posting", cascade="all, delete-orphan"
    )


class SourceURL(Base):
    __tablename__ = "source_urls"
    __table_args__ = (UniqueConstraint("posting_id", "source_name", "url", name="uq_posting_source_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"))
    source_name: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # raw ingested payload, for debugging
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    posting: Mapped[Posting] = relationship(back_populates="source_urls")


class OutreachLog(Base):
    __tablename__ = "outreach_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    posting_id: Mapped[str] = mapped_column(ForeignKey("postings.id"))
    contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. LinkedIn DM, email, referral
    date_messaged: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    posting: Mapped[Posting] = relationship(back_populates="outreach_entries")


class AppState(Base):
    """Single-row-per-key table for small bits of app state (e.g. last feed visit timestamp)."""

    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)


class RawIngestLog(Base):
    """Raw ingested payloads stored pre-normalization, for debugging parsing issues."""

    __tablename__ = "raw_ingest_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String, index=True)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
