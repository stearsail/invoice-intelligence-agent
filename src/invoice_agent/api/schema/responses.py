from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    job_id: int
    status: str
