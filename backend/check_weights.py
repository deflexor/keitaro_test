"""Run with: uv run python check_weights.py"""

from collections.abc import Collection
from types import SimpleNamespace
from typing import cast

from app.main import recalc, refresh_dirty
from app.models import Stream


def make(
    shares: list[int],
    pinned: Collection[int] = (),
    snapshot: list[dict[str, int]] | None = None,
) -> Stream:
    offers = [
        SimpleNamespace(offer_id=index + 1, share=share, pinned=index in pinned, removed=False)
        for index, share in enumerate(shares)
    ]
    return cast(Stream, SimpleNamespace(offers=offers, snapshot=snapshot or []))


def shares(stream: Stream) -> list[int]:
    return [offer.share for offer in stream.offers]


# Even split with the remainder going to the first offers.
stream = make([0, 0, 0])
recalc(stream)
assert shares(stream) == [34, 33, 33], shares(stream)

stream = make([0, 0, 0, 0])
recalc(stream)
assert shares(stream) == [25, 25, 25, 25], shares(stream)

# Pinned weight survives; the other two split 75.
stream = make([25, 25, 25, 25], pinned={0})
stream.offers[1].removed = True
recalc(stream)
assert shares(stream) == [25, 0, 38, 37], shares(stream)

# Removed offers always end up at zero.
stream = make([50, 50])
stream.offers[1].removed = True
recalc(stream)
assert shares(stream) == [100, 0], shares(stream)

# Fully pinned set leaves nothing for the rest.
stream = make([40, 60, 0], pinned={0, 1})
recalc(stream)
assert shares(stream) == [40, 60, 0], shares(stream)

# Dirty follows the snapshot: remove + bring back is not a change.
published = [{"offer_id": 1, "share": 50}, {"offer_id": 2, "share": 50}]
stream = make([50, 50], snapshot=published)
stream.offers[0].removed = True
recalc(stream)
refresh_dirty(stream)
assert stream.dirty

stream.offers[0].removed = False
recalc(stream)
refresh_dirty(stream)
assert not stream.dirty

# A draft offer that is removed again is not a change either.
stream.offers.append(SimpleNamespace(offer_id=3, share=0, pinned=False, removed=False))
recalc(stream)
refresh_dirty(stream)
assert stream.dirty

stream.offers.pop()
recalc(stream)
refresh_dirty(stream)
assert not stream.dirty

print("weights OK")
