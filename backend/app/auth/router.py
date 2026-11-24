import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.service import authenticate, current_user, end_session, register_user, start_session
from app.db.session import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    created_at: datetime


@router.post("/register", response_model=UserOut, status_code=201, summary="Create an account")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)) -> User:
    user = register_user(db, body.email, body.password)
    db.commit()
    start_session(response, user)
    return user


@router.post("/login", response_model=UserOut, summary="Log in")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)) -> User:
    user = authenticate(db, body.email, body.password)
    start_session(response, user)
    return user


@router.post("/logout", status_code=204, summary="Log out")
def logout(response: Response) -> Response:
    end_session(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut, summary="The logged-in user")
def me(user: User = Depends(current_user)) -> User:
    return user
