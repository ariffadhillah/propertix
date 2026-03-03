from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urljoin, urlparse, urlsplit, unquote, quote

import requests
from bs4 import BeautifulSoup

from scraper.core.schema import (
    coerce_offer_category,
    coerce_rent_period,
    coerce_tenure_type,
    map_subtype_and_asset_class,
)
from scraper.core.reso_mapper import to_reso_listing  # (tetap diimport kalau dipakai di tempat lain)

BASE = "https://propertia.com"


# =========================
# HTTP
# =========================
def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://propertia.com/",
        }
    )
    return s


def _patch_preview_location(item: dict, listing_loc: dict | None, map_loc: dict | None) -> None:
    """
    Transfer location detail -> item['location_preview'] (preview dari list page).

    - Isi latitude/longitude preview kalau masih None.
    - Isi area/sub_area preview kalau kosong (optional).
    """
    if not isinstance(item, dict):
        return

    pv = item.get("location_preview")
    if not isinstance(pv, dict):
        pv = {}
        item["location_preview"] = pv

    # pastikan keys exist (biar konsisten)
    pv.setdefault("area", None)
    pv.setdefault("sub_area", None)
    pv.setdefault("latitude", None)
    pv.setdefault("longitude", None)

    # 1) lat/lng dari map_loc (paling kuat)
    if isinstance(map_loc, dict):
        if pv.get("latitude") is None and map_loc.get("latitude") is not None:
            pv["latitude"] = map_loc["latitude"]
        if pv.get("longitude") is None and map_loc.get("longitude") is not None:
            pv["longitude"] = map_loc["longitude"]

    # 2) area/sub_area dari listing location (optional)
    if isinstance(listing_loc, dict):
        if not pv.get("area") and listing_loc.get("area"):
            pv["area"] = listing_loc["area"]
        if not pv.get("sub_area") and listing_loc.get("sub_area"):
            pv["sub_area"] = listing_loc["sub_area"]



def build_whatsapp_share_link(title: str | None, page_url: str) -> str:
    """
    Canonical WA share link (no phone target):
      https://wa.me/?text=<urlencoded>
    Use newline for readability.
    """
    t = (title or "").strip()
    u = (page_url or "").strip()

    if t and u:
        msg = f"{t}\n\n{u}"
    elif u:
        msg = u
    else:
        msg = t

    # full encode whole message
    encoded = quote(msg, safe="")
    return f"https://wa.me/?text={encoded}"


def normalize_whatsapp_link(url: str, title: str | None = None, page_url: str | None = None) -> str | None:
    """
    Normalize WhatsApp URLs into stable forms.

    - If URL contains phone= -> keep as api.whatsapp.com/send?phone=... (normalized digits)
    - If URL contains text= -> convert to https://wa.me/?text=<fully-encoded>
      (decode -> rebuild message; optionally append page_url if missing)

    Returns normalized URL or None.
    """
    if not url:
        return None

    u = url.strip()
    if not u:
        return None

    low = u.lower()

    # ---- case A: phone-based link (keep it) ----
    # Examples:
    #   https://api.whatsapp.com/send?phone=628....
    #   https://wa.me/628....
    phone = extract_phone_from_whatsapp_url(u)
    if phone:
        # keep it normalized as api.whatsapp.com (more explicit)
        phone_digits = re.sub(r"[^\d]", "", phone)
        if not phone_digits:
            return None
        return f"https://api.whatsapp.com/send?phone={phone_digits}"

    # ---- case B: text-based share link ----
    # Examples:
    #   https://api.whatsapp.com/send?text=...
    #   https://wa.me/?text=...
    try:
        parsed = urlparse(u)
        qs = parse_qs(parsed.query)
        txt = (qs.get("text") or [None])[0]

        if txt:
            # txt could contain '+' or percent-encoding; normalize by decoding first
            decoded = unquote(txt.replace("+", " ")).strip()

            # optionally ensure page_url is included (nice for consistency)
            if page_url:
                pu = page_url.strip()
                if pu and pu not in decoded:
                    # if decoded already has title but no url, append
                    if decoded:
                        decoded = decoded + "\n\n" + pu
                    else:
                        decoded = pu

            # if decoded is empty but we have title+page_url, rebuild
            if not decoded and (title or page_url):
                return build_whatsapp_share_link(title, page_url or "")

            encoded = quote(decoded, safe="")
            return f"https://wa.me/?text={encoded}"

    except Exception:
        pass

    # ---- fallback: if it “looks like” WA but we can't parse, return as-is ----
    if ("wa.me" in low) or ("api.whatsapp.com" in low):
        return u

    return None


def normalize_whatsapp_links(
    links: list[str],
    title: str | None = None,
    page_url: str | None = None,
) -> list[str]:
    """
    Normalize a list of WA links:
    - produce stable canonical wa.me/?text=... or api.whatsapp.com/send?phone=...
    - dedupe preserve order
    - if no text share link exists but we have title+page_url, optionally add one
    """
    out: list[str] = []
    for x in links or []:
        nx = normalize_whatsapp_link(x, title=title, page_url=page_url)
        if nx:
            out.append(nx)

    out = _dedupe_preserve_order(out)

    # Optional: ensure we always have share link (helpful for CRM)
    # Only add if we have page_url and no existing text share.
    if page_url:
        has_share = any("/?text=" in (s.lower()) for s in out if isinstance(s, str))
        if not has_share:
            out.append(build_whatsapp_share_link(title, page_url))

    return _dedupe_preserve_order(out)


# =========================
# Link filtering (social/contact allowlist)
# =========================
SOCIAL_ALLOW_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "pinterest.com",
    "pinterest.dk",
    "tiktok.com",
    "vt.tiktok.com",
}


def is_social_or_contact_link(url: str) -> bool:
    if not url:
        return False

    u = url.strip()
    low = u.lower()

    # always allow schemes
    if low.startswith(("mailto:", "tel:")):
        return True

    # allow whatsapp/messenger patterns
    if "wa.me" in low or "api.whatsapp.com" in low:
        return True
    if "m.me/" in low or "messenger.com" in low or "facebook.com/messages" in low:
        return True

    # parse domain
    try:
        host = (urlparse(low).netloc or "").lower()
    except Exception:
        return False

    host = host.split(":")[0]

    # social allow domains
    for d in SOCIAL_ALLOW_DOMAINS:
        if host == d or host.endswith("." + d):
            return True

    # block known junk internal links
    if host.endswith("propertia.com") and any(
        p in low
        for p in [
            "/privacy-policy",
            "/terms",
            "/add-new-property",
            "/login",
            "/wp-admin",
        ]
    ):
        return False

    # default false (clean output)
    return False


# =========================
# Small utils
# =========================
def _safe_json_loads(txt: str):
    try:
        return json.loads(txt)
    except Exception:
        return None


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    out: list[str] = []
    for x in items:
        x = (x or "").strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _norm_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _facts_value(soup: BeautifulSoup, label: str) -> str | None:
    label = label.strip().lower()
    for li in soup.select("div.detail-wrap li"):
        strong = li.find("strong")
        if not strong:
            continue
        if strong.get_text(" ", strip=True).strip().lower() == label:
            sp = li.find("span")
            return sp.get_text(" ", strip=True) if sp else None
    return None


def _parse_sqm(val: str) -> float | None:
    if not val:
        return None

    s = val.replace("\xa0", " ").strip().lower()

    # detect unit
    is_are = "are" in s

    # clean
    s = s.replace("m²", "").replace("sqm", "").replace("m2", "")
    s = s.replace("are", "")
    s = re.sub(r"[^\d.,]", "", s).strip()
    if not s:
        return None

    # normalize separators
    if s.count(".") > 1:
        s = s.replace(".", "")
    s = s.replace(",", ".")

    try:
        value = float(s)
    except Exception:
        return None

    # convert are -> sqm
    if is_are:
        return value * 100.0

    return value


# def _parse_number(val: str) -> float | None:
#     if not val:
#         return None
#     s = val.strip()
#     s = re.sub(r"[^\d.,]", "", s)
#     if not s:
#         return None
#     s = s.replace(".", "").replace(",", ".")
#     try:
#         return float(s)
#     except Exception:
#         return None

def _parse_number(val: str) -> float | None:
    """
    Parse angka dari teks, SUPPORT DESIMAL:
      - "4.5" => 4.5
      - "4,5" => 4.5
      - "4"   => 4.0
    Jangan ubah 4.5 jadi 45.
    """
    if not val:
        return None

    s = str(val).strip()
    if not s:
        return None

    # ambil token angka pertama yg mungkin desimal (prioritas)
    m = re.search(r"(\d+[.,]\d+|\d+)", s)
    if not m:
        return None

    num = m.group(1).replace(",", ".")
    try:
        return float(num)
    except Exception:
        return None

def normalize_phone_id(raw: str | None) -> str | None:
    """
    Normalize Indonesian phone numbers to E.164-like format.
    Examples:
      0812xxxx -> +62812xxxx
      62812xxxx -> +62812xxxx
      +62812xxxx -> +62812xxxx
    """
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None

    s = re.sub(r"[^\d+]", "", s)

    # remove multiple leading +
    if s.startswith("++"):
        s = "+" + s.lstrip("+")

    if s.startswith("+62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+" + digits

    if s.startswith("62"):
        digits = re.sub(r"[^\d]", "", s)
        return "+" + digits

    if s.startswith("0"):
        digits = re.sub(r"[^\d]", "", s)
        return "+62" + digits[1:]

    digits = re.sub(r"[^\d]", "", s)
    if len(digits) >= 9:
        return "+62" + digits

    return None


# =========================
# Organization (JSON-LD)
# =========================
def parse_org_from_jsonld(soup: BeautifulSoup) -> dict:
    """
    Extract org info from Yoast schema graph JSON-LD:
      Organization: name, email, telephone, sameAs
    """
    org = {"agency_name": None, "agency_email": None, "agency_phone_raw": None, "same_as": []}

    for sc in soup.select('script[type="application/ld+json"]'):
        data = _safe_json_loads(sc.get_text(strip=True) or "")
        if not data:
            continue

        if isinstance(data, dict) and "@graph" in data:
            graph = data.get("@graph") or []
        elif isinstance(data, list):
            graph = data
        else:
            graph = [data]

        for node in graph or []:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "Organization":
                org["agency_name"] = node.get("name") or org["agency_name"]
                org["agency_email"] = node.get("email") or org["agency_email"]
                org["agency_phone_raw"] = node.get("telephone") or org["agency_phone_raw"]

                same = node.get("sameAs") or []
                if isinstance(same, list):
                    org["same_as"].extend([s for s in same if isinstance(s, str) and s.strip()])
                break

    org["same_as"] = _dedupe_preserve_order([s.strip() for s in (org["same_as"] or []) if s.strip()])
    return org


# =========================
# WhatsApp helpers
# =========================
def extract_phone_from_whatsapp_url(url: str) -> str | None:
    """
    Supports:
      - https://api.whatsapp.com/send?phone=628...
      - https://wa.me/628...
    Returns digits/+ only (not normalized +62 yet).
    """
    if not url:
        return None
    u = url.strip()
    low = u.lower()

    # wa.me/<phone>
    m = re.search(r"wa\.me/(\+?\d{8,15})", low)
    if m:
        return m.group(1)

    # api.whatsapp.com/send?phone=...
    try:
        qs = parse_qs(urlparse(u).query)
        phone = (qs.get("phone") or [None])[0]
        if phone:
            phone = re.sub(r"[^\d+]", "", phone)
            return phone or None
    except Exception:
        pass

    # fallback regex
    m2 = re.search(r"(?:phone=)(\+?\d{8,15})", low)
    return m2.group(1) if m2 else None


def parse_whatsapp_widget_phone(soup: BeautifulSoup) -> str | None:
    """
    Extract phone from WA widget:
      href="https://api.whatsapp.com/send?phone=6281808887711"
    """
    root = soup.select_one("#wa.wa__widget_container") or soup
    a = root.select_one('a[href*="api.whatsapp.com/send"], a[href*="wa.me/"]')
    if not a:
        return None

    href = (a.get("href") or "").strip()
    return extract_phone_from_whatsapp_url(href)


def parse_whatsapp_widget_links(soup: BeautifulSoup) -> list[str]:
    """
    Extract WhatsApp links from WA widget (preferred), otherwise global.
    """
    out: list[str] = []
    root = soup.select_one("#wa.wa__widget_container") or soup

    for a in root.select('a[href*="api.whatsapp.com/send"], a[href*="wa.me/"]'):
        href = (a.get("href") or "").strip()
        if href:
            out.append(href)

    if not out:
        for a in soup.select('a[href*="api.whatsapp.com/send"], a[href*="wa.me/"]'):
            href = (a.get("href") or "").strip()
            if href:
                out.append(href)

    return _dedupe_preserve_order(out)


# =========================
# Footer contacts
# =========================
def parse_footer_links(soup: BeautifulSoup, page_url: str) -> dict:
    footer = soup.select_one("footer") or soup.select_one("section.site-footer")
    out = {"mailto": [], "tel": [], "whatsapp": [], "messenger": [], "form": [], "other": []}
    if not footer:
        return out

    for a in footer.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        href_abs = urljoin(page_url, href)
        low = href_abs.lower()

        if low.startswith("mailto:"):
            out["mailto"].append(href_abs)
        elif low.startswith("tel:"):
            out["tel"].append(href_abs)
        elif "wa.me" in low or "api.whatsapp.com" in low or "whatsapp" in low:
            out["whatsapp"].append(href_abs)
        elif "m.me/" in low or "facebook.com/messages" in low or "messenger.com" in low:
            out["messenger"].append(href_abs)
        else:
            out["other"].append(href_abs)

    for k in list(out.keys()):
        out[k] = _dedupe_preserve_order(out[k])

    return out


# =========================
# Agent/person block
# =========================
def parse_agent_block_propertia(soup: BeautifulSoup, page_url: str) -> dict:
    """
    Broker/person data:
      - name: ul.agent-information li.agent-name
      - email: input[name="target_email"]
      - profile: optional link around agent block
    """
    broker_name = None
    name_el = soup.select_one("ul.agent-information li.agent-name")
    if name_el:
        broker_name = name_el.get_text(" ", strip=True) or None

    broker_email = None
    inp = soup.select_one('input[name="target_email"][value]')
    if inp:
        broker_email = (inp.get("value") or "").strip() or None

    broker_profile_url = None
    container = soup.select_one("ul.agent-information")
    if container:
        parent = container.find_parent()
        a = parent.select_one("a[href]") if parent else None
        if a and a.get("href"):
            href = a.get("href").strip()
            if href and href != "#":
                broker_profile_url = urljoin(page_url, href)

    return {
        "broker_name": broker_name,
        "broker_email": broker_email.lower() if broker_email else None,
        "broker_profile_url": broker_profile_url,
    }


# =========================
# Broker/contact block (FINAL object)
# =========================
# def parse_broker_block_propertia(soup: BeautifulSoup, page_url: str) -> dict:
# def parse_broker_block_propertia(soup: BeautifulSoup, page_url: str, listing_title: str | None = None) -> dict:

#     contact_links_raw["whatsapp"] = normalize_whatsapp_links(
#         contact_links_raw["whatsapp"],
#         title=listing_title,
#         page_url=page_url,
#     )
#     agent = parse_agent_block_propertia(soup, page_url)
#     org = parse_org_from_jsonld(soup)
#     footer_links = parse_footer_links(soup, page_url)

#     contact_links_raw = {
#         "mailto": [],
#         "tel": [],
#         "whatsapp": [],
#         "messenger": [],
#         "form": [],
#         "other": [],
#     }

#     # --- org email/tel ---
#     if org.get("agency_email"):
#         contact_links_raw["mailto"].append("mailto:" + org["agency_email"].strip())

#     if org.get("agency_phone_raw"):
#         tel_raw = str(org["agency_phone_raw"]).strip()
#         if tel_raw:
#             contact_links_raw["tel"].append("tel:" + tel_raw)

#     # --- footer buckets ---
#     for k in contact_links_raw.keys():
#         contact_links_raw[k].extend(footer_links.get(k, []))

#     # --- org sameAs -> other ---
#     for u in (org.get("same_as") or []):
#         contact_links_raw["other"].append(u)

#     # --- WA widget -> whatsapp (collect links first) ---
#     wa_links = parse_whatsapp_widget_links(soup)
#     contact_links_raw["whatsapp"].extend(wa_links)
#         # --- normalize whatsapp links (canonical) ---
#     # NOTE: does NOT change output structure, still list[str]
#     # Use listing title if you have it later; for broker block we can just use None here.
#     # But we DO have page_url.
#     contact_links_raw["whatsapp"] = normalize_whatsapp_links(
#         contact_links_raw["whatsapp"],
#         title=None,           # kalau nanti mau, bisa isi dari listing title
#         page_url=page_url,    # ensure property url is included in share text
#     )

#     # --- filter + dedupe (KEEP FORMAT) ---
#     def dedupe(seq: list[str]) -> list[str]:
#         return _dedupe_preserve_order([x for x in (seq or []) if (x or "").strip()])

#     # filter OTHER
#     filtered_other: list[str] = []
#     for u in contact_links_raw["other"]:
#         u = (u or "").strip()
#         if not u:
#             continue
#         if is_social_or_contact_link(u):
#             filtered_other.append(u)
#     contact_links_raw["other"] = dedupe(filtered_other)

#     # dedupe all buckets
#     for k in ["mailto", "tel", "whatsapp", "messenger", "form"]:
#         contact_links_raw[k] = dedupe(contact_links_raw[k])

#     # --- phone raw priority: WA -> org telephone -> tel bucket ---
#     wa_phone = None
#     if contact_links_raw["whatsapp"]:
#         wa_phone = extract_phone_from_whatsapp_url(contact_links_raw["whatsapp"][0])

#     broker_phone_raw = None
#     if wa_phone:
#         broker_phone_raw = wa_phone
#     elif org.get("agency_phone_raw"):
#         broker_phone_raw = org["agency_phone_raw"]
#     elif contact_links_raw["tel"]:
#         t = contact_links_raw["tel"][0]
#         broker_phone_raw = t.split("tel:", 1)[1].strip() if "tel:" in t else t

#     broker_phone = normalize_phone_id(broker_phone_raw)
#     agency_name = org.get("agency_name") or "Propertia"

#     return {
#         "broker_name": agent.get("broker_name"),
#         "broker_phone_raw": broker_phone_raw,
#         "broker_phone": broker_phone,
#         "broker_email": agent.get("broker_email"),
#         "broker_profile_url": agent.get("broker_profile_url"),
#         "agency_name": agency_name,
#         "contact_links_raw": contact_links_raw,
#     }


def parse_broker_block_propertia(
    soup: BeautifulSoup,
    page_url: str,
    listing_title: str | None = None,
) -> dict:
    agent = parse_agent_block_propertia(soup, page_url)
    org = parse_org_from_jsonld(soup)
    footer_links = parse_footer_links(soup, page_url)

    contact_links_raw = {
        "mailto": [],
        "tel": [],
        "whatsapp": [],
        "messenger": [],
        "form": [],
        "other": [],
    }

    # --- org email/tel ---
    if org.get("agency_email"):
        contact_links_raw["mailto"].append("mailto:" + org["agency_email"].strip())

    if org.get("agency_phone_raw"):
        tel_raw = str(org["agency_phone_raw"]).strip()
        if tel_raw:
            contact_links_raw["tel"].append("tel:" + tel_raw)

    # --- footer buckets ---
    for k in contact_links_raw.keys():
        contact_links_raw[k].extend(footer_links.get(k, []))

    # --- org sameAs -> other ---
    for u in (org.get("same_as") or []):
        contact_links_raw["other"].append(u)

    # --- WA widget -> whatsapp (collect links first) ---
    wa_links = parse_whatsapp_widget_links(soup)
    contact_links_raw["whatsapp"].extend(wa_links)

    # --- filter + dedupe (KEEP FORMAT) ---
    def dedupe(seq: list[str]) -> list[str]:
        return _dedupe_preserve_order([x for x in (seq or []) if (x or "").strip()])

    # filter OTHER
    filtered_other: list[str] = []
    for u in contact_links_raw["other"]:
        u = (u or "").strip()
        if not u:
            continue
        if is_social_or_contact_link(u):
            filtered_other.append(u)
    contact_links_raw["other"] = dedupe(filtered_other)

    # dedupe all buckets (including whatsapp for now)
    for k in ["mailto", "tel", "whatsapp", "messenger", "form"]:
        contact_links_raw[k] = dedupe(contact_links_raw[k])

    # ✅ normalize whatsapp links (setelah whatsapp terkumpul & dedupe)
    contact_links_raw["whatsapp"] = normalize_whatsapp_links(
        contact_links_raw["whatsapp"],
        title=listing_title,
        page_url=page_url,
    )

    # --- phone raw priority: WA -> org telephone -> tel bucket ---
    wa_phone = None
    if contact_links_raw["whatsapp"]:
        wa_phone = extract_phone_from_whatsapp_url(contact_links_raw["whatsapp"][0])

    broker_phone_raw = None
    if wa_phone:
        broker_phone_raw = wa_phone
    elif org.get("agency_phone_raw"):
        broker_phone_raw = org["agency_phone_raw"]
    elif contact_links_raw["tel"]:
        t = contact_links_raw["tel"][0]
        broker_phone_raw = t.split("tel:", 1)[1].strip() if "tel:" in t else t

    broker_phone = normalize_phone_id(broker_phone_raw)
    agency_name = org.get("agency_name") or "Propertia"

    return {
        "broker_name": agent.get("broker_name"),
        "broker_phone_raw": broker_phone_raw,
        "broker_phone": broker_phone,
        "broker_email": agent.get("broker_email"),
        "broker_profile_url": agent.get("broker_profile_url"),
        "agency_name": agency_name,
        "contact_links_raw": contact_links_raw,
    }

# =========================
# Detail-page extractors
# =========================
def extract_price_categories(soup: BeautifulSoup) -> list[str]:
    cats: list[str] = []
    for sp in soup.select("div.side-info span[data-price-category]"):
        c = (sp.get("data-price-category") or "").strip().lower()
        if c:
            cats.append(c)
    return _dedupe_preserve_order(cats)


def infer_client_taxonomy(taxonomy_from_url: dict, price_categories: list[str]) -> dict:
    offer = coerce_offer_category(taxonomy_from_url.get("intent"))
    tenure = coerce_tenure_type(taxonomy_from_url.get("tenure"))
    rent_period = coerce_rent_period(taxonomy_from_url.get("rent_period"))

    cats = set(price_categories or [])

    if "yearly" in cats or "monthly" in cats:
        offer = "rent"
    if "freehold" in cats or "leasehold" in cats:
        offer = "sale" if offer != "rent" else offer

    if "freehold" in cats:
        tenure = "freehold"
    elif "leasehold" in cats:
        tenure = "leasehold"

    if "monthly" in cats:
        rent_period = "month"
    elif "yearly" in cats:
        rent_period = "year"

    return {"offer_category": offer, "tenure_type": tenure, "rent_period": rent_period}


def extract_breadcrumb_texts(soup: BeautifulSoup) -> list[str]:
    items: list[str] = []
    for li in soup.select("ol.breadcrumb li.breadcrumb-item"):
        t = li.get_text(" ", strip=True)
        if t:
            items.append(t)
    return items


# def parse_side_location(soup: BeautifulSoup) -> dict | None:
#     """
#     Extract location from <div class="side-location">.
#     Handles "Area - SubArea" or "Area, SubArea".
#     """
#     box = soup.select_one("div.side-location div.ml-10")
#     if not box:
#         return None

#     def norm(x: str | None) -> str | None:
#         if not x:
#             return None
#         x = re.sub(r"\s+", " ", x).strip()
#         return x or None

#     def split_area_subarea(text: str) -> tuple[str | None, str | None]:
#         if not text:
#             return None, None
#         t = norm(text)
#         if not t:
#             return None, None

#         m = re.split(r"\s*[-–—]\s*", t, maxsplit=1)
#         if len(m) == 2 and m[0] and m[1]:
#             return norm(m[0]), norm(m[1])

#         m = [p.strip() for p in t.split(",", 1)]
#         if len(m) == 2 and m[0] and m[1]:
#             return norm(m[0]), norm(m[1])

#         return t, None

#     span = box.select_one("span")
#     area = span.get_text(strip=True) if span else None

#     full_text = norm(box.get_text(" ", strip=True))
#     sub_area = None

#     if area:
#         area = norm(area)
#         if full_text and area and full_text.lower().startswith(area.lower()):
#             sub_area = norm(full_text[len(area) :].strip())
#         else:
#             sub_area = norm(full_text.replace(area or "", "", 1).strip())

#         if sub_area:
#             sub_area = re.sub(r"^[-–—,]\s*", "", sub_area).strip()
#             sub_area = norm(sub_area)

#         a2, s2 = split_area_subarea(area or "")
#         if a2 and s2:
#             area, sub_area = a2, s2

#         return {"area": area, "sub_area": sub_area}

#     if full_text:
#         a, s = split_area_subarea(full_text)
#         return {"area": norm(a), "sub_area": norm(s)}

#     return None


# def parse_side_location(soup: BeautifulSoup) -> dict | None:
#     def norm(x: str | None) -> str | None:
#         if not x:
#             return None
#         x = re.sub(r"\s+", " ", x).strip()
#         return x or None

#     # ✅ 1) ambil "Area" dari FACTS/detail-wrap
#     area_span = soup.select_one("div.detail-wrap li.prop_area span")
#     if area_span:
#         area = norm(area_span.get_text(" ", strip=True))
#         if area:
#             return {"area": area, "sub_area": None}

#     # 2) fallback lama (kalau masih ada di beberapa listing)
#     box = soup.select_one("div.side-location div.ml-10")
#     if not box:
#         return None

#     span = box.select_one("span")
#     area = span.get_text(strip=True) if span else None
#     full_text = box.get_text(" ", strip=True)
#     sub_area = None
#     if area:
#         sub_area = full_text.replace(area, "", 1).strip() or None

#     return {"area": norm(area), "sub_area": norm(sub_area)}

def parse_side_location(soup: BeautifulSoup) -> dict | None:
    """
    Extract location text and split into area/sub_area.

    Sources (priority):
      1) <address class="item-address ...">Umalas - Bumbak</address>
      2) legacy: div.side-location div.ml-10 (BHI-ish)
      3) (optional) FACTS prop_area (kalau ada)

    Returns:
      {"area": "...", "sub_area": "..."} with sub_area optional.
    """
    def norm(x: str | None) -> str | None:
        if not x:
            return None
        x = re.sub(r"\s+", " ", x).strip()
        return x or None

    def split_area_subarea(text: str) -> tuple[str | None, str | None]:
        """
        Split patterns:
          "Umalas - Bumbak" / "Umalas – Bumbak" / "Umalas — Bumbak"
          "Umalas, Bumbak"
        If no separator => (text, None)
        """
        t = norm(text)
        if not t:
            return None, None

        # dash variants
        parts = re.split(r"\s*[-–—]\s*", t, maxsplit=1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return norm(parts[0]), norm(parts[1])

        # comma
        parts = [p.strip() for p in t.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return norm(parts[0]), norm(parts[1])

        return t, None

    # ✅ 1) NEW: address.item-address (yang kamu bilang sumbernya)
    addr = soup.select_one("address.item-address")
    if addr:
        # remove icon text automatically by get_text
        txt = addr.get_text(" ", strip=True)
        a, s = split_area_subarea(txt)
        if a:
            return {"area": a, "sub_area": s}

    # ✅ 2) OPTIONAL: FACTS prop_area (kalau ada, biasanya cuma area)
    area_span = soup.select_one("div.detail-wrap li.prop_area span")
    if area_span:
        txt = norm(area_span.get_text(" ", strip=True))
        if txt:
            # kalau FACTS ternyata berisi "Umalas - Bumbak" tetap kita split
            a, s = split_area_subarea(txt)
            return {"area": a, "sub_area": s}

    # ✅ 3) legacy fallback
    box = soup.select_one("div.side-location div.ml-10")
    if box:
        txt = box.get_text(" ", strip=True)
        a, s = split_area_subarea(txt)
        if a:
            return {"area": a, "sub_area": s}

    return None

def parse_taxonomy_from_facts(soup: BeautifulSoup) -> dict:
    out = {"intent": None, "property_type": None, "tenure": None, "rent_period": None}

    def get_facts_value(label: str) -> str | None:
        for li in soup.select("div.detail-wrap li"):
            strong = li.find("strong")
            if not strong:
                continue
            if strong.get_text(" ", strip=True).lower() == label.lower():
                sp = li.find("span")
                return sp.get_text(" ", strip=True) if sp else None
        return None

    status = (get_facts_value("Property Status") or "").strip().lower()
    ptype = (get_facts_value("Property Type") or "").strip().lower()

    if "for sale" in status:
        out["intent"] = "sale"
    elif "for rent" in status:
        out["intent"] = "rent"

    m = re.search(r"\b(villa|land|apartment|house|condo|townhouse|commercial)\b", status)
    if m:
        out["property_type"] = m.group(1)
    if not out["property_type"]:
        m2 = re.search(r"\b(villa|land|apartment|house|condo|townhouse|commercial)\b", ptype)
        if m2:
            out["property_type"] = m2.group(1)

    if "leasehold" in ptype:
        out["tenure"] = "leasehold"
    elif "freehold" in ptype:
        out["tenure"] = "freehold"

    return out


def parse_taxonomy_from_url(url: str) -> dict:
    if not url:
        return {"intent": None, "property_type": None, "tenure": None, "rent_period": None}

    path = urlsplit(url).path.lower().strip("/")
    parts = path.split("/")

    out = {"intent": None, "property_type": None, "tenure": None, "rent_period": None}

    for p in parts:
        if p == "for-sale":
            out["intent"] = "sale"
        elif p == "for-rent":
            out["intent"] = "rent"

    try:
        idx = parts.index("for-sale")
    except ValueError:
        try:
            idx = parts.index("for-rent")
        except ValueError:
            return out

    if idx + 1 < len(parts):
        out["property_type"] = parts[idx + 1]

    if idx + 2 < len(parts):
        token = parts[idx + 2]
        if token in ("freehold", "leasehold"):
            out["tenure"] = token

        if token in ("daily", "nightly"):
            out["rent_period"] = "night"
        elif token in ("weekly", "week"):
            out["rent_period"] = "week"
        elif token in ("monthly", "month"):
            out["rent_period"] = "month"
        elif token in ("yearly", "annual", "year"):
            out["rent_period"] = "year"

    if out["tenure"] is None:
        for t in ("freehold", "leasehold"):
            if t in parts:
                out["tenure"] = t

    return out


def extract_description(soup: BeautifulSoup) -> str | None:
    box = soup.select_one(".property-description-content .description-content")
    if not box:
        return None

    parts: list[str] = []
    for p in box.select("p"):
        txt = p.get_text(" ", strip=True)
        if txt:
            parts.append(txt)

    parts = _dedupe_preserve_order(parts)
    desc = "\n\n".join(parts).strip()
    return desc or None


def extract_images_propertia(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []

    for img in soup.select("div.hs-gallery-v4-grid img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")

        if not src:
            srcset = img.get("srcset", "")
            if srcset:
                src = srcset.split(",")[0].strip().split(" ")[0].strip()

        if not src:
            continue

        src = src.strip()
        if not src:
            continue

        if src.startswith("/"):
            src = urljoin(BASE, src)

        if "wp-content/uploads/" not in src:
            continue

        urls.append(src)

    return _dedupe_preserve_order(urls)


# =========================
# Generic table parsing
# =========================
def extract_table_kv(container) -> dict[str, str]:
    out: dict[str, str] = {}
    if not container:
        return out

    for tr in container.select("table.table tbody tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        if len(tds) >= 3:
            key = tds[0].get_text(" ", strip=True)
            val = tds[2].get_text(" ", strip=True)
        else:
            key = tds[0].get_text(" ", strip=True)
            val = tds[1].get_text(" ", strip=True) if len(tds) > 1 else ""
            val = val.lstrip(":").strip()

        if key:
            out[_norm_key(key)] = (val or "").strip()

    return out


def extract_section_by_category(soup: BeautifulSoup, section_prefix: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for cat in ["freehold", "leasehold", "yearly", "monthly"]:
        el = soup.select_one(f"#{section_prefix}-{cat}")
        kv = extract_table_kv(el)
        if kv:
            out[cat] = kv
    return out


def choose_primary_category(source_url: str) -> str:
    url = (source_url or "").lower()
    if "/for-sale/" in url or "/sale/" in url:
        return "freehold"
    if "/for-rent/" in url or "/rent/" in url:
        return "yearly"
    return "freehold"


def pick_category_dict(all_by_cat: dict[str, dict[str, str]], preferred: str) -> tuple[str | None, dict[str, str]]:
    if not all_by_cat:
        return None, {}
    if preferred in all_by_cat:
        return preferred, all_by_cat[preferred]
    for cat in ["freehold", "leasehold", "yearly", "monthly"]:
        if cat in all_by_cat:
            return cat, all_by_cat[cat]
    k = next(iter(all_by_cat.keys()))
    return k, all_by_cat[k]


# =========================
# Facilities / General info (FACTS-based)
# =========================
def extract_parking_from_facts(soup: BeautifulSoup) -> dict[str, str]:
    kv: dict[str, str] = {}
    for li in soup.select("div.detail-wrap li"):
        strong = li.find("strong")
        span = li.find("span")
        if not strong or not span:
            continue

        label = strong.get_text(" ", strip=True).strip().lower()
        value = span.get_text(" ", strip=True).strip()

        if label == "parking type" and value:
            kv["parking"] = value
        elif label == "parking spaces" and value:
            kv["parking size"] = value

    return kv


def extract_facilities_propertia(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    def norm_key(x: str) -> str:
        x = x.strip().lower()
        x = re.sub(r"\s+", " ", x)
        return x

    cat = "freehold"
    for li in soup.select("div.detail-wrap li.prop_type"):
        sp = li.find("span")
        txt = sp.get_text(" ", strip=True).lower() if sp else ""
        if "leasehold" in txt:
            cat = "leasehold"
        elif "freehold" in txt:
            cat = "freehold"

    kv: dict[str, str] = {}

    wrap = soup.select_one("#property-features-wrap")
    if wrap:
        for a in wrap.select("li a"):
            name = a.get_text(" ", strip=True)
            if name:
                kv[norm_key(name)] = "Yes"

    parking_kv = extract_parking_from_facts(soup)
    if parking_kv:
        kv.update(parking_kv)

    if not kv:
        return {}

    return {cat: kv}


def extract_general_information_propertia(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    def norm_key(x: str) -> str:
        x = x.strip().lower()
        x = re.sub(r"\s+", " ", x)
        return x

    cat = "freehold"
    prop_type = soup.select_one("div.detail-wrap li.prop_type span")
    txt = prop_type.get_text(" ", strip=True).lower() if prop_type else ""
    if "leasehold" in txt:
        cat = "leasehold"
    elif "freehold" in txt:
        cat = "freehold"

    kv: dict[str, str] = {}

    for li in soup.select("div.detail-wrap li"):
        strong = li.find("strong")
        span = li.find("span")
        if not strong or not span:
            continue

        k = norm_key(strong.get_text(" ", strip=True))
        v = span.get_text(" ", strip=True).strip()
        if not k or not v:
            continue

        # skip obvious non-general fields
        if k in (
            "price",
            "property id",
            "property status",
            "property type",
            "bedrooms",
            "bathrooms",
            "area",
        ):
            continue

        kv[k] = v

    if not kv:
        return {}

    return {cat: kv}


# =========================
# Price parsing
# =========================
def _parse_amount(raw: str) -> float | None:
    if not raw:
        return None

    s = raw.strip()
    if "request" in s.lower():
        return None

    s = s.split("/")[0].strip()
    s = s.replace(".", "").replace(",", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None

    try:
        return float(s)
    except Exception:
        return None


def _map_period(category: str) -> str | None:
    c = (category or "").lower()
    if c in ("freehold", "leasehold"):
        return "one_time"
    if c == "yearly":
        return "year"
    if c == "monthly":
        return "month"
    return None


def extract_prices(soup: BeautifulSoup) -> list[dict]:
    spans = soup.select("span[data-price][data-price-category]")
    out: list[dict] = []

    # ===== 1) ORIGINAL LOGIC (JANGAN DIUBAH) =====
    for sp in spans:
        raw_price = sp.get("data-price", "").strip()
        category = sp.get("data-price-category", "").strip().lower()

        amount = _parse_amount(raw_price)
        if amount is None:
            continue

        out.append(
            {
                "currency": "IDR",
                "amount": amount,
                "period": _map_period(category),
                "category": category,
            }
        )

    # ===== 2) FALLBACK: FACTS SECTION =====
    if not out:
        for li in soup.select("div.detail-wrap li"):
            strong = li.find("strong")
            if not strong:
                continue
            if strong.get_text(strip=True).lower() != "price":
                continue

            span = li.find("span")
            if not span:
                continue

            raw_price = span.get_text(strip=True)
            amount = _parse_amount(raw_price)
            if amount:
                out.append(
                    {
                        "currency": "IDR",
                        "amount": amount,
                        "period": "one_time",
                        "category": "facts_block",
                    }
                )

    # ===== 3) DEDUPE =====
    seen = set()
    deduped = []
    for p in out:
        k = (p["amount"], p["period"], p.get("category"))
        if k in seen:
            continue
        seen.add(k)
        deduped.append(p)

    return deduped


def choose_primary_price(prices: list[dict], source_url: str) -> dict | None:
    if not prices:
        return None

    url = (source_url or "").lower()

    def find_cat(cat: str):
        for p in prices:
            if p.get("category") == cat:
                return p
        return None

    if "/for-sale/" in url or "/sale/" in url:
        return find_cat("freehold") or find_cat("leasehold") or prices[0]

    if "/for-rent/" in url or "/rent/" in url:
        return find_cat("yearly") or find_cat("monthly") or prices[0]

    return (
        find_cat("freehold")
        or find_cat("leasehold")
        or find_cat("yearly")
        or find_cat("monthly")
        or prices[0]
    )


def extract_price_per_are_per_year(soup: BeautifulSoup) -> dict | None:
    raw_txt = _facts_value(soup, "Price per Are per year")
    if not raw_txt:
        return None

    amt = _parse_amount(raw_txt)
    if amt is None:
        return {"raw": raw_txt.strip()}

    return {
        "currency": "IDR",
        "amount": float(amt),
        "unit": "are",
        "period": "year",
        "raw": raw_txt.strip(),
    }


# =========================
# Title / Neighborhood
# =========================
def extract_title(soup: BeautifulSoup) -> str | None:
    el = soup.select_one(".property-title-wrap .page-title h1") or soup.select_one("h1")
    if not el:
        return None
    t = el.get_text(" ", strip=True)
    return t or None


def extract_neighborhood_propertia(soup: BeautifulSoup) -> dict[str, str]:
    wrap = soup.select_one("#property-neighborhood-wrap")
    if not wrap:
        return {}

    def norm_key(x: str) -> str:
        x = x.strip().lower()
        x = re.sub(r"\s+", "_", x)
        x = re.sub(r"[^a-z0-9_]", "", x)
        return x

    out: dict[str, str] = {}

    for block in wrap.select(".col-md-6, .col-sm-6, .col-6"):
        label = block.select_one("label")
        value = block.select_one(".single_field_nhood span")

        k = label.get_text(" ", strip=True) if label else ""
        v = value.get_text(" ", strip=True) if value else ""
        v = re.sub(r"\s+", " ", (v or "").strip())

        k = norm_key(k)
        if k and v:
            out[f"{k}_distance"] = v

    return out


# def extract_lat_lng_from_map(soup: BeautifulSoup) -> tuple[Optional[float], Optional[float]]:
#     """
#     Houzez map container:
#     <div id="houzez-single-listing-map-address" data-map='{"latitude":"..","longitude":".."}'>
#     """
#     el = soup.select_one("#houzez-single-listing-map-address[data-map]")
#     if not el:
#         return None, None

#     raw = (el.get("data-map") or "").strip()
#     if not raw:
#         return None, None

#     data = _safe_json_loads(raw)
#     if not isinstance(data, dict):
#         return None, None

#     lat_raw = data.get("latitude")
#     lng_raw = data.get("longitude")

#     try:
#         lat = float(lat_raw) if lat_raw not in (None, "") else None
#     except Exception:
#         lat = None

#     try:
#         lng = float(lng_raw) if lng_raw not in (None, "") else None
#     except Exception:
#         lng = None

#     return lat, lng

def parse_map_lat_lng_propertia(soup: BeautifulSoup) -> dict | None:
    """
    Extract lat/lng/address from:
      <div id="houzez-single-listing-map-address" data-map="{...}">

    Returns:
      {"latitude": float, "longitude": float, "address": str|None}
    """
    el = soup.select_one("#houzez-single-listing-map-address[data-map]")
    if not el:
        return None

    raw = (el.get("data-map") or "").strip()
    if not raw:
        return None

    data = _safe_json_loads(raw)
    if not isinstance(data, dict):
        return None

    lat_raw = data.get("latitude")
    lng_raw = data.get("longitude")
    addr = data.get("address")

    try:
        lat = float(str(lat_raw).strip()) if lat_raw is not None else None
        lng = float(str(lng_raw).strip()) if lng_raw is not None else None
    except Exception:
        lat, lng = None, None

    if lat is None and lng is None:
        return None

    out = {"latitude": lat, "longitude": lng, "address": (addr or "").strip() or None}
    return out


# =========================
# MAIN: parse_detail_page (OUTPUT JSON TIDAK DIUBAH)
# =========================
def parse_detail_page(item: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """
    Return 'listing dict' (bukan nested record), mirip BHI parse_detail_page.
    Adapter akan memasukkan ke schema record tanpa mengubah struktur inti.
    """
    url = item["url"]

    sess = _make_session()
    r = sess.get(url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    taxonomy = parse_taxonomy_from_url(url)

    facts_tax = parse_taxonomy_from_facts(soup)
    for k, v in facts_tax.items():
        if not taxonomy.get(k) and v:
            taxonomy[k] = v

    title = extract_title(soup)
    prices = extract_prices(soup)
    primary = choose_primary_price(prices, url)

    preferred_cat = choose_primary_category(url)

    indoor_all = extract_section_by_category(soup, "list-indoor")
    outdoor_all = extract_section_by_category(soup, "list-outdoor")

    general_all = extract_general_information_propertia(soup)
    gen_cat, general = pick_category_dict(general_all, preferred_cat)
    in_cat, indoor = pick_category_dict(indoor_all, preferred_cat)

    fac_all = extract_facilities_propertia(soup)
    fac_cat, facilities = pick_category_dict(fac_all, preferred_cat)

    land_size = _parse_sqm(general.get("land size", ""))
    building_size = _parse_sqm(general.get("building size", ""))

    # fallback FACTS
    if land_size is None:
        land_size = _parse_sqm(_facts_value(soup, "Land Size") or "")
    if building_size is None:
        building_size = _parse_sqm(_facts_value(soup, "Building Size") or "")

    bedrooms = _parse_number(indoor.get("bedroom", ""))
    bathrooms = _parse_number(indoor.get("bathroom", ""))

    if bedrooms is None:
        bedrooms = _parse_number(_facts_value(soup, "Bedrooms") or "")
    if bathrooms is None:
        bathrooms = _parse_number(_facts_value(soup, "Bathrooms") or "")

    # Year Built
    year_built = None
    yb_raw = _facts_value(soup, "Year Built")
    if yb_raw:
        yb_raw = yb_raw.strip()
        if yb_raw.isdigit():
            year_built = int(yb_raw)

    neighborhood = extract_neighborhood_propertia(soup)
    price_per_are_per_year = extract_price_per_are_per_year(soup)

    images = extract_images_propertia(soup)
    description = extract_description(soup)

    # broker = parse_broker_block_propertia(soup, url)
    broker = parse_broker_block_propertia(soup, url, listing_title=title)

    def to_money(p: dict) -> dict:
        return {"currency": p["currency"], "amount": p["amount"], "period": p.get("period")}

    # strongest taxonomy
    price_categories = extract_price_categories(soup)
    client_tax = infer_client_taxonomy(taxonomy, price_categories)

    # map subtype/asset_class
    raw_type = taxonomy.get("property_type")
    asset_class, property_subtype = map_subtype_and_asset_class(raw_type)

    # lat, lng = extract_lat_lng_from_map(soup)

    # if lat is not None or lng is not None:
    #     listing["location"] = {
    #         "latitude": lat,
    #         "longitude": lng,
    #     }

    # =========================
    # ✅ OUTPUT JSON (JANGAN DIUBAH FORMAT)
    # =========================
    listing = {
        "source_listing_id": item["source_listing_id"],
        "source_url": url,
        "title": title,
        "description": description,

        # ✅ Client fields
        "offer_category": client_tax["offer_category"],
        "tenure_type": client_tax["tenure_type"],
        "rent_period": client_tax["rent_period"],
        "asset_class": asset_class,
        "property_subtype": property_subtype,

        # (optional) legacy fields sementara
        "intent": taxonomy.get("intent") or "unknown",
        "property_type": taxonomy.get("property_type") or "unknown",
        "tenure": taxonomy.get("tenure") or "unknown",

        "price": to_money(primary) if primary else None,
        "prices": [to_money(p) for p in prices],

        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "land_size_sqm": land_size,
        "building_size_sqm": building_size,

        "location": None,
        "images": images,

        "broker_name": broker.get("broker_name"),
        "broker_phone": broker.get("broker_phone"),
        "broker_email": broker.get("broker_email"),
        "broker_profile_url": broker.get("broker_profile_url"),
        "agency_name": broker.get("agency_name"),

        "broker_phone_raw": broker.get("broker_phone_raw"),
        "contact_links_raw": broker.get("contact_links_raw"),

        "raw": {
            "debug": {"fetched_url": url},
            "url_taxonomy": taxonomy,
            "price_categories": price_categories,
            "breadcrumb": extract_breadcrumb_texts(soup),

            "site_sections": {
                "general_information": general_all,
                "indoor": indoor_all,
                "outdoor": outdoor_all,
                "facilities": facilities,
                "primary_category_used": {
                    "preferred": preferred_cat,
                    "general": gen_cat,
                    "indoor": in_cat,
                },
            },

            "facts": {"year_built": year_built},

            "neighborhood": neighborhood or None,

            "contact": {
                "broker_phone_raw": broker.get("broker_phone_raw"),
                "contact_links_raw": broker.get("contact_links_raw"),
            },
        },
    }

    # location
    # side_loc = parse_side_location(soup)
    # if side_loc:
    #     loc = listing.get("location") or {}
    #     if not isinstance(loc, dict):
    #         loc = {}
    #     if not loc.get("area") and side_loc.get("area"):
    #         loc["area"] = side_loc["area"]
    #     if not loc.get("sub_area") and side_loc.get("sub_area"):
    #         loc["sub_area"] = side_loc["sub_area"]
    #     listing["location"] = loc or None

    # # --- lat/lng from map (detail page) ---
    # map_loc = parse_map_lat_lng_propertia(soup)
    # if map_loc:
    #     loc = listing.get("location") or {}
    #     if not isinstance(loc, dict):
    #         loc = {}

    #     # jangan overwrite kalau sudah ada
    #     if loc.get("latitude") is None and map_loc.get("latitude") is not None:
    #         loc["latitude"] = map_loc["latitude"]
    #     if loc.get("longitude") is None and map_loc.get("longitude") is not None:
    #         loc["longitude"] = map_loc["longitude"]
            

    #     # optional: simpan address mentah kalau kamu mau (tetap dalam dict location)
    #     # kalau client schema tidak mau address, skip baris ini
    #     # if loc.get("address") is None and map_loc.get("address"):
    #     #     loc["address"] = map_loc["address"]

    #     listing["location"] = loc or None
    #     _patch_preview_location(item, listing.get("location"), map_loc)



    # location
    side_loc = parse_side_location(soup)
    if side_loc:
        loc = listing.get("location") or {}
        if not isinstance(loc, dict):
            loc = {}
        if not loc.get("area") and side_loc.get("area"):
            loc["area"] = side_loc["area"]
        if not loc.get("sub_area") and side_loc.get("sub_area"):
            loc["sub_area"] = side_loc["sub_area"]
        listing["location"] = loc or None

    # --- lat/lng from map (detail page) ---
    map_loc = parse_map_lat_lng_propertia(soup)
    if map_loc:
        loc = listing.get("location") or {}
        if not isinstance(loc, dict):
            loc = {}

        if loc.get("latitude") is None and map_loc.get("latitude") is not None:
            loc["latitude"] = map_loc["latitude"]
        if loc.get("longitude") is None and map_loc.get("longitude") is not None:
            loc["longitude"] = map_loc["longitude"]

        listing["location"] = loc or None

    # ✅ TRANSFER ke preview (item dari list_items)
    _patch_preview_location(item, listing.get("location"), map_loc)


    # pricing
    if price_per_are_per_year:
        listing["raw"].setdefault("pricing", {})["price_per_are_per_year"] = price_per_are_per_year

    return listing