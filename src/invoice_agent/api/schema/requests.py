from typing import Literal

from pydantic import BaseModel

_AllowedContentType = Literal["image/jpeg", "image/png", "application/pdf"]


class ImageInput(BaseModel):
    content_type = _AllowedContentType
    reconciliation_issues: str | None = None
    needs_review: bool = False
