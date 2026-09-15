"""AI toolbox client: completion + model catalogue, typed errors, DRF error mapping, availability status."""

from .client import ToolboxClient
from .errors import (
    ToolboxAuthError,
    ToolboxBudgetExceededError,
    ToolboxConnectionError,
    ToolboxError,
    ToolboxModelNotAllowedError,
    ToolboxNotConfiguredError,
    ToolboxNotFoundError,
    ToolboxRateLimitError,
    ToolboxServerError,
    ToolboxTimeoutError,
    ToolboxValidationError,
)
from .schemas import CompletionRequest, CompletionResponse, Message, ModelInfo, Usage
from .status import ToolboxStatus, status
from .views import handle_toolbox_error

__all__ = [
    "ToolboxClient",
    "CompletionRequest",
    "CompletionResponse",
    "Message",
    "ModelInfo",
    "Usage",
    "status",
    "ToolboxStatus",
    "handle_toolbox_error",
    "ToolboxError",
    "ToolboxNotConfiguredError",
    "ToolboxAuthError",
    "ToolboxModelNotAllowedError",
    "ToolboxNotFoundError",
    "ToolboxValidationError",
    "ToolboxBudgetExceededError",
    "ToolboxRateLimitError",
    "ToolboxTimeoutError",
    "ToolboxServerError",
    "ToolboxConnectionError",
]
