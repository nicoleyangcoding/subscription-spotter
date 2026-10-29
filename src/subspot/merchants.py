"""Turn messy statement descriptions into a stable merchant key.

"SQ *CORNER BAKERY #0412 SEATTLE WA" and "SQ *CORNER BAKERY #0398" both become "CORNER BAKERY".
"""

from __future__ import annotations

import re

# Prefixes added by banks and payment processors, not part of the merchant name.
_PREFIXES = re.compile(
    r"^(?:(?:POS|ACH|DEBIT|CREDIT|CARD|PURCHASE|RECURRING|PAYMENT|AUTOPAY|ONLINE|WEB|"
    r"CHECKCARD|VISA|MC|DD|DIRECT DEBIT|PREAUTHORIZED|PRE-AUTH|BILL PAY|TO|FROM)\b[\s:/-]*)+"
)
_PROCESSOR = re.compile(r"^(?:SQ|SP|TST|PP|PAYPAL|GOOGLE|APPLE\.COM/BILL|AMZN MKTP|IC|DNH|FS)\s*\*\s*")
_US_STATES = set(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
    "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
_NOISE = re.compile(
    r"(?:#\s*\w+)|(?:\b\d{3,}\b)|(?:\b[A-Z]*\d[A-Z\d]*\b)|(?:\bX{2,}\d*\b)|(?:\*+)"
    r"|(?:\b(?:WWW\.)?[A-Z0-9-]+\.(?:COM|NET|ORG|IO|CO|TV|APP)\b)"
)
_DOMAIN = re.compile(r"\b(?:WWW\.)?([A-Z0-9-]+)\.(?:COM|NET|ORG|IO|CO|TV|APP)\b")
_STOPWORDS = {
    "INC",
    "LLC",
    "LTD",
    "CORP",
    "THE",
    "USA",
    "US",
    "BILL",
    "SUBSCRIPTION",
    "MEMBERSHIP",
    "ANNUAL",
    "MONTHLY",
    "YEARLY",
    "RENEWAL",
    "PLAN",
}


def merchant_key(description: str) -> str:
    text = description.upper().strip()
    text = _PROCESSOR.sub("", text)
    text = _PREFIXES.sub("", text)
    domain = _DOMAIN.search(text)
    text = _NOISE.sub(" ", text)
    if domain and not text.strip():
        text = domain.group(1)
    elif domain:
        text = f"{domain.group(1)} {text}"
    text = re.sub(r"[^A-Z& ]", " ", text)
    words = [w for w in text.split() if w not in _STOPWORDS and (len(w) > 1 or w == "&")]
    if len(words) >= 2 and words[-1] in _US_STATES:
        words.pop()  # trailing state code ...
        if len(words) >= 3:
            words.pop()  # ... and usually the city before it
    while words and words[-1] == "&":
        words.pop()
    if len(words) > 3:
        words = words[:4] if words[1] == "&" or words[2] == "&" else words[:3]
    return " ".join(words) or description.upper().strip()[:24]


def display_name(key: str) -> str:
    return " ".join(w if w == "&" else w.capitalize() for w in key.split())
