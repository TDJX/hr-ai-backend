from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.models.vacancy import VacancyCreate, VacancyRead, VacancyUpdate
from app.services.vacancy_parser_service import vacancy_parser_service
from app.services.vacancy_service import VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


class VacancyParseResponse(BaseModel):
    """Ответ на запрос парсинга вакансии"""

    message: str
    parsed_data: dict | None = None
    task_id: str | None = None


@router.post("/", response_model=VacancyRead)
async def create_vacancy(
    vacancy: VacancyCreate, vacancy_service: VacancyService = Depends(VacancyService)
):
    return await vacancy_service.create_vacancy(vacancy)


@router.get("/", response_model=list[VacancyRead])
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    title: str | None = Query(None),
    company_name: str | None = Query(None),
    area_name: str | None = Query(None),
    vacancy_service: VacancyService = Depends(VacancyService),
):
    if any([title, company_name, area_name]):
        return await vacancy_service.search_vacancies(
            title=title,
            company_name=company_name,
            area_name=area_name,
            skip=skip,
            limit=limit,
        )

    if active_only:
        return await vacancy_service.get_active_vacancies(skip=skip, limit=limit)

    return await vacancy_service.get_all_vacancies(skip=skip, limit=limit)


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    vacancy = await vacancy_service.get_vacancy(vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy


@router.put("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: int,
    vacancy: VacancyUpdate,
    vacancy_service: VacancyService = Depends(VacancyService),
):
    updated_vacancy = await vacancy_service.update_vacancy(vacancy_id, vacancy)
    if not updated_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return updated_vacancy


@router.delete("/{vacancy_id}")
async def delete_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    success = await vacancy_service.delete_vacancy(vacancy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return {"message": "Vacancy deleted successfully"}


@router.patch("/{vacancy_id}/archive", response_model=VacancyRead)
async def archive_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    archived_vacancy = await vacancy_service.archive_vacancy(vacancy_id)
    if not archived_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return archived_vacancy


@router.post("/parse-file", response_model=VacancyParseResponse)
async def parse_vacancy_from_file(
    file: UploadFile = File(...),
    create_vacancy: bool = Query(False, description="Создать вакансию после парсинга"),
    vacancy_service: VacancyService = Depends(VacancyService),
):
    """
    Парсинг вакансии из загруженного файла (PDF, DOCX, RTF, TXT)

    Args:
        file: Файл вакансии
        create_vacancy: Создать вакансию в БД после парсинга

    Returns:
        VacancyParseResponse: Результат парсинга
    """

    # Проверяем формат файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла не указано")

    file_extension = file.filename.lower().split(".")[-1]
    supported_formats = ["pdf", "docx", "rtf", "txt"]

    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Поддерживаются: {', '.join(supported_formats)}",
        )

    # Проверяем размер файла (максимум 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="Файл слишком большой (максимум 10MB)"
        )

    try:
        # Извлекаем текст из файла
        raw_text = vacancy_parser_service.extract_text_from_file(
            file_content, file.filename
        )

        if not raw_text.strip():
            raise HTTPException(
                status_code=400, detail="Не удалось извлечь текст из файла"
            )

        # Парсим с помощью AI
        parsed_data = await vacancy_parser_service.parse_vacancy_with_ai(raw_text)

        # Если нужно создать вакансию, создаем её
        created_vacancy = None
        if create_vacancy:
            try:
                vacancy_create = VacancyCreate(**parsed_data)
                created_vacancy = await vacancy_service.create_vacancy(vacancy_create)
            except Exception as e:
                # Возвращаем парсинг, но предупреждаем об ошибке создания
                return VacancyParseResponse(
                    message=f"Парсинг выполнен, но ошибка при создании вакансии: {str(e)}",
                    parsed_data=parsed_data,
                )

        response_message = "Парсинг выполнен успешно"
        if created_vacancy:
            response_message += f". Вакансия создана с ID: {created_vacancy.id}"

        return VacancyParseResponse(message=response_message, parsed_data=parsed_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при парсинге вакансии: {str(e)}"
        )


@router.post("/parse-text", response_model=VacancyParseResponse)
async def parse_vacancy_from_text(
    text: str = Query(..., description="Текст вакансии для парсинга"),
    create_vacancy: bool = Query(False, description="Создать вакансию после парсинга"),
    vacancy_service: VacancyService = Depends(VacancyService),
):
    """
    Парсинг вакансии из текста

    Args:
        text: Текст вакансии
        create_vacancy: Создать вакансию в БД после парсинга

    Returns:
        VacancyParseResponse: Результат парсинга
    """

    if not text.strip():
        raise HTTPException(
            status_code=400, detail="Текст вакансии не может быть пустым"
        )

    if len(text) > 50000:  # Ограничение на длину текста
        raise HTTPException(
            status_code=400, detail="Текст слишком длинный (максимум 50000 символов)"
        )

    try:
        # Парсим с помощью AI
        parsed_data = await vacancy_parser_service.parse_vacancy_with_ai(text)

        # Если нужно создать вакансию, создаем её
        created_vacancy = None
        if create_vacancy:
            try:
                vacancy_create = VacancyCreate(**parsed_data)
                created_vacancy = await vacancy_service.create_vacancy(vacancy_create)
            except Exception as e:
                return VacancyParseResponse(
                    message=f"Парсинг выполнен, но ошибка при создании вакансии: {str(e)}",
                    parsed_data=parsed_data,
                )

        response_message = "Парсинг выполнен успешно"
        if created_vacancy:
            response_message += f". Вакансия создана с ID: {created_vacancy.id}"

        return VacancyParseResponse(message=response_message, parsed_data=parsed_data)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при парсинге вакансии: {str(e)}"
        )


@router.get("/parse-formats")
async def get_supported_formats():
    """
    Получить список поддерживаемых форматов файлов для парсинга вакансий

    Returns:
        dict: Информация о поддерживаемых форматах
    """
    return {
        "supported_formats": [
            {"extension": "pdf", "description": "PDF документы", "max_size_mb": 10},
            {
                "extension": "docx",
                "description": "Microsoft Word документы",
                "max_size_mb": 10,
            },
            {"extension": "rtf", "description": "Rich Text Format", "max_size_mb": 10},
            {"extension": "txt", "description": "Текстовые файлы", "max_size_mb": 10},
        ],
        "features": [
            "Автоматическое извлечение текста из файлов",
            "AI-парсинг структурированной информации",
            "Создание вакансии в базе данных",
            "Валидация данных",
        ],
    }


@router.post("/parse-file-async", response_model=dict)
async def parse_vacancy_from_file_async(
    file: UploadFile = File(...),
    create_vacancy: str = Form("false", description="Создать вакансию после парсинга"),
):
    """
    Асинхронный парсинг вакансии из загруженного файла (PDF, DOCX, RTF, TXT)

    Args:
        file: Файл вакансии
        create_vacancy: Создать вакансию в БД после парсинга

    Returns:
        dict: ID задачи для отслеживания статуса
    """
    import base64

    from celery_worker.tasks import parse_vacancy_task

    # Проверяем формат файла
    if not file.filename:
        raise HTTPException(status_code=400, detail="Имя файла не указано")

    file_extension = file.filename.lower().split(".")[-1]
    supported_formats = ["pdf", "docx", "rtf", "txt"]

    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Поддерживаются: {', '.join(supported_formats)}",
        )

    # Проверяем размер файла (максимум 10MB)
    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400, detail="Файл слишком большой (максимум 10MB)"
        )

    try:
        # Кодируем содержимое файла в base64 для передачи в Celery
        file_content_base64 = base64.b64encode(file_content).decode("utf-8")

        # Конвертируем строку в boolean
        create_vacancy_bool = create_vacancy.lower() in ("true", "1", "yes", "on")

        # Запускаем асинхронную задачу
        task = parse_vacancy_task.delay(
            file_content_base64=file_content_base64,
            filename=file.filename,
            create_vacancy=create_vacancy_bool,
        )

        return {
            "message": "Задача парсинга запущена",
            "task_id": task.id,
            "status": "pending",
            "check_status_url": f"/api/v1/vacancies/parse-status/{task.id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при запуске парсинга: {str(e)}"
        )


@router.get("/parse-status/{task_id}")
async def get_parse_status(task_id: str):
    """
    Получить статус асинхронной задачи парсинга вакансии

    Args:
        task_id: ID задачи

    Returns:
        dict: Статус задачи и результат (если завершена)
    """
    from celery_worker.celery_app import celery_app

    try:
        task = celery_app.AsyncResult(task_id)

        if task.state == "PENDING":
            response = {
                "task_id": task_id,
                "state": task.state,
                "status": "Задача ожидает выполнения...",
                "progress": 0,
            }
        elif task.state == "PROGRESS":
            response = {
                "task_id": task_id,
                "state": task.state,
                "status": task.info.get("status", ""),
                "progress": task.info.get("progress", 0),
            }
        elif task.state == "SUCCESS":
            response = {
                "task_id": task_id,
                "state": task.state,
                "status": "completed",
                "progress": 100,
                "result": task.result,
            }
        else:  # FAILURE
            response = {
                "task_id": task_id,
                "state": task.state,
                "status": "failed",
                "progress": 0,
                "error": str(task.info),
            }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении статуса задачи: {str(e)}"
        )
