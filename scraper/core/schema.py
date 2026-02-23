from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ListingStatus = Literal["active", "removed", "unknown"]
ListingIntent = Literal["sale", "rent", "leasehold", "freehold", "unknown"]
PropertyType = Literal["villa", "house", "apartment", "land", "commercial", "other", "unknown"]


class Money(BaseModel):
    currency: str = "IDR"
    amount: Optional[float] = None
    period: Optional[Literal["month", "year", "day", "one_time"]] = None


class Location(BaseModel):
    country: str = "ID"
    province: Optional[str] = None
    city: Optional[str] = None
    area: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ListingNormalized(BaseModel):
    # Identity (raw listing)
    source: str                         # e.g. "bali-home-immo"
    source_listing_id: str              # stable per site
    source_url: str
    first_seen_at: str                  # ISO datetime
    last_seen_at: str                   # ISO datetime
    status: ListingStatus = "active"

    # Content
    title: Optional[str] = None
    description: Optional[str] = None
    intent: ListingIntent = "unknown"
    property_type: PropertyType = "unknown"

    # Pricing
    price: Optional[Money] = None                 # primary / preferred price
    prices: List[Money] = Field(default_factory=list)  # all available prices (freehold/yearly/monthly)

    # Attributes
    bedrooms: Optional[float] = None
    bathrooms: Optional[float] = None
    land_size_sqm: Optional[float] = None
    building_size_sqm: Optional[float] = None

    # Location
    location: Optional[Location] = None

    # Media
    images: List[str] = Field(default_factory=list)

    # Agent/Broker
    broker_name: Optional[str] = None
    broker_phone: Optional[str] = None
    broker_email: Optional[str] = None

    # Raw extras for debugging / future fields
    raw: Dict[str, Any] = Field(default_factory=dict)

    # Hash for change detection (computed later)
    content_hash: Optional[str] = None

    amenities: Optional[Amenities] = None

class Amenities(BaseModel):
    furnished: Optional[bool] = None
    internet: Optional[bool] = None
    internet_type: Optional[str] = None

    electricity_watt: Optional[int] = None
    water_source: Optional[str] = None

    parking: Optional[bool] = None
    parking_type: Optional[str] = None

    has_pool: Optional[bool] = None
    pool_size_text: Optional[str] = None

    terrace: Optional[bool] = None
    security_post: Optional[bool] = None