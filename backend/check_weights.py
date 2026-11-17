"""Run with: uv run python check_weights.py"""

from types import SimpleNamespace

from app.main import recalc


def make(shares, pinned=()):
    offers = [
        SimpleNamespace(offer_id=index + 1, share=share, pinned=index in pinned, removed=False)
        for index, share in enumerate(shares)
    ]
    return SimpleNamespace(offers=offers)


def shares(stream):
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

print("weights OK")
