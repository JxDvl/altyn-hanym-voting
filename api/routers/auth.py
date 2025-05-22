from fastapi import APIRouter, HTTPException, status, Request
from ..models.schemas import TokenResponse
from ..services.auth_service import AuthService
import logging
from typing import Dict

router = APIRouter()
logger = logging.getLogger(__name__)

auth_service = AuthService()

# Словарь с описаниями провайдеров
PROVIDER_DESCRIPTIONS: Dict[str, str] = {
    "google": "Google",
    "apple": "Apple ID",
    "facebook": "Facebook",
    "instagram": "Instagram"
}

@router.get("/test")
async def test_endpoint():
    """Тестовый эндпоинт для проверки работы роутера."""
    return {"message": "Auth router is working!"}

@router.post("/{provider}", response_model=TokenResponse)
async def social_auth(provider: str, request: Request):
    """
    Обработка авторизации через социальные сети.
    В реальном приложении здесь будет OAuth2 flow.
    """
    client_ip = request.client.host
    logger.info("Auth request from IP %s for provider %s", client_ip, provider)

    if provider not in PROVIDER_DESCRIPTIONS:
        logger.warning("Invalid provider requested: %s from IP %s", provider, client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый провайдер авторизации. Доступные провайдеры: {', '.join(PROVIDER_DESCRIPTIONS.keys())}"
        )
    
    try:
        token = await auth_service.generate_test_token(provider)
        logger.info("Successfully generated token for provider %s from IP %s", provider, client_ip)
        return TokenResponse(token=token)
    except HTTPException as e:
        # Пробрасываем HTTP исключения дальше
        raise e
    except Exception as e:
        logger.error("Unexpected error during auth for provider %s from IP %s: %s", 
                    provider, client_ip, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера при авторизации"
        ) 