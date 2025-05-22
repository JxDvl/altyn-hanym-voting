from datetime import datetime, timedelta
from jose import jwt, JWTError
from ..core.config import settings
import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        logger.info("AuthService initialized with algorithm: %s", self.algorithm)

    async def generate_test_token(self, provider: str) -> str:
        """
        Генерирует тестовый JWT токен для указанного провайдера.
        В реальном приложении здесь будет OAuth2 flow.
        """
        try:
            logger.info("Generating test token for provider: %s", provider)
            
            # Создаем payload для токена
            payload = {
                "sub": f"test_user_{provider}",  # subject (user identifier)
                "provider": provider,
                "exp": datetime.utcnow() + timedelta(days=1),  # токен действителен 1 день
                "iat": datetime.utcnow(),  # issued at
            }

            # Генерируем JWT токен
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info("Successfully generated token for provider: %s", provider)
            return token
            
        except Exception as e:
            logger.error("Failed to generate token for provider %s: %s", provider, str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при генерации токена: {str(e)}"
            )

    async def verify_token(self, token: str) -> dict:
        """
        Проверяет JWT токен и возвращает его payload.
        """
        try:
            logger.info("Verifying token")
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            logger.info("Token verified successfully")
            return payload
        except JWTError as e:
            logger.error("Token verification failed: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный токен"
            )
        except Exception as e:
            logger.error("Unexpected error during token verification: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка при проверке токена"
            ) 