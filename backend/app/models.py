from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    geo: Mapped[str] = mapped_column(String(2), default="")
    offer_id: Mapped[int] = mapped_column(Integer, default=0)
    domain_id: Mapped[int] = mapped_column(Integer, default=0)
    group_id: Mapped[int] = mapped_column(Integer, default=0)
    traffic_source_id: Mapped[int] = mapped_column(Integer, default=0)
    domain_name: Mapped[str] = mapped_column(String, default="")
    group_name: Mapped[str] = mapped_column(String, default="")
    source_name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    streams: Mapped[list["Stream"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="Stream.position",
    )


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer, default=0)
    schema_name: Mapped[str] = mapped_column(String, default="")
    action_type: Mapped[str] = mapped_column(String, default="")
    action_payload: Mapped[str] = mapped_column(String, default="")
    filters: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    # Full offer state (including archived ones) as of the last fetch/push.
    snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    campaign: Mapped[Campaign] = relationship(back_populates="streams")
    offers: Mapped[list["StreamOffer"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="StreamOffer.id",
    )

    @property
    def editable(self) -> bool:
        return self.schema_name == "landings"


class StreamOffer(Base):
    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("streams.id"))
    offer_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String, default="")
    share: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    removed: Mapped[bool] = mapped_column(Boolean, default=False)

    stream: Mapped[Stream] = relationship(back_populates="offers")
