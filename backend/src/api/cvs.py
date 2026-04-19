import re
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_verified_user_id
from core.database import get_db
from models.cv import CV
from schemas.cv import (
    ConfirmUploadRequest,
    CVResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from services.s3 import delete_object_best_effort, generate_upload_url

router = APIRouter()


def _sanitize_filename(filename: str) -> str:
    return re.sub(r'[^\w\-.]', '_', filename)


@router.post(
    '/upload-url', response_model=UploadUrlResponse, status_code=status.HTTP_200_OK
)
async def upload_url(
    body: UploadUrlRequest, user_id: UUID = Depends(get_verified_user_id)
) -> UploadUrlResponse:
    extension = body.filename.rsplit('.', 1)[-1].lower()
    if extension != 'pdf':
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail='Invalid file extension - Upload PDF'
        )
    if body.file_size > (5 * 1024 * 1024):  # max 5MB
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail='File size too large - Max 5MB'
        )

    url, s3_key = generate_upload_url(user_id, body.filename)
    return UploadUrlResponse(upload_url=url, s3_key=s3_key)


@router.post('/confirm', response_model=CVResponse, status_code=status.HTTP_200_OK)
async def confirm(
    body: ConfirmUploadRequest,
    user_id: UUID = Depends(get_verified_user_id),
    db: AsyncSession = Depends(get_db),
) -> CVResponse:
    # Deactivate any previos active CV
    result = await db.execute(select(CV).where(CV.user_id == user_id))
    all_cvs = result.scalars().all()

    if len(all_cvs) >= 3:
        raise HTTPException(status.HTTP_409_CONFLICT, detail='Max 3 CVs allowed')
    elif all_cvs:
        for cv in all_cvs:
            cv.is_active = False

    # Create new CV Record
    cv_record = CV(
        user_id=user_id,
        s3_key=body.s3_key,
        filename=_sanitize_filename(body.filename),
        file_size=body.file_size,
    )

    # Add new record
    db.add(cv_record)
    await db.flush()
    await db.refresh(cv_record)  # re-reads the object from DB, including updated_at

    return cv_record


@router.get('/cvs', response_model=list[CVResponse], status_code=status.HTTP_200_OK)
async def get_cvs(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[CVResponse]:
    query = select(CV).where(CV.user_id == user_id).order_by(CV.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.put(
    '/{cv_id}/activate', response_model=CVResponse, status_code=status.HTTP_200_OK
)
async def activate_cv(
    cv_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(CV).where(CV.id == cv_id, CV.user_id == user_id))
    target_cv = result.scalar_one_or_none()

    if not target_cv:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='CV not found')

    result = await db.execute(
        select(CV).where(CV.user_id == user_id, CV.is_active == True)
    )
    for cv in result.scalars().all():
        cv.is_active = False

    target_cv.is_active = True

    await db.flush()
    await db.refresh(target_cv)  # re-reads the object from DB, including updated_at
    return target_cv


@router.delete('/{cv_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_cv(
    cv_id: UUID,
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Same pattern as /auth/delete-account: delete the DB row inside the
    # transaction, then schedule the S3 cleanup as a best-effort background
    # task. Guarantees the user's "CV deleted" expectation is durable even
    # if S3 is flaky; orphan S3 files are acceptable tech debt for a future
    # janitor sweep.
    result = await db.execute(select(CV).where(CV.id == cv_id, CV.user_id == user_id))
    deleted_cv = result.scalar_one_or_none()

    if not deleted_cv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='CV not found')

    # Capture the s3_key BEFORE db.delete — afterwards the ORM object is
    # expired and attribute access would re-query (or fail).
    s3_key = deleted_cv.s3_key
    await db.delete(deleted_cv)

    background_tasks.add_task(delete_object_best_effort, s3_key)
