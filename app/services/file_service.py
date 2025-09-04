import os
import tempfile

from fastapi import UploadFile

from app.core.s3 import s3_service


class FileService:
    def __init__(self):
        self.s3_service = s3_service

    async def upload_resume_file(self, file: UploadFile) -> tuple[str, str] | None:
        """
        Загружает резюме в S3 и сохраняет локальную копию для парсинга

        Returns:
            tuple[str, str]: (s3_url, local_file_path) или None при ошибке
        """
        if not file.filename:
            return None

        content = await file.read()
        content_type = file.content_type or "application/octet-stream"

        # Загружаем в S3
        s3_url = await self.s3_service.upload_file(
            file_content=content, file_name=file.filename, content_type=content_type
        )

        if not s3_url:
            return None

        # Сохраняем локальную копию для парсинга
        try:
            # Создаем временный файл с сохранением расширения
            temp_dir = tempfile.gettempdir()
            file_extension = os.path.splitext(file.filename)[1]
            if not file_extension:
                # Пытаемся определить расширение по MIME типу
                if content_type == "application/pdf":
                    file_extension = ".pdf"
                elif content_type in [
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                ]:
                    file_extension = ".docx"
                elif content_type in ["application/msword"]:
                    file_extension = ".doc"
                elif content_type == "text/plain":
                    file_extension = ".txt"
                else:
                    file_extension = ".pdf"  # fallback

            temp_filename = f"resume_{hash(s3_url)}_{file.filename}"
            local_file_path = os.path.join(temp_dir, temp_filename)

            # Сохраняем содержимое файла
            with open(local_file_path, "wb") as temp_file:
                temp_file.write(content)

            return (s3_url, local_file_path)

        except Exception as e:
            print(f"Failed to save local copy: {str(e)}")
            # Если не удалось сохранить локально, возвращаем только S3 URL
            return (s3_url, s3_url)

    async def upload_interview_report(self, file: UploadFile) -> str | None:
        if not file.filename:
            return None

        content = await file.read()
        content_type = file.content_type or "application/octet-stream"

        return await self.s3_service.upload_file(
            file_content=content,
            file_name=f"interview_report_{file.filename}",
            content_type=content_type,
        )

    async def delete_file(self, file_url: str) -> bool:
        return await self.s3_service.delete_file(file_url)
