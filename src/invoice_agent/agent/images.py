import io
from PIL import Image
import base64


def load_image_b64(path, resize=True, max_pixels=1_000_000) -> tuple[str, str]:
    img = Image.open(path)
    if resize:
        w, h = img.size
        if w * h > max_pixels:
            scale = (max_pixels / (w * h)) ** 0.5
            img = img.resize((int(w * scale), int(h * scale)))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode(), "image/png"

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return data, Image.MIME.get(img.format, "image/png")
