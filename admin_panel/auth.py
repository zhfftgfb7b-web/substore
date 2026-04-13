"""
HTTP Basic Auth для админ-панели
"""
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import settings

security = HTTPBasic()


def verify_credentials(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)]
) -> str:
    """
    Проверка логина и пароля для доступа к админ-панели

    Returns:
        str: username при успешной авторизации

    Raises:
        HTTPException: При неверных credentials
    """
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        settings.ADMIN_PANEL_LOGIN.encode("utf8"),
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        settings.ADMIN_PANEL_PASSWORD.encode("utf8"),
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
