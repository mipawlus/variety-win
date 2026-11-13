"""Quotes shown on the wallpaper: a small built-in set, or the user's own text file."""

import logging
import random
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

AUTHOR_SEPARATORS = (" -- ", " — ", " – ")


@dataclass(frozen=True)
class Quote:
    text: str
    author: str = ""


BUILTIN_QUOTES = [
    Quote("The unexamined life is not worth living.", "Socrates"),
    Quote("Know thyself.", "Inscription at Delphi"),
    Quote("Waste no more time arguing what a good man should be. Be one.", "Marcus Aurelius"),
    Quote(
        "Dwell on the beauty of life. Watch the stars, and see yourself running with them.",
        "Marcus Aurelius",
    ),
    Quote(
        "It is not that we have a short time to live, but that we waste a lot of it.", "Seneca"
    ),
    Quote("The journey of a thousand miles begins with a single step.", "Laozi"),
    Quote("Fortune favours the bold.", "Virgil"),
    Quote("The mind is not a vessel to be filled but a fire to be kindled.", "Plutarch"),
    Quote("I think, therefore I am.", "René Descartes"),
    Quote("Knowledge is power.", "Francis Bacon"),
    Quote("The heart has its reasons which reason knows nothing of.", "Blaise Pascal"),
    Quote(
        "If I have seen further, it is by standing on the shoulders of giants.", "Isaac Newton"
    ),
    Quote("No man is an island, entire of itself.", "John Donne"),
    Quote("To be, or not to be, that is the question.", "William Shakespeare"),
    Quote("Well done is better than well said.", "Benjamin Franklin"),
    Quote("Beauty is truth, truth beauty.", "John Keats"),
    Quote("The mass of men lead lives of quiet desperation.", "Henry David Thoreau"),
    Quote("Hope is the thing with feathers that perches in the soul.", "Emily Dickinson"),
    Quote("I am large, I contain multitudes.", "Walt Whitman"),
    Quote("All that we see or seem is but a dream within a dream.", "Edgar Allan Poe"),
    Quote("He who has a why to live can bear almost any how.", "Friedrich Nietzsche"),
    Quote("Whereof one cannot speak, thereof one must be silent.", "Ludwig Wittgenstein"),
]


def parse_line(line: str) -> Quote | None:
    """One quote per line, optionally followed by ` -- Author`. `#` starts a comment line."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    for separator in AUTHOR_SEPARATORS:
        text, found, author = line.rpartition(separator)
        if found and text.strip() and author.strip():
            return Quote(text.strip().strip('"„”“'), author.strip())
    return Quote(line.strip('"„”“'))


def load(file: str) -> list[Quote]:
    """Quotes from the user's file, or the built-in set if it is unset, missing or empty."""
    if file:
        try:
            lines = Path(file).read_text(encoding="utf-8-sig").splitlines()
            quotes = [quote for quote in map(parse_line, lines) if quote is not None]
            if quotes:
                return quotes
            logger.warning("No quotes found in %s, using the built-in ones", file)
        except (OSError, UnicodeDecodeError):
            logger.exception("Could not read quotes file %s, using the built-in ones", file)
    return BUILTIN_QUOTES


def pick(quotes: list[Quote], previous: Quote | None = None) -> Quote:
    choices = [quote for quote in quotes if quote != previous] or quotes
    return random.choice(choices)
