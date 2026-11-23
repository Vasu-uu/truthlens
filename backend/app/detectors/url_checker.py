"""Offline lexical URL risk analysis. URLs are never visited or resolved."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.fusion import noisy_or
from app.schemas import Signal

_MULTI_SUFFIX = {
    "co.in", "org.in", "gov.in", "nic.in", "ac.in", "net.in", "res.in",
    "co.uk", "com.au", "co.jp", "com.br", "org.uk",
}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy",
    "shorturl.at", "ow.ly", "buff.ly", "tiny.cc", "rebrand.ly", "t.ly",
    "bit.do", "s.id", "v.gd", "lnkd.in",
}
SUSPICIOUS_TLDS = {
    "xyz", "top", "click", "link", "icu", "buzz", "tk", "ml", "ga", "cf", "gq",
    "work", "support", "rest", "cam", "loan", "zip", "mov", "monster", "cyou",
}
# brand token -> legitimate registrable domains
BRANDS: dict[str, set[str]] = {
    "sbi": {"sbi.co.in", "onlinesbi.sbi", "onlinesbi.com", "sbicard.com", "sbi.bank.in"},
    "hdfc": {"hdfcbank.com", "hdfc.com", "hdfcbank.net", "hdfclife.com"},
    "icici": {"icicibank.com", "icicilombard.com", "iciciprulife.com", "icicidirect.com"},
    "axisbank": {"axisbank.com"},
    "kotak": {"kotak.com"},
    "pnb": {"pnbindia.in", "netpnb.com"},
    "paytm": {"paytm.com", "paytmbank.com"},
    "phonepe": {"phonepe.com"},
    "amazon": {"amazon.in", "amazon.com", "amazon.co.uk"},
    "flipkart": {"flipkart.com"},
    "npci": {"npci.org.in"},
    "irctc": {"irctc.co.in", "irctc.com"},
    "rbi": {"rbi.org.in"},
    "indiapost": {"indiapost.gov.in"},
    "whatsapp": {"whatsapp.com", "whatsapp.net"},
    "google": {"google.com", "google.co.in"},
    "jio": {"jio.com"},
    "airtel": {"airtel.in", "airtel.com"},
    "paypal": {"paypal.com"},
    "netflix": {"netflix.com"},
}
_SWAPS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})
_PHISHY_PATH = re.compile(r"(login|verify|update|kyc|secure|otp|signin|account|refund|claim)", re.I)

_URL_RE = re.compile(
    r"""(?ix)
    (?<![@\w.\-])
    (
      (?:https?://|www\.)[^\s<>"']+
      |
      (?:[a-z0-9\-]+\.)+(?:com|in|net|org|xyz|top|co|io|me|link|click|info|online|site|app|ly|gl|cc|tk|ml|ga|cf|gq|icu|buzz|live|support)\b(?:/[^\s<>"']*)?
    )
    """
)
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def extract_urls(text: str) -> list[tuple[str, int, int]]:
    """Return (url, start, end) for each URL-like token in the text."""
    out: list[tuple[str, int, int]] = []
    for m in _URL_RE.finditer(text):
        raw = m.group(1).rstrip(".,;:!?)]}'\"")
        if not raw:
            continue
        out.append((raw, m.start(1), m.start(1) + len(raw)))
    return out


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def split_host(host: str) -> tuple[str, list[str]]:
    """Return (registrable_domain, subdomain_labels)."""
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in _MULTI_SUFFIX:
        n = 3
    else:
        n = 2
    n = min(n, len(labels))
    return ".".join(labels[-n:]), labels[:-n]


def _sig(sid: str, name: str, value: str | float | bool | None, weight: float, detail: str) -> Signal:
    return Signal(id=sid, name=name, category="url", value=value, direction="suspicious", weight=weight, detail=detail)


def analyze_url(url: str) -> list[Signal]:
    """Return suspicious-URL signals for one URL (lexical checks only)."""
    sigs: list[Signal] = []
    full = url if re.match(r"^[a-z][a-z0-9+.\-]*://", url, re.I) else "http://" + url
    try:
        parts = urlsplit(full)
        host = (parts.hostname or "").lower()
    except ValueError:
        return [_sig("url_malformed", "Malformed link", url[:60], 0.2, "The link is not a valid web address, which is unusual for a genuine message.")]
    if not host:
        return sigs
    shown = host

    if "@" in parts.netloc:
        sigs.append(_sig("url_at_trick", "Link hides its real destination", shown, 0.45,
                         "The link uses an '@' trick, so what comes before it is ignored and the real site is different from what it appears to be."))
    if _IPV4.match(host):
        sigs.append(_sig("url_ip_host", "Link points to a raw IP address", shown, 0.45,
                         "Genuine banks and shops use proper names, not numeric IP addresses."))
        return sigs
    if host in SHORTENERS:
        sigs.append(_sig("url_shortener", "Shortened link", shown, 0.18,
                         "Link shorteners hide where you will land, so scammers use them to mask fake sites."))
    reg, subs = split_host(host)
    tld = reg.rsplit(".", 1)[-1]

    if "xn--" in host:
        sigs.append(_sig("url_punycode", "Punycode (look-alike characters) in domain", shown, 0.45,
                         "The domain uses encoded international characters that can imitate a real brand."))
    elif any(ord(c) > 127 for c in host):
        sigs.append(_sig("url_homoglyph", "Non-standard characters in domain", shown, 0.45,
                         "The domain contains unusual characters that can imitate a real brand."))
    if len(subs) >= 3:
        sigs.append(_sig("url_subdomains", "Too many subdomains", len(subs), 0.2,
                         "Long chains of subdomains are a common trick to make a fake address look official."))
    if tld in SUSPICIOUS_TLDS:
        sigs.append(_sig("url_suspicious_tld", "Suspicious domain ending", "." + tld, 0.2,
                         f"The '.{tld}' ending is cheap and frequently used for throwaway scam sites."))
    if host.count("-") >= 3:
        sigs.append(_sig("url_hyphens", "Many hyphens in domain", host.count("-"), 0.12,
                         "Domains stuffed with hyphens are often made-up addresses imitating real services."))
    if len(url) > 100:
        sigs.append(_sig("url_long", "Very long link", len(url), 0.1,
                         "Very long links can bury the real destination."))
    if parts.scheme == "http":
        sigs.append(_sig("url_no_https", "Link is not encrypted (http)", shown, 0.08,
                         "The link does not use HTTPS, which genuine banking and payment sites always do."))

    # Brand checks
    label_text = ".".join(subs + [reg.rsplit(".", 1)[0]])
    flat = re.sub(r"[\-.]", "", label_text)
    normalized = flat.translate(_SWAPS).replace("rn", "m").replace("vv", "w")
    first_label = reg.split(".")[0]
    brand_flagged = False
    for brand, legit in BRANDS.items():
        if reg in legit:
            brand_flagged = False
            break
        in_raw = brand in flat
        in_norm = brand in normalized
        near = len(first_label) >= 5 and len(brand) >= 5 and 0 < _lev(first_label, brand) <= 1
        if in_norm and not in_raw:
            sigs.append(_sig("url_lookalike", "Look-alike of a known brand", shown, 0.5,
                             f"The domain swaps letters or digits to imitate '{brand}', a classic phishing trick."))
            brand_flagged = True
            break
        if near and not in_raw:
            sigs.append(_sig("url_lookalike", "Look-alike of a known brand", shown, 0.5,
                             f"The domain is one character away from '{brand}', a classic phishing trick."))
            brand_flagged = True
            break
        if in_raw:
            sigs.append(_sig("url_brand_mismatch", "Brand name inside an unrelated domain", shown, 0.45,
                             f"The name '{brand}' appears in the address, but the site is not run by {brand}'s official domain."))
            brand_flagged = True
            break
    if _PHISHY_PATH.search(parts.path + "?" + (parts.query or "")) and (brand_flagged or tld in SUSPICIOUS_TLDS or host in SHORTENERS):
        sigs.append(_sig("url_phishy_path", "Login/verify wording in the link", parts.path[:40] or None, 0.1,
                         "Words like 'login', 'verify' or 'kyc' in a link to an unofficial site are typical of phishing pages."))
    return sigs


def url_risk(url: str) -> float:
    """Combined 0-1 risk for one URL."""
    return noisy_or([s.weight for s in analyze_url(url)])


def analyze_urls(text: str) -> tuple[list[tuple[str, int, int]], list[Signal]]:
    """Extract URLs from text and return (urls_with_spans, deduplicated signals)."""
    urls = extract_urls(text)
    seen: dict[str, Signal] = {}
    for u, _, _ in urls:
        for s in analyze_url(u):
            seen.setdefault(s.id, s)
    return urls, list(seen.values())
