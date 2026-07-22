import base64
import io
from pathlib import Path
from PIL import Image
from invoice_agent.agent.images import load_image_b64


def test_small_image_is_returned_unmodified(tmp_path: Path):
    path = tmp_path / "small.png"
    Image.new("RGB", (500, 500), color="red").save(path, format="PNG")

    result = load_image_b64(str(path), max_pixels=1_000_000)

    assert base64.b64decode(result) == path.read_bytes()


def test_image_exactly_at_limit_is_not_resized(tmp_path: Path):
    path = tmp_path / "exact.png"
    Image.new("RGB", (1000, 1000), color="green").save(path, format="PNG")

    result = load_image_b64(str(path), max_pixels=1_000_000)

    assert base64.b64decode(result) == path.read_bytes()


def test_large_image_is_resized_to_fit(tmp_path: Path):
    path = tmp_path / "large.png"
    Image.new("RGB", (2000, 1000), color="blue").save(path, format="PNG")

    result = load_image_b64(str(path), max_pixels=1_000_000)

    decoded = base64.b64decode(result)
    resized = Image.open(io.BytesIO(decoded))
    width, height = resized.size

    assert width * height <= 1_000_000
    assert abs((width / height) - 2.0) < 0.01
