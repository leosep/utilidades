"""Recurring charge detection."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import timedelta
from statistics import median

from .models import Charge, Subscription

# (name, typical minimum days, maximum, minimum charges, factor for monthly cost)
_FREQUENCIES = (
    ("weekly", 6, 8, 3, 52 / 12),
    ("monthly", 26, 35, 3, 1.0),
    ("quarterly", 85, 97, 2, 1 / 3),
    ("semiannual", 175, 190, 2, 1 / 6),
    ("yearly", 350, 380, 2, 1 / 12),
)

_NOISE = {"pos", "compra", "pago", "debito", "tarjeta", "www", "com", "http", "https", "ref",
          "purchase", "payment", "debit", "card", "charge", "online"}

# Known management pages. Check the link: services change their URLs.
CANCEL_URLS = {
    "netflix": "https://www.netflix.com/cancelplan",
    "spotify": "https://www.spotify.com/account/subscription/",
    "youtube": "https://www.youtube.com/paid_memberships",
    "amazon": "https://www.amazon.com/mc",
}

AMOUNT_TOLERANCE = 0.15
# With only 2 charges the evidence is weak: require the amount to be almost identical.
TWO_CHARGES_TOLERANCE = 0.02


def normalize_merchant(description: str) -> str:
    """First meaningful word of the merchant, without numbers or noise."""
    text = unicodedata.normalize("NFKD", description).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    words = [w for w in text.split() if w not in _NOISE and len(w) > 1]
    return words[0] if words else "unknown"


def _cluster_by_amount(charges: list[Charge]) -> list[list[Charge]]:
    clusters: list[list[Charge]] = []
    for charge in sorted(charges, key=lambda c: c.amount):
        for cluster in clusters:
            base = cluster[0].amount
            if abs(charge.amount - base) <= base * AMOUNT_TOLERANCE:
                cluster.append(charge)
                break
        else:
            clusters.append([charge])
    return clusters


def _classify(days: list[int]) -> tuple[str, float, int] | None:
    """Return (frequency, factor, typical interval) if the gaps are regular."""
    gaps = [b - a for a, b in zip(days, days[1:])]
    if not gaps:
        return None
    typical = median(gaps)
    for name, low, high, minimum, factor in _FREQUENCIES:
        if low <= typical <= high and len(days) >= minimum:
            tolerance = min(max(4, typical * 0.15), 7)  # real charges land within a few days of the expected date
            if all(abs(g - typical) <= tolerance for g in gaps):
                return name, factor, round(typical)
    return None


def _subscription(merchant: str, cluster: list[Charge]) -> Subscription | None:
    cluster = sorted(cluster, key=lambda c: c.day)
    if len(cluster) == 2 and abs(cluster[0].amount - cluster[1].amount) > cluster[0].amount * TWO_CHARGES_TOLERANCE:
        return None
    result = _classify([c.day.toordinal() for c in cluster])
    if result is None:
        return None
    frequency, factor, interval = result
    # Use the most recent charges: after a price increase, the old price is not "typical" any more.
    amount = round(median(c.amount for c in cluster[-3:]), 2)
    last = cluster[-1].day
    return Subscription(
        merchant=merchant,
        frequency=frequency,
        typical_amount=amount,
        monthly_cost=round(amount * factor, 2),
        charges=len(cluster),
        last_charge=last,
        next_charge=last + timedelta(days=interval),
        cancel_url=CANCEL_URLS.get(merchant),
    )


def _merge_price_changes(merchant: str, clusters: list[list[Charge]]) -> list[Subscription]:
    """Join clusters that are the same subscription before and after a price change.

    A price jump above the tolerance splits the charges into two amount clusters. If one
    cluster starts right after the other ends, it is the same service at a new price; a
    second concurrent plan would interleave in time instead.
    """
    merged: list[tuple[list[Charge], Subscription]] = []
    clusters = [sorted(cluster, key=lambda c: c.day) for cluster in clusters]
    for cluster in sorted(clusters, key=lambda c: c[0].day):
        sub = _subscription(merchant, cluster)
        if sub is None:
            continue
        if merged:
            previous_cluster, previous_sub = merged[-1]
            gap = (cluster[0].day - previous_cluster[-1].day).days
            interval = (previous_sub.next_charge - previous_sub.last_charge).days
            if 0 < gap <= interval * 1.6 and sub.frequency == previous_sub.frequency:
                combined = sorted(previous_cluster + cluster, key=lambda c: c.day)
                rebuilt = _subscription(merchant, combined)
                if rebuilt is not None:
                    merged[-1] = (combined, rebuilt)
                    continue
        merged.append((cluster, sub))
    return [sub for _, sub in merged]


def detect_subscriptions(charges: list[Charge]) -> list[Subscription]:
    by_merchant: dict[str, list[Charge]] = defaultdict(list)
    for charge in charges:
        by_merchant[normalize_merchant(charge.description)].append(charge)

    found: list[Subscription] = []
    for merchant, group in by_merchant.items():
        found.extend(_merge_price_changes(merchant, _cluster_by_amount(group)))
    return sorted(found, key=lambda s: s.monthly_cost, reverse=True)
