from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.schemas.question_bank import (
    BankQuestionCreate,
    BankSurveyGenerate,
    BankQuestionPublic,
    BankQuestionUpdate,
    BankTitleCreate,
    BankTitlePublic,
    BankTitleUpdate,
)
from app.schemas.questions import QuestionPublic
from app.security.dependencies import get_admin_user
from app.services.question_bank import (
    copy_bank_question_to_survey,
    generate_survey_questions_from_bank,
    create_bank_question,
    create_title,
    delete_bank_question,
    list_bank_questions,
    list_titles,
    update_bank_question,
    update_title,
)

router = APIRouter(
    prefix="/api/admin/question-bank",
    tags=["question-bank"],
)


@router.get("/titles", response_model=list[BankTitlePublic])
def get_titles(
    active_only: bool = Query(default=False),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return list_titles(db, active_only)


@router.post(
    "/titles",
    response_model=BankTitlePublic,
    status_code=status.HTTP_201_CREATED,
)
def add_title(
    data: BankTitleCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return create_title(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/titles/{title_id}", response_model=BankTitlePublic)
def edit_title(
    title_id: UUID,
    data: BankTitleUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return update_title(db, title_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/titles/{title_id}/questions",
    response_model=list[BankQuestionPublic],
)
def get_bank_questions(
    title_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return list_bank_questions(db, title_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/titles/{title_id}/questions",
    response_model=BankQuestionPublic,
    status_code=status.HTTP_201_CREATED,
)
def add_bank_question(
    title_id: UUID,
    data: BankQuestionCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return create_bank_question(db, title_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch(
    "/questions/{question_id}",
    response_model=BankQuestionPublic,
)
def edit_bank_question(
    question_id: UUID,
    data: BankQuestionUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return update_bank_question(db, question_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete(
    "/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_bank_question(
    question_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        delete_bank_question(db, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/surveys/{survey_id}/copy/{bank_question_id}",
    response_model=QuestionPublic,
    status_code=status.HTTP_201_CREATED,
)
def copy_question_to_survey(
    survey_id: UUID,
    bank_question_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return copy_bank_question_to_survey(
            db, survey_id, bank_question_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



@router.post("/surveys/{survey_id}/generate")
def generate_survey_questions(
    survey_id: UUID,
    data: BankSurveyGenerate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return generate_survey_questions_from_bank(
            db=db,
            survey_id=survey_id,
            title_ids=data.title_ids,
            question_count=data.question_count,
            shuffle=data.shuffle,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
