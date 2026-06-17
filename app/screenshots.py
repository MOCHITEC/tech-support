"""スクリーンショットの検証とサニタイズ。

サイズ上限・magic-byte(Pillow による形式判定)・寸法/ピクセル上限(圧縮爆弾対策)を
検査し、PNG に再エンコードしてメタデータを除去した bytes を返す。
"""
import io

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_DIM = 5000  # 縦横の上限(px)
MAX_PIXELS = 25_000_000  # 総ピクセル数の上限
ALLOWED_FORMATS = {"PNG", "JPEG"}


def validate_and_process(raw: bytes) -> bytes:
    """検証して PNG bytes を返す。不正な場合は ValueError。"""
    if len(raw) > MAX_BYTES:
        raise ValueError("画像が大きすぎます")

    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format not in ALLOWED_FORMATS:
                raise ValueError("PNG または JPEG のみ対応します")

            width, height = img.size
            if width > MAX_DIM or height > MAX_DIM or width * height > MAX_PIXELS:
                raise ValueError("画像の寸法が大きすぎます")

            img.load()  # 寸法を確認した後にデコードする
            rgb = img.convert("RGB")
            # 生ピクセルだけを新規画像に移すことでメタデータを完全に除去する。
            clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("画像を読み込めませんでした") from exc

    out = io.BytesIO()
    clean.save(out, format="PNG")
    return out.getvalue()
