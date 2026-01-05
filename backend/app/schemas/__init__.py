# Schemas package - export all schemas
from app.schemas.paper import (
    AuthorSchema,
    PaperBase,
    PaperCreate,
    PaperMetricsResponse,
    PaperImplementationResponse,
    PaperSummaryResponse,
    PaperListItem,
    PaperDetail,
    PaperListResponse,
    PaperSearchRequest,
)
from app.schemas.user import (
    UserRegister,
    UserLogin,
    Token,
    TokenData,
    UserResponse,
    UserPreferencesUpdate,
    UserPreferencesResponse,
    InteractionCreate,
    InteractionResponse,
)

__all__ = [
    # Paper schemas
    "AuthorSchema",
    "PaperBase",
    "PaperCreate",
    "PaperMetricsResponse",
    "PaperImplementationResponse",
    "PaperSummaryResponse",
    "PaperListItem",
    "PaperDetail",
    "PaperListResponse",
    "PaperSearchRequest",
    # User schemas
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenData",
    "UserResponse",
    "UserPreferencesUpdate",
    "UserPreferencesResponse",
    "InteractionCreate",
    "InteractionResponse",
]
