"""Perceptual image hashing for catalog visual search (Pillow-only)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

from config.settings import settings

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
HASH_SIZE = 8
HIST_BINS = 8
# Combined score threshold (0–1). Below this, a product is not returned.
DEFAULT_MIN_SCORE = 0.42
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ImageSignature:
    """Compact visual fingerprint for similarity ranking."""

    dhash: int
    ahash: int
    histogram: Tuple[int, ...]


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _hash_similarity(a: int, b: int, bits: int = HASH_SIZE * HASH_SIZE) -> float:
    return 1.0 - (_hamming(a, b) / bits)


def _histogram_similarity(a: Sequence[int], b: Sequence[int]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    # Cosine similarity on color histograms
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))


def open_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid or unsupported image file") from exc


def compute_signature(img: Image.Image) -> ImageSignature:
    """Build difference-hash, average-hash, and coarse RGB histogram."""
    rgb = img.convert("RGB")

    # Difference hash
    gray = ImageOps.autocontrast(rgb.convert("L"))
    d_img = gray.resize((HASH_SIZE + 1, HASH_SIZE), Image.Resampling.LANCZOS)
    d_pixels = list(d_img.getdata())
    dhash = 0
    bit = 0
    for row in range(HASH_SIZE):
        row_start = row * (HASH_SIZE + 1)
        for col in range(HASH_SIZE):
            left = d_pixels[row_start + col]
            right = d_pixels[row_start + col + 1]
            if left > right:
                dhash |= 1 << bit
            bit += 1

    # Average hash
    a_img = gray.resize((HASH_SIZE, HASH_SIZE), Image.Resampling.LANCZOS)
    a_pixels = list(a_img.getdata())
    avg = sum(a_pixels) / len(a_pixels)
    ahash = 0
    for i, px in enumerate(a_pixels):
        if px >= avg:
            ahash |= 1 << i

    # Coarse color histogram (8 bins × 3 channels)
    small = rgb.resize((64, 64), Image.Resampling.LANCZOS)
    hist = small.histogram()
    # Pillow RGB histogram is 256×3; downsample each channel to HIST_BINS
    reduced: List[int] = []
    bucket = 256 // HIST_BINS
    for channel in range(3):
        base = channel * 256
        for b in range(HIST_BINS):
            start = base + b * bucket
            end = base + (b + 1) * bucket if b < HIST_BINS - 1 else base + 256
            reduced.append(sum(hist[start:end]))

    return ImageSignature(dhash=dhash, ahash=ahash, histogram=tuple(reduced))


def signature_from_bytes(data: bytes) -> ImageSignature:
    return compute_signature(open_image(data))


def similarity(a: ImageSignature, b: ImageSignature) -> float:
    """Weighted blend of perceptual hashes + color histogram (0–1)."""
    d = _hash_similarity(a.dhash, b.dhash)
    ah = _hash_similarity(a.ahash, b.ahash)
    h = _histogram_similarity(a.histogram, b.histogram)
    return 0.45 * d + 0.25 * ah + 0.30 * h


def resolve_image_path(url: str) -> Optional[Path]:
    """Map a product image URL to a local filesystem path when possible."""
    if not url:
        return None
    url = url.strip()
    if url.startswith(("http://", "https://", "//")):
        return None

    path_part = url.split("?", 1)[0]
    if path_part.startswith("/static/"):
        candidate = _PROJECT_ROOT / path_part.lstrip("/")
    elif path_part.startswith("static/"):
        candidate = _PROJECT_ROOT / path_part
    elif path_part.startswith("/uploads/"):
        rel = path_part[len("/uploads/") :]
        candidate = Path(settings.upload_dir) / rel
        if not candidate.is_absolute():
            candidate = _PROJECT_ROOT / candidate
    elif path_part.startswith("uploads/"):
        candidate = Path(settings.upload_dir) / path_part[len("uploads/") :]
        if not candidate.is_absolute():
            candidate = _PROJECT_ROOT / candidate
    else:
        candidate = _PROJECT_ROOT / path_part.lstrip("/")

    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    if candidate.is_file():
        return candidate
    return None


def signature_from_path(path: Path) -> Optional[ImageSignature]:
    try:
        data = path.read_bytes()
        return signature_from_bytes(data)
    except (OSError, ValueError):
        return None


def rank_by_image(
    query: ImageSignature,
    candidates: Iterable[Tuple[int, ImageSignature]],
    *,
    min_score: float = DEFAULT_MIN_SCORE,
    limit: int = 24,
) -> List[Tuple[int, float]]:
    """Return (product_id, score) pairs sorted by descending similarity."""
    scored: dict[int, float] = {}
    for product_id, sig in candidates:
        score = similarity(query, sig)
        if score < min_score:
            continue
        prev = scored.get(product_id)
        if prev is None or score > prev:
            scored[product_id] = score
    ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)
    return ranked[:limit]
