import io

import pytest
from PIL import Image

from app import screenshots


def _png_bytes(w=10, h=10, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 180, 240)).save(buf, format=fmt)
    return buf.getvalue()


def test_accepts_valid_png_and_returns_png():
    out = screenshots.validate_and_process(_png_bytes())
    # 返り値は PNG として開ける
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG"


def test_strips_metadata():
    # exif 付き JPEG を入れても、出力にメタデータが残らない
    raw = _png_bytes(fmt="JPEG")
    out = screenshots.validate_and_process(raw)
    img = Image.open(io.BytesIO(out))
    assert not img.info.get("exif")


def test_rejects_non_image():
    with pytest.raises(ValueError):
        screenshots.validate_and_process(b"this is not an image")


def test_rejects_oversized(monkeypatch):
    monkeypatch.setattr(screenshots, "MAX_BYTES", 10)
    with pytest.raises(ValueError):
        screenshots.validate_and_process(_png_bytes())


def test_rejects_huge_dimensions(monkeypatch):
    monkeypatch.setattr(screenshots, "MAX_DIM", 5)
    with pytest.raises(ValueError):
        screenshots.validate_and_process(_png_bytes(w=50, h=50))
