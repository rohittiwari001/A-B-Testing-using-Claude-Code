"""Build deck.pptx."""

from pathlib import Path

from abkit.deck import build_standard_deck

RUN = Path(__file__).resolve().parents[1]
print(build_standard_deck(RUN))
