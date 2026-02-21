# # # import re
# # # import time
# # # import requests
# # # from bs4 import BeautifulSoup
# # # from typing import Optional

# # # HEADERS = {
# # #     "User-Agent": "Mozilla/5.0",
# # #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
# # # }

# # # def fetch_html(url: str, timeout: int = 30, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
# # #     """
# # #     Fetch HTML detail page dengan:
# # #     - timeout
# # #     - raise_for_status
# # #     - retry/backoff
# # #     - blocked detection 403/429
# # #     """
# # #     last_err = None
# # #     for attempt in range(1, retries + 1):
# # #         try:
# # #             resp = requests.get(url, headers=HEADERS, timeout=timeout)

# # #             # blocked detection ringan
# # #             if resp.status_code in (403, 429):
# # #                 print(f"[BLOCKED] {resp.status_code} on {url}")
# # #                 return None

# # #             resp.raise_for_status()
# # #             return resp.text

# # #         except Exception as e:
# # #             last_err = e
# # #             if attempt < retries:
# # #                 sleep_s = backoff * attempt
# # #                 time.sleep(sleep_s)
# # #             else:
# # #                 print(f"[FAILED] {url} error={last_err}")
# # #                 return None

# # #     return None


# # # def parse_price(raw: str):
# # #     """
# # #     Return dict:
# # #     {
# # #       "raw": "...",
# # #       "currency": "IDR"/"USD"/...,
# # #       "amount": int/None,
# # #       "period": "month"/"year"/None,
# # #       "unit": None,
# # #       "flags": {"poa": bool, "contact": bool, "negotiable": bool}
# # #     }
# # #     """
# # #     if not raw:
# # #         return None

# # #     text = " ".join(raw.split())
# # #     low = text.lower()

# # #     flags = {
# # #         "poa": ("poa" in low) or ("price on application" in low),
# # #         "contact": ("contact" in low) or ("call" in low) or ("enquire" in low),
# # #         "negotiable": ("nego" in low) or ("negotiable" in low),
# # #     }

# # #     # period (rent)
# # #     period = None
# # #     if "/month" in low or "per month" in low or "monthly" in low:
# # #         period = "month"
# # #     elif "/year" in low or "per year" in low or "yearly" in low:
# # #         period = "year"
# # #     elif "/night" in low or "per night" in low:
# # #         period = "night"
# # #     elif "/day" in low or "per day" in low:
# # #         period = "day"

# # #     # currency detection
# # #     currency = None
# # #     if "idr" in low or "rp" in low:
# # #         currency = "IDR"
# # #     elif "usd" in low or "$" in text:
# # #         currency = "USD"
# # #     elif "aud" in low:
# # #         currency = "AUD"
# # #     elif "eur" in low or "€" in text:
# # #         currency = "EUR"

# # #     # kalau POA / contact, amount boleh None
# # #     if flags["poa"] or flags["contact"]:
# # #         return {
# # #             "raw": text,
# # #             "currency": currency,
# # #             "amount": None,
# # #             "period": period,
# # #             "unit": None,
# # #             "flags": flags,
# # #         }

# # #     # handle shorthand: 4.3B / 250K / 50M
# # #     m = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])\b", low)
# # #     if m:
# # #         num = float(m.group(1))
# # #         suf = m.group(2)
# # #         mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suf]
# # #         amount = int(num * mult)
# # #         return {
# # #             "raw": text,
# # #             "currency": currency,
# # #             "amount": amount,
# # #             "period": period,
# # #             "unit": None,
# # #             "flags": flags,
# # #         }

# # #     # normal digits: remove everything except digits
# # #     digits = re.sub(r"[^\d]", "", text)
# # #     amount = int(digits) if digits else None

# # #     return {
# # #         "raw": text,
# # #         "currency": currency,
# # #         "amount": amount,
# # #         "period": period,
# # #         "unit": None,
# # #         "flags": flags,
# # #     }



# # # def extract_measure(text):
# # #     """
# # #     Extract numeric value + unit
# # #     '85 m²' -> (85.0, 'm²')
# # #     '1.69 Are' -> (1.69, 'Are')
# # #     """
# # #     if not text:
# # #         return None, None

# # #     cleaned = text.replace(",", "").strip()

# # #     num_match = re.search(r"[\d.]+", cleaned)
# # #     value = float(num_match.group()) if num_match else None

# # #     unit = re.sub(r"[\d.,\s]", "", cleaned)
# # #     unit = unit or None

# # #     return value, unit


# # # def extract_description(soup):
# # #     container = soup.select_one(".description-content")
# # #     if not container:
# # #         return None

# # #     # remove read-more button if exists
# # #     for btn in container.select(".houzez-read-more-link"):
# # #         btn.decompose()

# # #     texts = [
# # #         p.get_text(" ", strip=True)
# # #         for p in container.select("p")
# # #         if p.get_text(strip=True)
# # #     ]

# # #     if not texts:
# # #         return None

# # #     # normalize whitespace
# # #     return " ".join(" ".join(texts).split())


# # # def extract_features(soup):
# # #     container = soup.select_one("#property-features-wrap")
# # #     if not container:
# # #         return [], {}

# # #     all_features = []
# # #     grouped = {}
# # #     current_group = None

# # #     for el in container.select(".block-content-wrap > *"):
# # #         if "group_name" in el.get("class", []):
# # #             current_group = el.get_text(strip=True)
# # #             grouped[current_group] = []
# # #         elif el.name == "ul" and current_group:
# # #             for a in el.select("li a"):
# # #                 txt = a.get_text(strip=True)
# # #                 if txt:
# # #                     grouped[current_group].append(txt)
# # #                     all_features.append(txt)

# # #     return all_features, grouped


# # # def extract_images(soup):
# # #     images = []
# # #     for img in soup.select(".hs-gallery-v4-grid img"):
# # #         src = img.get("src")
# # #         if src and "wp-content/uploads" in src:
# # #             images.append(src)

# # #     # dedupe keep order
# # #     images = list(dict.fromkeys(images))
# # #     return images if images else None



# # # def parse_travel_time(text: str):
# # #     """
# # #     "5 Minutes by walk" -> {"minutes": 5, "mode": "walk", "raw": "..."}
# # #     "15 min by car" -> {"minutes": 15, "mode": "car", "raw": "..."}
# # #     Jika gagal parse -> {"raw": "..."}
# # #     """
# # #     if not text:
# # #         return None

# # #     raw = " ".join(text.split())  # normalize whitespace
# # #     lower = raw.lower()

# # #     # ambil angka pertama
# # #     m = re.search(r"(\d+(?:\.\d+)?)", lower)
# # #     minutes = None
# # #     if m:
# # #         try:
# # #             minutes = float(m.group(1))
# # #             # kebanyakan minutes integer
# # #             if minutes.is_integer():
# # #                 minutes = int(minutes)
# # #         except:
# # #             minutes = None

# # #     # ambil mode setelah kata "by"
# # #     mode = None
# # #     m2 = re.search(r"\bby\s+([a-z]+)", lower)
# # #     if m2:
# # #         mode = m2.group(1)

# # #     out = {"raw": raw}
# # #     if minutes is not None:
# # #         out["minutes"] = minutes
# # #     if mode:
# # #         out["mode"] = mode
# # #     return out


# # # # def extract_neighborhood(soup):
# # # #     wrap = soup.select_one("#property-neighborhood-wrap")
# # # #     if not wrap:
# # # #         return None

# # # #     data = {}

# # # #     # setiap item biasanya punya <label> + <div class="single_field_nhood"><span>...</span></div>
# # # #     for item in wrap.select(".block-content-wrap > div"):
# # # #         label_el = item.select_one("label")
# # # #         value_el = item.select_one(".single_field_nhood span")

# # # #         label = label_el.get_text(" ", strip=True) if label_el else None
# # # #         value = value_el.get_text(" ", strip=True) if value_el else None

# # # #         if label and value:
# # # #             data[label] = value

# # # #     return data if data else None


# # # def extract_neighborhood(soup):
# # #     """
# # #     Return dict:
# # #     {
# # #       "Beach": {"minutes": 5, "mode": "walk", "raw": "..."},
# # #       "Airport": {"minutes": 50, "mode": "car", "raw": "..."},
# # #       ...
# # #     }
# # #     """
# # #     wrap = soup.select_one("#property-neighborhood-wrap")
# # #     if not wrap:
# # #         return None

# # #     data = {}

# # #     for item in wrap.select(".block-content-wrap > div"):
# # #         label_el = item.select_one("label")
# # #         value_el = item.select_one(".single_field_nhood span")

# # #         label = label_el.get_text(" ", strip=True) if label_el else None
# # #         value = value_el.get_text(" ", strip=True) if value_el else None

# # #         if label and value:
# # #             data[label] = parse_travel_time(value)

# # #     return data if data else None

# # # def scrape_property_detail(url):
# # #     print("Scraping:", url)

# # #     html = fetch_html(url, timeout=30, retries=3, backoff=2.0)
# # #     if not html:
# # #         return None

# # #     # ✅ FIX: parse dari html string
# # #     soup = BeautifulSoup(html, "html.parser")

# # #     # TITLE
# # #     title_tag = soup.select_one(".page-title h1")
# # #     title = title_tag.get_text(strip=True) if title_tag else None

# # #     # ADDRESS
# # #     address_tag = soup.select_one("address.item-address")
# # #     address = address_tag.get_text(strip=True) if address_tag else None

# # #     # PRICE
# # #     price_tag = soup.select_one(".item-price .price")
# # #     price_raw = price_tag.get_text(strip=True) if price_tag else None
# # #     price = parse_price(price_raw)

# # #     # LABELS (remove duplicates keep order)
# # #     labels = []
# # #     for a in soup.select(".property-labels-wrap a"):
# # #         txt = a.get_text(strip=True)
# # #         if txt:
# # #             labels.append(txt)
# # #     labels = list(dict.fromkeys(labels))

# # #     # FACTS
# # #     facts = {}
# # #     for li in soup.select("#property-detail-wrap li"):
# # #         key_tag = li.find("strong")
# # #         val_tag = li.find("span")

# # #         if key_tag and val_tag:
# # #             key = key_tag.get_text(strip=True).lower().replace(" ", "_")
# # #             value = val_tag.get_text(strip=True)
# # #             facts[key] = value

# # #     property_id = facts.get("property_id")
# # #     property_status = facts.get("property_status")
# # #     property_type = facts.get("property_type")
# # #     bedrooms = facts.get("bedrooms")
# # #     bathrooms = facts.get("bathrooms")
# # #     building_size_text = facts.get("building_size")
# # #     land_size_text = facts.get("land_size")
# # #     year_built = facts.get("year_built")
# # #     area = facts.get("area")
# # #     years = facts.get("years")

# # #     # year built -> int
# # #     if year_built and str(year_built).isdigit():
# # #         year_built = int(year_built)

# # #     building_size_value, building_size_unit = extract_measure(building_size_text)
# # #     land_size_value, land_size_unit = extract_measure(land_size_text)

# # #     features, feature_groups = extract_features(soup)
# # #     neighborhood = extract_neighborhood(soup)
# # #     images = extract_images(soup)

# # #     return {
# # #         "title": title,
# # #         "url": url,
# # #         "property_id": property_id,
# # #         "property_status": property_status,
# # #         "property_type": property_type,
# # #         "price": price,
# # #         "years": years,
# # #         "bedrooms": bedrooms,
# # #         "bathrooms": bathrooms,
# # #         "building_size": building_size_text,
# # #         "building_size_value": building_size_value,
# # #         "building_size_unit": building_size_unit,
# # #         "land_size": land_size_text,
# # #         "land_size_value": land_size_value,
# # #         "land_size_unit": land_size_unit,
# # #         "year_built": year_built,
# # #         "area": area,
# # #         "address": address,
# # #         "labels": labels,
# # #         "neighborhood": neighborhood,
# # #         "description": extract_description(soup),
# # #         "features": features,
# # #         "feature_groups": feature_groups,
# # #         "images": images,
# # #     }

# # # # =====================
# # # # TEST
# # # # =====================

# # # if __name__ == "__main__":
# # #     # test_url = "https://propertia.com/property/ready-to-move-in-2-bedroom-villa-in-prime-pererenan/"
# # #     test_url = "https://propertia.com/property/magnificent-beachfront-property-in-buleleng/"
# # #     data = scrape_property_detail(test_url)

# # #     from pprint import pprint
# # #     pprint(data)



# # import re
# # import os
# # import time
# # import random
# # import requests
# # from bs4 import BeautifulSoup
# # from typing import Optional, Dict, Any, Tuple

# # # =====================
# # # CONFIG
# # # =====================

# # HEADERS_BASE = {
# #     "User-Agent": "Mozilla/5.0",  # akan dioverride oleh UA rotate (optional)
# #     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
# # }

# # # OPTIONAL: rotate UA biar lebih aman
# # USER_AGENTS = [
# #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
# #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
# #     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
# #     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
# # ]

# # BLOCKED_STATUS = {403, 429}

# # # folder debug html (kalau benar2 kena protection)
# # DEBUG_DIR = "debug_html"
# # os.makedirs(DEBUG_DIR, exist_ok=True)


# # # =====================
# # # PROTECTION DETECTION
# # # =====================

# # def looks_like_challenge(html: str) -> bool:
# #     """
# #     Deteksi page proteksi/antibot secara lebih akurat (tidak sekadar keyword 'captcha').
# #     """
# #     if not html:
# #         return False

# #     low = html.lower()

# #     patterns = (
# #         "just a moment",
# #         "checking your browser",
# #         "attention required",
# #         "cf-challenge",
# #         "cf-turnstile",
# #         "/cdn-cgi/challenge-platform",
# #         "cloudflare ray id",
# #         "ddos protection",
# #         "verify you are human",
# #         "are you a robot",
# #         "security check",
# #         "access denied",
# #     )
# #     if any(p in low for p in patterns):
# #         return True

# #     # Marker yang sering muncul pada challenge page
# #     if re.search(r"cdn-cgi|cf-ray|cf-chl", low):
# #         return True

# #     return False


# # def dump_debug_html(url: str, html: str, reason: str = "challenge") -> str:
# #     safe = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
# #     safe = safe[:120] if len(safe) > 120 else safe
# #     path = os.path.join(DEBUG_DIR, f"{reason}_{safe}.html")
# #     try:
# #         with open(path, "w", encoding="utf-8") as f:
# #             f.write(html or "")
# #     except Exception:
# #         pass
# #     return path


# # # =====================
# # # HTTP FETCH
# # # =====================

# # def fetch_html(
# #     session: requests.Session,
# #     url: str,
# #     timeout: int = 30,
# #     retries: int = 3,
# #     backoff: float = 2.0,
# #     jitter: float = 0.5,
# # ) -> Optional[str]:
# #     """
# #     Fetch HTML detail page:
# #     - timeout
# #     - retry/backoff
# #     - blocked detection 403/429
# #     - protection/challenge detection (Cloudflare, etc.)
# #     - dump debug html kalau terdeteksi challenge
# #     """
# #     last_err = None

# #     for attempt in range(1, retries + 1):
# #         try:
# #             headers = dict(HEADERS_BASE)
# #             headers["User-Agent"] = random.choice(USER_AGENTS)

# #             resp = session.get(url, headers=headers, timeout=timeout)

# #             if resp.status_code in BLOCKED_STATUS:
# #                 print(f"[BLOCKED] {resp.status_code} on {url}")
# #                 dump_debug_html(url, resp.text or "", reason=f"blocked_{resp.status_code}")
# #                 return None

# #             resp.raise_for_status()
# #             html = resp.text or ""

# #             # ✅ deteksi challenge page secara lebih spesifik
# #             if looks_like_challenge(html):
# #                 path = dump_debug_html(url, html, reason="challenge")
# #                 print(f"[PROTECTION PAGE] detected on {url} (saved: {path})")
# #                 return None

# #             return html

# #         except Exception as e:
# #             last_err = e
# #             if attempt < retries:
# #                 sleep_s = (backoff * attempt) + random.uniform(0, jitter)
# #                 time.sleep(sleep_s)
# #             else:
# #                 print(f"[FAILED] {url} error={last_err}")
# #                 return None

# #     return None


# # # =====================
# # # PARSERS
# # # =====================

# # def parse_price(raw: str) -> Optional[Dict[str, Any]]:
# #     """
# #     Return dict:
# #     {
# #       "raw": "...",
# #       "currency": "IDR"/"USD"/...,
# #       "amount": int/None,
# #       "period": "month"/"year"/"day"/"night"/None,
# #       "unit": None,
# #       "flags": {"poa": bool, "contact": bool, "negotiable": bool}
# #     }
# #     """
# #     if not raw:
# #         return None

# #     text = " ".join(raw.split())
# #     low = text.lower()

# #     flags = {
# #         "poa": ("poa" in low) or ("price on application" in low),
# #         "contact": ("contact" in low) or ("call" in low) or ("enquire" in low),
# #         "negotiable": ("nego" in low) or ("negotiable" in low),
# #     }

# #     period = None
# #     if "/month" in low or "per month" in low or "monthly" in low:
# #         period = "month"
# #     elif "/year" in low or "per year" in low or "yearly" in low:
# #         period = "year"
# #     elif "/night" in low or "per night" in low:
# #         period = "night"
# #     elif "/day" in low or "per day" in low:
# #         period = "day"

# #     currency = None
# #     if "idr" in low or "rp" in low:
# #         currency = "IDR"
# #     elif "usd" in low or "$" in text:
# #         currency = "USD"
# #     elif "aud" in low:
# #         currency = "AUD"
# #     elif "eur" in low or "€" in text:
# #         currency = "EUR"

# #     if flags["poa"] or flags["contact"]:
# #         return {"raw": text, "currency": currency, "amount": None, "period": period, "unit": None, "flags": flags}

# #     # shorthand: 4.3B / 250K / 50M
# #     m = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])\b", low)
# #     if m:
# #         num = float(m.group(1))
# #         suf = m.group(2)
# #         mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suf]
# #         amount = int(num * mult)
# #         return {"raw": text, "currency": currency, "amount": amount, "period": period, "unit": None, "flags": flags}

# #     digits = re.sub(r"[^\d]", "", text)
# #     amount = int(digits) if digits else None
# #     return {"raw": text, "currency": currency, "amount": amount, "period": period, "unit": None, "flags": flags}


# # def extract_measure(text: Optional[str]):
# #     if not text:
# #         return None, None

# #     cleaned = text.replace(",", "").strip()
# #     num_match = re.search(r"[\d.]+", cleaned)
# #     value = float(num_match.group()) if num_match else None

# #     unit = re.sub(r"[\d.,\s]", "", cleaned)
# #     unit = unit or None
# #     return value, unit


# # def extract_description(soup: BeautifulSoup) -> Optional[str]:
# #     container = soup.select_one(".description-content")
# #     if not container:
# #         return None

# #     for btn in container.select(".houzez-read-more-link"):
# #         btn.decompose()

# #     texts = [p.get_text(" ", strip=True) for p in container.select("p") if p.get_text(strip=True)]
# #     if not texts:
# #         return None

# #     return " ".join(" ".join(texts).split())


# # def extract_features(soup: BeautifulSoup):
# #     container = soup.select_one("#property-features-wrap")
# #     if not container:
# #         return [], {}

# #     all_features = []
# #     grouped = {}
# #     current_group = None

# #     for el in container.select(".block-content-wrap > *"):
# #         if "group_name" in el.get("class", []):
# #             current_group = el.get_text(strip=True)
# #             grouped[current_group] = []
# #         elif el.name == "ul" and current_group:
# #             for a in el.select("li a"):
# #                 txt = a.get_text(strip=True)
# #                 if txt:
# #                     grouped[current_group].append(txt)
# #                     all_features.append(txt)

# #     return all_features, grouped


# # def extract_images(soup: BeautifulSoup):
# #     images = []
# #     for img in soup.select(".hs-gallery-v4-grid img"):
# #         src = img.get("src")
# #         if src and "wp-content/uploads" in src:
# #             images.append(src)

# #     images = list(dict.fromkeys(images))
# #     return images if images else None


# # def parse_travel_time(text: str):
# #     if not text:
# #         return None

# #     raw = " ".join(text.split())
# #     lower = raw.lower()

# #     m = re.search(r"(\d+(?:\.\d+)?)", lower)
# #     minutes = None
# #     if m:
# #         try:
# #             minutes = float(m.group(1))
# #             if minutes.is_integer():
# #                 minutes = int(minutes)
# #         except Exception:
# #             minutes = None

# #     mode = None
# #     m2 = re.search(r"\bby\s+([a-z]+)", lower)
# #     if m2:
# #         mode = m2.group(1)

# #     out = {"raw": raw}
# #     if minutes is not None:
# #         out["minutes"] = minutes
# #     if mode:
# #         out["mode"] = mode
# #     return out


# # def extract_neighborhood(soup: BeautifulSoup):
# #     wrap = soup.select_one("#property-neighborhood-wrap")
# #     if not wrap:
# #         return None

# #     data = {}
# #     for item in wrap.select(".block-content-wrap > div"):
# #         label_el = item.select_one("label")
# #         value_el = item.select_one(".single_field_nhood span")

# #         label = label_el.get_text(" ", strip=True) if label_el else None
# #         value = value_el.get_text(" ", strip=True) if value_el else None

# #         if label and value:
# #             data[label] = parse_travel_time(value)

# #     return data if data else None


# # # =====================
# # # MAIN SCRAPER
# # # =====================

# # def scrape_property_detail(
# #     url: str,
# #     session: Optional[requests.Session] = None,
# #     delay_range: Optional[Tuple[float, float]] = None,
# # ) -> Optional[Dict[str, Any]]:
# #     """
# #     session: reuse dari scraper utama (lebih cepat/stabil)
# #     delay_range: (min,max) delay random sebelum request
# #     """
# #     owns_session = False
# #     if session is None:
# #         session = requests.Session()
# #         owns_session = True

# #     try:
# #         if delay_range:
# #             time.sleep(random.uniform(delay_range[0], delay_range[1]))

# #         html = fetch_html(session, url, timeout=30, retries=3, backoff=2.0, jitter=0.7)
# #         if not html:
# #             return None

# #         soup = BeautifulSoup(html, "html.parser")

# #         # TITLE
# #         title_tag = soup.select_one(".page-title h1")
# #         title = title_tag.get_text(strip=True) if title_tag else None

# #         # ADDRESS
# #         address_tag = soup.select_one("address.item-address")
# #         address = address_tag.get_text(strip=True) if address_tag else None

# #         # PRICE (structured)
# #         price_tag = soup.select_one(".item-price .price")
# #         price_raw = price_tag.get_text(strip=True) if price_tag else None
# #         price = parse_price(price_raw)

# #         # LABELS
# #         labels = []
# #         for a in soup.select(".property-labels-wrap a"):
# #             txt = a.get_text(strip=True)
# #             if txt:
# #                 labels.append(txt)
# #         labels = list(dict.fromkeys(labels))

# #         # FACTS
# #         facts = {}
# #         for li in soup.select("#property-detail-wrap li"):
# #             key_tag = li.find("strong")
# #             val_tag = li.find("span")
# #             if key_tag and val_tag:
# #                 key = key_tag.get_text(strip=True).lower().replace(" ", "_")
# #                 value = val_tag.get_text(strip=True)
# #                 facts[key] = value

# #         property_id = facts.get("property_id")
# #         property_status = facts.get("property_status")
# #         property_type = facts.get("property_type")
# #         bedrooms = facts.get("bedrooms")
# #         bathrooms = facts.get("bathrooms")
# #         building_size_text = facts.get("building_size")
# #         land_size_text = facts.get("land_size")
# #         year_built = facts.get("year_built")
# #         area = facts.get("area")
# #         years = facts.get("years")
# #         price_per_are_per_year = facts.get("price_per_are_per_year")

# #         if year_built and str(year_built).isdigit():
# #             year_built = int(year_built)

# #         building_size_value, building_size_unit = extract_measure(building_size_text)
# #         land_size_value, land_size_unit = extract_measure(land_size_text)

# #         features, feature_groups = extract_features(soup)
# #         neighborhood = extract_neighborhood(soup)
# #         images = extract_images(soup)

# #         return {
# #             "title": title,
# #             "url": url,
# #             "property_id": property_id,
# #             "property_status": property_status,
# #             "property_type": property_type,
# #             "price": price,
# #             "years": years,
# #             "price_per_are_per_year": price_per_are_per_year,
# #             "bedrooms": bedrooms,
# #             "bathrooms": bathrooms,
# #             "building_size": building_size_text,
# #             "building_size_value": building_size_value,
# #             "building_size_unit": building_size_unit,
# #             "land_size": land_size_text,
# #             "land_size_value": land_size_value,
# #             "land_size_unit": land_size_unit,
# #             "year_built": year_built,
# #             "area": area,
# #             "address": address,
# #             "labels": labels,
# #             "neighborhood": neighborhood,
# #             "description": extract_description(soup),
# #             "features": features,
# #             "feature_groups": feature_groups,
# #             "images": images,
# #         }

# #     finally:
# #         if owns_session:
# #             session.close()


# # if __name__ == "__main__":
# #     test_url = "https://propertia.com/property/magnificent-beachfront-property-in-buleleng/"
# #     data = scrape_property_detail(test_url)
# #     from pprint import pprint
# #     pprint(data)



# import re
# import os
# import time
# import random
# import requests
# from bs4 import BeautifulSoup
# from typing import Optional, Dict, Any, Tuple

# # =====================
# # CONFIG
# # =====================

# HEADERS_BASE = {
#     "User-Agent": "Mozilla/5.0",
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
# }

# # OPTIONAL: rotate UA biar lebih aman
# USER_AGENTS = [
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
#     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
#     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
#     "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
# ]

# BLOCKED_STATUS = {403, 429}

# # folder debug html (kalau benar2 kena protection)
# DEBUG_DIR = "debug_html"
# os.makedirs(DEBUG_DIR, exist_ok=True)


# # =====================
# # HELPERS
# # =====================

# def norm_key(text: str) -> str:
#     """
#     Normalisasi key facts:
#     "Price per Are per year" -> "price_per_are_per_year"
#     """
#     text = (text or "").strip().lower()
#     text = re.sub(r"[^a-z0-9]+", "_", text)
#     return text.strip("_")


# def looks_like_challenge(html: str) -> bool:
#     """
#     Deteksi antibot/challenge secara lebih akurat (hindari false positive keyword 'captcha').
#     """
#     if not html:
#         return False

#     low = html.lower()

#     patterns = (
#         "just a moment",
#         "checking your browser",
#         "attention required",
#         "cf-challenge",
#         "cf-turnstile",
#         "/cdn-cgi/challenge-platform",
#         "cloudflare ray id",
#         "ddos protection",
#         "verify you are human",
#         "are you a robot",
#         "security check",
#         "access denied",
#     )
#     if any(p in low for p in patterns):
#         return True

#     # marker umum challenge page
#     if re.search(r"cdn-cgi|cf-ray|cf-chl", low):
#         return True

#     return False


# def dump_debug_html(url: str, html: str, reason: str = "challenge") -> str:
#     safe = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
#     safe = safe[:120] if len(safe) > 120 else safe
#     path = os.path.join(DEBUG_DIR, f"{reason}_{safe}.html")
#     try:
#         with open(path, "w", encoding="utf-8") as f:
#             f.write(html or "")
#     except Exception:
#         pass
#     return path


# # =====================
# # HTTP
# # =====================

# def fetch_html(
#     session: requests.Session,
#     url: str,
#     timeout: int = 30,
#     retries: int = 3,
#     backoff: float = 2.0,
#     jitter: float = 0.7,
# ) -> Optional[str]:
#     """
#     Fetch HTML detail page:
#     - timeout
#     - retry/backoff
#     - blocked detection 403/429
#     - protection/challenge detection
#     - dump debug html kalau challenge
#     """
#     last_err = None

#     for attempt in range(1, retries + 1):
#         try:
#             headers = dict(HEADERS_BASE)
#             headers["User-Agent"] = random.choice(USER_AGENTS)

#             resp = session.get(url, headers=headers, timeout=timeout)

#             if resp.status_code in BLOCKED_STATUS:
#                 print(f"[BLOCKED] {resp.status_code} on {url}")
#                 dump_debug_html(url, resp.text or "", reason=f"blocked_{resp.status_code}")
#                 return None

#             resp.raise_for_status()
#             html = resp.text or ""

#             if looks_like_challenge(html):
#                 path = dump_debug_html(url, html, reason="challenge")
#                 print(f"[PROTECTION PAGE] detected on {url} (saved: {path})")
#                 return None

#             return html

#         except Exception as e:
#             last_err = e
#             if attempt < retries:
#                 sleep_s = (backoff * attempt) + random.uniform(0, jitter)
#                 time.sleep(sleep_s)
#             else:
#                 print(f"[FAILED] {url} error={last_err}")
#                 return None

#     return None


# # =====================
# # PARSERS
# # =====================

# def parse_price(raw: str) -> Optional[Dict[str, Any]]:
#     """
#     Return dict:
#     {
#       "raw": "...",
#       "currency": "IDR"/"USD"/...,
#       "amount": int/None,
#       "period": "month"/"year"/"day"/"night"/None,
#       "unit": None,
#       "flags": {"poa": bool, "contact": bool, "negotiable": bool}
#     }
#     """
#     if not raw:
#         return None

#     text = " ".join(raw.split())
#     low = text.lower()

#     flags = {
#         "poa": ("poa" in low) or ("price on application" in low),
#         "contact": ("contact" in low) or ("call" in low) or ("enquire" in low),
#         "negotiable": ("nego" in low) or ("negotiable" in low),
#     }

#     # period detection (rent)
#     period = None
#     if "/month" in low or "per month" in low or "monthly" in low:
#         period = "month"
#     elif "/year" in low or "per year" in low or "yearly" in low:
#         period = "year"
#     elif "/night" in low or "per night" in low:
#         period = "night"
#     elif "/day" in low or "per day" in low:
#         period = "day"

#     # currency detection
#     currency = None
#     if "idr" in low or "rp" in low:
#         currency = "IDR"
#     elif "usd" in low or "$" in text:
#         currency = "USD"
#     elif "aud" in low:
#         currency = "AUD"
#     elif "eur" in low or "€" in text:
#         currency = "EUR"

#     # POA/contact -> amount None
#     if flags["poa"] or flags["contact"]:
#         return {
#             "raw": text,
#             "currency": currency,
#             "amount": None,
#             "period": period,
#             "unit": None,
#             "flags": flags,
#         }

#     # shorthand: 4.3B / 250K / 50M
#     m = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])\b", low)
#     if m:
#         num = float(m.group(1))
#         suf = m.group(2)
#         mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suf]
#         amount = int(num * mult)
#         return {
#             "raw": text,
#             "currency": currency,
#             "amount": amount,
#             "period": period,
#             "unit": None,
#             "flags": flags,
#         }

#     # normal digits
#     digits = re.sub(r"[^\d]", "", text)
#     amount = int(digits) if digits else None

#     return {
#         "raw": text,
#         "currency": currency,
#         "amount": amount,
#         "period": period,
#         "unit": None,
#         "flags": flags,
#     }


# def extract_measure(text: Optional[str]):
#     """
#     '85 m²' -> (85.0, 'm²')
#     '1.69 Are' -> (1.69, 'Are')
#     """
#     if not text:
#         return None, None

#     cleaned = text.replace(",", "").strip()
#     num_match = re.search(r"[\d.]+", cleaned)
#     value = float(num_match.group()) if num_match else None

#     unit = re.sub(r"[\d.,\s]", "", cleaned)
#     unit = unit or None
#     return value, unit


# def extract_description(soup: BeautifulSoup) -> Optional[str]:
#     container = soup.select_one(".description-content")
#     if not container:
#         return None

#     for btn in container.select(".houzez-read-more-link"):
#         btn.decompose()

#     texts = [p.get_text(" ", strip=True) for p in container.select("p") if p.get_text(strip=True)]
#     if not texts:
#         return None

#     return " ".join(" ".join(texts).split())


# def extract_features(soup: BeautifulSoup):
#     container = soup.select_one("#property-features-wrap")
#     if not container:
#         return [], {}

#     all_features = []
#     grouped = {}
#     current_group = None

#     for el in container.select(".block-content-wrap > *"):
#         if "group_name" in el.get("class", []):
#             current_group = el.get_text(strip=True)
#             grouped[current_group] = []
#         elif el.name == "ul" and current_group:
#             for a in el.select("li a"):
#                 txt = a.get_text(strip=True)
#                 if txt:
#                     grouped[current_group].append(txt)
#                     all_features.append(txt)

#     return all_features, grouped


# def extract_images(soup: BeautifulSoup):
#     images = []
#     for img in soup.select(".hs-gallery-v4-grid img"):
#         src = img.get("src")
#         if src and "wp-content/uploads" in src:
#             images.append(src)

#     images = list(dict.fromkeys(images))
#     return images if images else None


# def parse_travel_time(text: str):
#     """
#     "5 Minutes by walk" -> {"minutes": 5, "mode": "walk", "raw": "..."}
#     """
#     if not text:
#         return None

#     raw = " ".join(text.split())
#     lower = raw.lower()

#     m = re.search(r"(\d+(?:\.\d+)?)", lower)
#     minutes = None
#     if m:
#         try:
#             minutes = float(m.group(1))
#             if minutes.is_integer():
#                 minutes = int(minutes)
#         except Exception:
#             minutes = None

#     mode = None
#     m2 = re.search(r"\bby\s+([a-z]+)", lower)
#     if m2:
#         mode = m2.group(1)

#     out = {"raw": raw}
#     if minutes is not None:
#         out["minutes"] = minutes
#     if mode:
#         out["mode"] = mode
#     return out


# def extract_neighborhood(soup: BeautifulSoup):
#     """
#     Return dict:
#     {
#       "Beach": {"minutes": 5, "mode": "walk", "raw": "..."},
#       ...
#     }
#     """
#     wrap = soup.select_one("#property-neighborhood-wrap")
#     if not wrap:
#         return None

#     data = {}
#     for item in wrap.select(".block-content-wrap > div"):
#         label_el = item.select_one("label")
#         value_el = item.select_one(".single_field_nhood span")

#         label = label_el.get_text(" ", strip=True) if label_el else None
#         value = value_el.get_text(" ", strip=True) if value_el else None

#         if label and value:
#             data[label] = parse_travel_time(value)

#     return data if data else None


# # =====================
# # MAIN SCRAPER
# # =====================

# def scrape_property_detail(
#     url: str,
#     session: Optional[requests.Session] = None,
#     delay_range: Optional[Tuple[float, float]] = None,
# ) -> Optional[Dict[str, Any]]:
#     """
#     session: reuse dari scraper utama (lebih cepat/stabil)
#     delay_range: (min,max) delay random sebelum request
#     """
#     owns_session = False
#     if session is None:
#         session = requests.Session()
#         owns_session = True

#     try:
#         if delay_range:
#             time.sleep(random.uniform(delay_range[0], delay_range[1]))

#         html = fetch_html(session, url, timeout=30, retries=3, backoff=2.0, jitter=0.7)
#         if not html:
#             return None

#         soup = BeautifulSoup(html, "html.parser")

#         # TITLE
#         title_tag = soup.select_one(".page-title h1")
#         title = title_tag.get_text(strip=True) if title_tag else None

#         # ADDRESS
#         address_tag = soup.select_one("address.item-address")
#         address = address_tag.get_text(strip=True) if address_tag else None

#         # PRICE (structured)
#         price_tag = soup.select_one(".item-price .price")
#         price_raw = price_tag.get_text(strip=True) if price_tag else None
#         price = parse_price(price_raw)

#         # LABELS
#         labels = []
#         for a in soup.select(".property-labels-wrap a"):
#             txt = a.get_text(strip=True)
#             if txt:
#                 labels.append(txt)
#         labels = list(dict.fromkeys(labels))

#         # FACTS
#         facts = {}
#         for li in soup.select("#property-detail-wrap li"):
#             key_tag = li.find("strong")
#             val_tag = li.find("span")
#             if key_tag and val_tag:
#                 key = norm_key(key_tag.get_text(" ", strip=True))
#                 value = val_tag.get_text(" ", strip=True)
#                 facts[key] = value

#         # basic facts
#         property_id = facts.get("property_id")
#         property_status = facts.get("property_status")
#         property_type = facts.get("property_type")
#         bedrooms = facts.get("bedrooms")
#         bathrooms = facts.get("bathrooms")
#         building_size_text = facts.get("building_size")
#         land_size_text = facts.get("land_size")
#         year_built = facts.get("year_built")
#         area = facts.get("area")
#         years = facts.get("years")

#         # NEW: price per are per year (structured)
#         ppa_raw = facts.get("price_per_are_per_year")
#         price_per_are_per_year = parse_price(ppa_raw) if ppa_raw else None
#         if price_per_are_per_year:
#             # enforce unit/period for consistency
#             price_per_are_per_year["unit"] = "are"
#             price_per_are_per_year["period"] = price_per_are_per_year.get("period") or "year"

#         if year_built and str(year_built).isdigit():
#             year_built = int(year_built)

#         building_size_value, building_size_unit = extract_measure(building_size_text)
#         land_size_value, land_size_unit = extract_measure(land_size_text)

#         features, feature_groups = extract_features(soup)
#         neighborhood = extract_neighborhood(soup)
#         images = extract_images(soup)

#         return {
#             "title": title,
#             "url": url,
#             "property_id": property_id,
#             "property_status": property_status,
#             "property_type": property_type,
#             "price": price,
#             "price_per_are_per_year": price_per_are_per_year, 
#             "years": years,
#             "bedrooms": bedrooms,
#             "bathrooms": bathrooms,
#             "building_size": building_size_text,
#             "building_size_value": building_size_value,
#             "building_size_unit": building_size_unit,
#             "land_size": land_size_text,
#             "land_size_value": land_size_value,
#             "land_size_unit": land_size_unit,
#             "year_built": year_built,
#             "area": area,
#             "address": address,
#             "labels": labels,
#             "neighborhood": neighborhood,
#             "description": extract_description(soup),
#             "features": features,
#             "feature_groups": feature_groups,
#             "images": images,
#         }

#     finally:
#         if owns_session:
#             session.close()


# if __name__ == "__main__":
#     test_url = "https://propertia.com/property/prime-commercial-land-in-bingin-for-high-growth-commercial-development/"
#     data = scrape_property_detail(test_url)
#     from pprint import pprint
#     pprint(data)


import re
import os
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, Tuple

# =====================
# CONFIG
# =====================

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36",
]

BLOCKED_STATUS = {403, 429}

DEBUG_DIR = "debug_html"
os.makedirs(DEBUG_DIR, exist_ok=True)


# =====================
# HELPERS
# =====================

def norm_key(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def looks_like_challenge(html: str) -> bool:
    if not html:
        return False

    low = html.lower()
    patterns = (
        "just a moment",
        "checking your browser",
        "attention required",
        "cf-challenge",
        "cf-turnstile",
        "/cdn-cgi/challenge-platform",
        "cloudflare ray id",
        "ddos protection",
        "verify you are human",
        "are you a robot",
        "security check",
        "access denied",
    )
    if any(p in low for p in patterns):
        return True

    if re.search(r"cdn-cgi|cf-ray|cf-chl", low):
        return True

    return False


def dump_debug_html(url: str, html: str, reason: str = "challenge") -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", url).strip("_")
    safe = safe[:120] if len(safe) > 120 else safe
    path = os.path.join(DEBUG_DIR, f"{reason}_{safe}.html")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html or "")
    except Exception:
        pass
    return path


def parse_int(value: Optional[str]) -> Optional[int]:
    """
    Robust int parser:
    - "23" -> 23
    - "23 Years" -> 23
    - "-" / "N/A" / "" -> None
    """
    if value is None:
        return None
    txt = str(value).strip()
    if not txt or txt.lower() in {"-", "n/a", "na", "none"}:
        return None

    m = re.search(r"(\d+)", txt)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def ensure_float(value: Optional[float]) -> Optional[float]:
    """
    Pastikan numeric selalu float (biar konsisten):
    - 3 -> 3.0
    - 7.28 -> 7.28
    """
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


# =====================
# HTTP
# =====================

def fetch_html(
    session: requests.Session,
    url: str,
    timeout: int = 30,
    retries: int = 3,
    backoff: float = 2.0,
    jitter: float = 0.7,
) -> Optional[str]:
    last_err = None

    for attempt in range(1, retries + 1):
        try:
            headers = dict(HEADERS_BASE)
            headers["User-Agent"] = random.choice(USER_AGENTS)

            resp = session.get(url, headers=headers, timeout=timeout)

            if resp.status_code in BLOCKED_STATUS:
                print(f"[BLOCKED] {resp.status_code} on {url}")
                dump_debug_html(url, resp.text or "", reason=f"blocked_{resp.status_code}")
                return None

            resp.raise_for_status()
            html = resp.text or ""

            if looks_like_challenge(html):
                path = dump_debug_html(url, html, reason="challenge")
                print(f"[PROTECTION PAGE] detected on {url} (saved: {path})")
                return None

            return html

        except Exception as e:
            last_err = e
            if attempt < retries:
                sleep_s = (backoff * attempt) + random.uniform(0, jitter)
                time.sleep(sleep_s)
            else:
                print(f"[FAILED] {url} error={last_err}")
                return None

    return None


# =====================
# PARSERS
# =====================

def parse_price(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    text = " ".join(raw.split())
    low = text.lower()

    flags = {
        "poa": ("poa" in low) or ("price on application" in low),
        "contact": ("contact" in low) or ("call" in low) or ("enquire" in low),
        "negotiable": ("nego" in low) or ("negotiable" in low),
    }

    period = None
    if "/month" in low or "per month" in low or "monthly" in low:
        period = "month"
    elif "/year" in low or "per year" in low or "yearly" in low:
        period = "year"
    elif "/night" in low or "per night" in low:
        period = "night"
    elif "/day" in low or "per day" in low:
        period = "day"

    currency = None
    if "idr" in low or "rp" in low:
        currency = "IDR"
    elif "usd" in low or "$" in text:
        currency = "USD"
    elif "aud" in low:
        currency = "AUD"
    elif "eur" in low or "€" in text:
        currency = "EUR"

    if flags["poa"] or flags["contact"]:
        return {"raw": text, "currency": currency, "amount": None, "period": period, "unit": None, "flags": flags}

    m = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])\b", low)
    if m:
        num = float(m.group(1))
        suf = m.group(2)
        mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suf]
        amount = int(num * mult)
        return {"raw": text, "currency": currency, "amount": amount, "period": period, "unit": None, "flags": flags}

    digits = re.sub(r"[^\d]", "", text)
    amount = int(digits) if digits else None

    return {"raw": text, "currency": currency, "amount": amount, "period": period, "unit": None, "flags": flags}


def extract_measure(text: Optional[str]):
    """
    Return (float_value, unit)
    """
    if not text:
        return None, None

    cleaned = str(text).replace(",", "").strip()

    num_match = re.search(r"[\d.]+", cleaned)
    value = float(num_match.group()) if num_match else None

    unit = re.sub(r"[\d.,\s]", "", cleaned)
    unit = unit or None

    return ensure_float(value), unit


def extract_description(soup: BeautifulSoup) -> Optional[str]:
    container = soup.select_one(".description-content")
    if not container:
        return None

    for btn in container.select(".houzez-read-more-link"):
        btn.decompose()

    texts = [p.get_text(" ", strip=True) for p in container.select("p") if p.get_text(strip=True)]
    if not texts:
        return None

    return " ".join(" ".join(texts).split())


def extract_features(soup: BeautifulSoup):
    container = soup.select_one("#property-features-wrap")
    if not container:
        return [], {}

    all_features = []
    grouped = {}
    current_group = None

    for el in container.select(".block-content-wrap > *"):
        if "group_name" in el.get("class", []):
            current_group = el.get_text(strip=True)
            grouped[current_group] = []
        elif el.name == "ul" and current_group:
            for a in el.select("li a"):
                txt = a.get_text(strip=True)
                if txt:
                    grouped[current_group].append(txt)
                    all_features.append(txt)

    return all_features, grouped


def extract_images(soup: BeautifulSoup):
    images = []
    for img in soup.select(".hs-gallery-v4-grid img"):
        src = img.get("src")
        if src and "wp-content/uploads" in src:
            images.append(src)

    images = list(dict.fromkeys(images))
    return images if images else None


def parse_travel_time(text: str):
    if not text:
        return None

    raw = " ".join(text.split())
    lower = raw.lower()

    m = re.search(r"(\d+(?:\.\d+)?)", lower)
    minutes = None
    if m:
        try:
            minutes = float(m.group(1))
            if minutes.is_integer():
                minutes = int(minutes)
        except Exception:
            minutes = None

    mode = None
    m2 = re.search(r"\bby\s+([a-z]+)", lower)
    if m2:
        mode = m2.group(1)

    out = {"raw": raw}
    if minutes is not None:
        out["minutes"] = minutes
    if mode:
        out["mode"] = mode
    return out


def extract_neighborhood(soup: BeautifulSoup):
    wrap = soup.select_one("#property-neighborhood-wrap")
    if not wrap:
        return None

    data = {}
    for item in wrap.select(".block-content-wrap > div"):
        label_el = item.select_one("label")
        value_el = item.select_one(".single_field_nhood span")

        label = label_el.get_text(" ", strip=True) if label_el else None
        value = value_el.get_text(" ", strip=True) if value_el else None

        if label and value:
            data[label] = parse_travel_time(value)

    return data if data else None


# =====================
# MAIN SCRAPER
# =====================

def scrape_property_detail(
    url: str,
    session: Optional[requests.Session] = None,
    delay_range: Optional[Tuple[float, float]] = None,
) -> Optional[Dict[str, Any]]:
    owns_session = False
    if session is None:
        session = requests.Session()
        owns_session = True

    try:
        if delay_range:
            time.sleep(random.uniform(delay_range[0], delay_range[1]))

        html = fetch_html(session, url, timeout=30, retries=3, backoff=2.0, jitter=0.7)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # TITLE
        title_tag = soup.select_one(".page-title h1")
        title = title_tag.get_text(strip=True) if title_tag else None

        # ADDRESS
        address_tag = soup.select_one("address.item-address")
        address = address_tag.get_text(strip=True) if address_tag else None

        # PRICE (structured)
        price_tag = soup.select_one(".item-price .price")
        price_raw = price_tag.get_text(strip=True) if price_tag else None
        price = parse_price(price_raw)

        # LABELS
        labels = []
        for a in soup.select(".property-labels-wrap a"):
            txt = a.get_text(strip=True)
            if txt:
                labels.append(txt)
        labels = list(dict.fromkeys(labels))

        # FACTS (normalized keys)
        facts: Dict[str, str] = {}
        for li in soup.select("#property-detail-wrap li"):
            key_tag = li.find("strong")
            val_tag = li.find("span")
            if key_tag and val_tag:
                key = norm_key(key_tag.get_text(" ", strip=True))
                value = val_tag.get_text(" ", strip=True)
                facts[key] = value

        # basic facts
        property_id = facts.get("property_id")
        property_status = facts.get("property_status")
        property_type = facts.get("property_type")

        bedrooms = parse_int(facts.get("bedrooms"))
        bathrooms = parse_int(facts.get("bathrooms"))
        years = parse_int(facts.get("years"))

        building_size_text = facts.get("building_size")
        land_size_text = facts.get("land_size")

        year_built = parse_int(facts.get("year_built"))
        area = facts.get("area")

        building_size_value, building_size_unit = extract_measure(building_size_text)
        land_size_value, land_size_unit = extract_measure(land_size_text)

        # NEW: price per are per year (structured)
        ppa_raw = facts.get("price_per_are_per_year")
        price_per_are_per_year = parse_price(ppa_raw) if ppa_raw else None
        if price_per_are_per_year:
            price_per_are_per_year["unit"] = "are"
            price_per_are_per_year["period"] = price_per_are_per_year.get("period") or "year"

        features, feature_groups = extract_features(soup)
        neighborhood = extract_neighborhood(soup)
        images = extract_images(soup)

        return {
            "title": title,
            "url": url,

            "property_id": property_id,
            "property_status": property_status,
            "property_type": property_type,

            "price": price,
            "price_per_are_per_year": price_per_are_per_year,

            "years": years,                 # ✅ int/None
            "bedrooms": bedrooms,           # ✅ int/None
            "bathrooms": bathrooms,         # ✅ int/None

            "building_size": building_size_text,
            "building_size_value": building_size_value,   # ✅ float/None
            "building_size_unit": building_size_unit,

            "land_size": land_size_text,
            "land_size_value": land_size_value,           # ✅ float/None
            "land_size_unit": land_size_unit,

            "year_built": year_built,       # ✅ int/None
            "area": area,
            "address": address,

            "labels": labels,
            "neighborhood": neighborhood,

            "description": extract_description(soup),

            "features": features,
            "feature_groups": feature_groups,

            "images": images,
        }

    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    test_url = "https://propertia.com/property/balangan-land-offering-the-perfect-size-for-development/"
    data = scrape_property_detail(test_url)
    from pprint import pprint
    pprint(data)