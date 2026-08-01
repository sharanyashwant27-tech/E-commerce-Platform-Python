"""Unit tests for perceptual image search helpers."""

import io
from pathlib import Path

from PIL import Image

from utils.image_search import (
    compute_signature,
    rank_by_image,
    resolve_image_path,
    similarity,
    signature_from_bytes,
)


def _png_bytes(color, size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_identical_images_score_near_one():
    data = _png_bytes((220, 40, 40))
    a = signature_from_bytes(data)
    b = signature_from_bytes(data)
    assert similarity(a, b) >= 0.99


def test_different_images_score_lower():
    red = signature_from_bytes(_png_bytes((220, 30, 30)))
    blue = signature_from_bytes(_png_bytes((30, 40, 220)))
    assert similarity(red, blue) < 0.85


def test_rank_by_image_orders_best_match_first():
    query = signature_from_bytes(_png_bytes((200, 50, 50)))
    near = signature_from_bytes(_png_bytes((190, 60, 55)))
    far = signature_from_bytes(_png_bytes((20, 200, 40)))
    ranked = rank_by_image(query, [(1, near), (2, far)], min_score=0.0, limit=10)
    assert ranked[0][0] == 1
    assert ranked[0][1] >= ranked[1][1]


def test_resolve_static_image_path():
    headphones = Path(__file__).resolve().parents[2] / "static" / "images" / "headphones.jpg"
    if not headphones.is_file():
        return
    path = resolve_image_path("/static/images/headphones.jpg")
    assert path is not None
    assert path.name == "headphones.jpg"


def test_invalid_bytes_raise():
    try:
        signature_from_bytes(b"not-an-image")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_compute_signature_from_pil():
    img = Image.new("RGB", (48, 48), (10, 120, 200))
    sig = compute_signature(img)
    assert isinstance(sig.dhash, int)
    assert len(sig.histogram) == 24
