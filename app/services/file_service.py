from fastapi import UploadFile
from typing import Optional
from app.core.s3 import s3_service


class FileService:
    def __init__(self):
        self.s3_service = s3_service

    async def upload_resume_file(self, file: UploadFile) -> Optional[str]:
        if not file.filename:
            return None
            
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"
        
        return await self.s3_service.upload_file(
            file_content=content,
            file_name=file.filename,
            content_type=content_type
        )

    async def upload_interview_report(self, file: UploadFile) -> Optional[str]:
        if not file.filename:
            return None
            
        content = await file.read()
        content_type = file.content_type or "application/octet-stream"
        
        return await self.s3_service.upload_file(
            file_content=content,
            file_name=f"interview_report_{file.filename}",
            content_type=content_type
        )

    async def delete_file(self, file_url: str) -> bool:
        return await self.s3_service.delete_file(file_url)