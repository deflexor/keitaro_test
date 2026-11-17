import re
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db, init_db
from .keitaro import KeitaroError, call as ktr
from .models import Campaign, Stream, StreamOffer

app = FastAPI(title="Keitaro wrapper")


@app.exception_handler(KeitaroError)
def keitaro_error_handler(_request, exc: KeitaroError):
    return JSONResponse(status_code=502, content={"detail": exc.detail})


init_db()


# ---------------------------------------------------------------- schemas


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1)
    geo: str
    offer_id: int
    domain_id: int
    group_id: int
    traffic_source_id: int


class CampaignImport(BaseModel):
    keitaro_id: int


class OfferIn(BaseModel):
    offer_id: int


class PinIn(BaseModel):
    pinned: bool


# ---------------------------------------------------------------- weights


def recalc(stream: Stream) -> None:
    """Redistribute shares: pinned offers keep their share, the rest split the remainder."""
    active = [o for o in stream.offers if not o.removed]
    pinned = [o for o in active if o.pinned]
    others = [o for o in active if not o.pinned]
    remaining = max(0, 100 - sum(o.share for o in pinned))
    if others:
        base, extra = divmod(remaining, len(others))
        for index, offer in enumerate(others):
            offer.share = base + (1 if index < extra else 0)
    for offer in stream.offers:
        if offer.removed:
            offer.share = 0


def snapshot_of(stream: Stream) -> list[dict]:
    return [
        {
            "offer_id": offer.offer_id,
            "name": offer.name,
            "share": offer.share,
            "pinned": bool(offer.pinned),
            "removed": bool(offer.removed),
        }
        for offer in sorted(stream.offers, key=lambda item: item.offer_id)
    ]


# ---------------------------------------------------------------- serializers


def stream_json(stream: Stream) -> dict:
    return {
        "id": stream.id,
        "keitaro_id": stream.keitaro_id,
        "name": stream.name,
        "position": stream.position,
        "schema": stream.schema_name,
        "editable": stream.editable,
        "dirty": stream.dirty,
        "offers": [
            {
                "offer_id": offer.offer_id,
                "name": offer.name,
                "share": offer.share,
                "pinned": offer.pinned,
                "removed": offer.removed,
            }
            for offer in stream.offers
        ],
    }


def campaign_json(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "keitaro_id": campaign.keitaro_id,
        "name": campaign.name,
        "geo": campaign.geo,
        "domain": campaign.domain_name,
        "group": campaign.group_name,
        "source": campaign.source_name,
        "streams": [stream_json(stream) for stream in campaign.streams],
    }


def campaign_summary(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "keitaro_id": campaign.keitaro_id,
        "name": campaign.name,
        "geo": campaign.geo,
        "domain": campaign.domain_name,
        "group": campaign.group_name,
        "source": campaign.source_name,
        "offers": sum(1 for stream in campaign.streams for o in stream.offers if not o.removed),
        "dirty": any(stream.dirty for stream in campaign.streams),
    }


# ---------------------------------------------------------------- helpers


def get_campaign(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign


def get_stream(db: Session, stream_id: int) -> Stream:
    stream = db.get(Stream, stream_id)
    if not stream:
        raise HTTPException(404, "Flow not found")
    return stream


def find_offer(stream: Stream, offer_id: int) -> StreamOffer | None:
    return next((offer for offer in stream.offers if offer.offer_id == offer_id), None)


def offer_name(offer_id: int) -> str:
    try:
        return ktr("GET", f"/offers/{offer_id}").get("name") or str(offer_id)
    except KeitaroError:
        return str(offer_id)


def sync_campaign(db: Session, campaign: Campaign) -> None:
    """Pull flows from Keitaro. Offers missing there stay locally as 'removed'."""
    remote_streams = ktr("GET", f"/campaigns/{campaign.keitaro_id}/streams")
    for remote in remote_streams:
        stream = db.query(Stream).filter_by(keitaro_id=remote["id"]).first()
        if not stream:
            stream = Stream(keitaro_id=remote["id"], campaign_id=campaign.id)
            db.add(stream)
        stream.name = remote.get("name") or f"Flow {remote['id']}"
        stream.position = remote.get("position") or 0
        stream.schema_name = remote.get("schema") or ""
        stream.action_type = remote.get("action_type") or ""
        stream.action_payload = remote.get("action_payload") or ""
        stream.filters = remote.get("filters") or []
        stream.dirty = False

        remote_offers = {item["offer_id"]: item.get("share", 0) for item in remote.get("offers") or []}
        known = {offer.offer_id: offer for offer in stream.offers}
        for offer_id, share in remote_offers.items():
            offer = known.get(offer_id)
            if offer is None:
                stream.offers.append(
                    StreamOffer(offer_id=offer_id, name=offer_name(offer_id), share=share)
                )
            else:
                offer.removed = False
                offer.share = share
        for offer_id, offer in known.items():
            if offer_id not in remote_offers:
                offer.removed = True
                offer.share = 0
        stream.snapshot = snapshot_of(stream)
    db.commit()


# ---------------------------------------------------------------- keitaro proxies


@app.get("/api/meta")
def get_meta():
    domains = ktr("GET", "/domains")
    groups = ktr("GET", "/groups?type=campaigns")
    sources = ktr("GET", "/traffic_sources")
    return {
        "domains": [{"id": item["id"], "name": item["name"]} for item in domains],
        "groups": [{"id": item["id"], "name": item["name"]} for item in groups],
        "sources": [{"id": item["id"], "name": item["name"]} for item in sources],
    }


@app.get("/api/offers")
def search_offers(q: str = Query("")):
    query = q.strip().lower()
    offers = ktr("GET", "/offers")
    matches = [
        offer
        for offer in offers
        if not query or query in str(offer["id"]) or query in (offer.get("name") or "").lower()
    ]
    return [
        {"id": offer["id"], "name": offer.get("name") or str(offer["id"])}
        for offer in matches[:20]
    ]


# ---------------------------------------------------------------- campaigns


@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.id.desc()).all()
    return [campaign_summary(campaign) for campaign in campaigns]


@app.get("/api/campaigns/{campaign_id}")
def get_campaign_detail(campaign_id: int, db: Session = Depends(get_db)):
    return campaign_json(get_campaign(db, campaign_id))


@app.post("/api/campaigns")
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    geo = payload.geo.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", geo):
        raise HTTPException(400, "Geo must be a two-letter country code, e.g. AU")

    offer = ktr("GET", f"/offers/{payload.offer_id}")
    domains = ktr("GET", "/domains")
    groups = ktr("GET", "/groups?type=campaigns")
    sources = ktr("GET", "/traffic_sources")
    domain = next((item for item in domains if item["id"] == payload.domain_id), None)
    group = next((item for item in groups if item["id"] == payload.group_id), None)
    source = next((item for item in sources if item["id"] == payload.traffic_source_id), None)
    if not domain or not group or not source:
        raise HTTPException(400, "Unknown domain, group or traffic source")

    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or "campaign"
    keitaro_campaign = ktr(
        "POST",
        "/campaigns",
        json={
            "name": payload.name,
            "alias": f"{slug}-{secrets.token_hex(3)}",
            "type": "position",
            "domain_id": payload.domain_id,
            "group_id": payload.group_id,
            "traffic_source_id": payload.traffic_source_id,
        },
    )
    campaign_id = keitaro_campaign["id"]

    try:
        geo_flow = ktr(
            "POST",
            "/streams",
            json={
                "campaign_id": campaign_id,
                "type": "regular",
                "name": f"Geo {geo} -> Google",
                "position": 1,
                "schema": "redirect",
                "action_type": "http",
                "action_payload": "https://google.com",
                "filters": [{"name": "country", "mode": "accept", "payload": [geo]}],
                "collect_clicks": True,
                "offers": [],
                "landings": [],
                "triggers": [],
            },
        )
        offer_flow = ktr(
            "POST",
            "/streams",
            json={
                "campaign_id": campaign_id,
                "type": "regular",
                "name": "Offers",
                "position": 2,
                "schema": "landings",
                "action_type": "http",
                "action_payload": "",
                "collect_clicks": True,
                "offers": [{"offer_id": payload.offer_id, "share": 100, "state": "active"}],
                "landings": [],
                "triggers": [],
            },
        )
    except KeitaroError:
        try:
            ktr("DELETE", f"/campaigns/{campaign_id}")
        except KeitaroError:
            pass
        raise

    campaign = Campaign(
        keitaro_id=campaign_id,
        name=payload.name,
        geo=geo,
        offer_id=payload.offer_id,
        domain_id=payload.domain_id,
        group_id=payload.group_id,
        traffic_source_id=payload.traffic_source_id,
        domain_name=domain["name"],
        group_name=group["name"],
        source_name=source["name"],
    )
    db.add(campaign)
    db.flush()

    for data in (geo_flow, offer_flow):
        stream = Stream(
            campaign_id=campaign.id,
            keitaro_id=data["id"],
            name=data.get("name") or "",
            position=data.get("position") or 0,
            schema_name=data.get("schema") or "",
            action_type=data.get("action_type") or "",
            action_payload=data.get("action_payload") or "",
            filters=data.get("filters") or [],
        )
        db.add(stream)
        db.flush()
        for item in data.get("offers") or []:
            name = offer["name"] if item["offer_id"] == payload.offer_id else offer_name(item["offer_id"])
            stream.offers.append(
                StreamOffer(offer_id=item["offer_id"], name=name, share=item.get("share", 0))
            )
        stream.snapshot = snapshot_of(stream)

    db.commit()
    db.refresh(campaign)
    return campaign_json(campaign)


@app.post("/api/campaigns/import")
def import_campaign(payload: CampaignImport, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter_by(keitaro_id=payload.keitaro_id).first()
    if not campaign:
        data = ktr("GET", f"/campaigns/{payload.keitaro_id}")
        campaign = Campaign(
            keitaro_id=data["id"],
            name=data.get("name") or f"Campaign {data['id']}",
            domain_id=data.get("domain_id") or 0,
            group_id=data.get("group_id") or 0,
            traffic_source_id=data.get("traffic_source_id") or 0,
            domain_name=(data.get("domain") or "").replace("https://", "").replace("http://", "").rstrip("/"),
            group_name=data.get("group") or "",
        )
        db.add(campaign)
        db.commit()
    sync_campaign(db, campaign)
    db.refresh(campaign)
    return campaign_json(campaign)


@app.post("/api/campaigns/{campaign_id}/fetch")
def fetch_streams(campaign_id: int, db: Session = Depends(get_db)):
    campaign = get_campaign(db, campaign_id)
    sync_campaign(db, campaign)
    db.refresh(campaign)
    return campaign_json(campaign)


# ---------------------------------------------------------------- offers in a flow


@app.post("/api/streams/{stream_id}/offers")
def add_offer(stream_id: int, payload: OfferIn, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    if not stream.editable:
        raise HTTPException(400, "Offers can only be managed in offer flows")
    offer = ktr("GET", f"/offers/{payload.offer_id}")
    row = find_offer(stream, payload.offer_id)
    if row and not row.removed:
        raise HTTPException(400, "Offer is already in the flow")
    if row:
        row.removed = False
        row.name = offer.get("name") or row.name
    else:
        stream.offers.append(
            StreamOffer(offer_id=payload.offer_id, name=offer.get("name") or str(payload.offer_id))
        )
    recalc(stream)
    stream.dirty = True
    db.commit()
    return stream_json(stream)


@app.delete("/api/streams/{stream_id}/offers/{offer_id}")
def remove_offer(stream_id: int, offer_id: int, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    row = find_offer(stream, offer_id)
    if not row or row.removed:
        raise HTTPException(404, "Offer is not active in the flow")
    row.removed = True
    row.pinned = False
    recalc(stream)
    stream.dirty = True
    db.commit()
    return stream_json(stream)


@app.post("/api/streams/{stream_id}/offers/{offer_id}/restore")
def restore_offer(stream_id: int, offer_id: int, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    row = find_offer(stream, offer_id)
    if not row:
        raise HTTPException(404, "Offer is not known in the flow")
    row.removed = False
    recalc(stream)
    stream.dirty = True
    db.commit()
    return stream_json(stream)


@app.post("/api/streams/{stream_id}/offers/{offer_id}/pin")
def pin_offer(stream_id: int, offer_id: int, payload: PinIn, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    row = find_offer(stream, offer_id)
    if not row or row.removed:
        raise HTTPException(404, "Offer is not active in the flow")
    row.pinned = payload.pinned
    db.commit()
    return stream_json(stream)


@app.post("/api/streams/{stream_id}/push")
def push_stream(stream_id: int, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    if not stream.editable:
        raise HTTPException(400, "Offers can only be managed in offer flows")
    active = [offer for offer in stream.offers if not offer.removed]
    response = ktr(
        "PUT",
        f"/streams/{stream.keitaro_id}",
        json={
            "offers": [
                {"offer_id": offer.offer_id, "share": offer.share, "state": "active"}
                for offer in active
            ]
        },
    )
    shares = {item["offer_id"]: item.get("share", 0) for item in response.get("offers") or []}
    for offer in stream.offers:
        if offer.offer_id in shares:
            offer.share = shares[offer.offer_id]
    stream.dirty = False
    stream.snapshot = snapshot_of(stream)
    db.commit()
    return stream_json(stream)


@app.post("/api/streams/{stream_id}/cancel")
def cancel_stream(stream_id: int, db: Session = Depends(get_db)):
    stream = get_stream(db, stream_id)
    snapshot = {item["offer_id"]: item for item in stream.snapshot or []}
    for row in list(stream.offers):
        entry = snapshot.pop(row.offer_id, None)
        if entry is None:
            stream.offers.remove(row)
        else:
            row.name = entry.get("name", row.name)
            row.share = entry.get("share", 0)
            row.removed = bool(entry.get("removed", False))
            row.pinned = bool(entry.get("pinned", False))
    for offer_id, entry in snapshot.items():
        stream.offers.append(
            StreamOffer(
                offer_id=offer_id,
                name=entry.get("name") or str(offer_id),
                share=entry.get("share", 0),
                removed=entry.get("removed", False),
                pinned=entry.get("pinned", False),
            )
        )
    stream.dirty = False
    db.commit()
    return stream_json(stream)


# ---------------------------------------------------------------- frontend

dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
