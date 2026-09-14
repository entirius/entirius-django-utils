# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Pydantic contract of the toolbox completion API (``POST complete/``, ``GET models/``)."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Tag = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.:-]{1,64}$")]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class CompletionRequest(BaseModel):
    """Request body of ``POST ai-completion/…/complete/``; serialise with ``exclude_none=True``."""

    model_config = ConfigDict(extra="forbid")

    model: str
    messages: list[Message] = Field(min_length=1)
    json_schema: dict | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=8192)
    tags: list[Tag] = Field(default_factory=list, max_length=10)


class Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int
    output_tokens: int


class CompletionResponse(BaseModel):
    """Response of ``POST complete/``; store it through ``model_dump(mode="json")`` (``cost`` is a Decimal)."""

    model_config = ConfigDict(extra="ignore")

    output: str | None
    parsed: dict | None
    usage: Usage
    cost: Decimal | None
    model: str
    attempts: int
    request_id: str


class ModelInfo(BaseModel):
    """One entry of the plain list returned by ``GET ai-completion/…/models/``."""

    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    provider: str
    model_id: str
    display_name: str
    supports_structured_output: bool
    max_input_tokens: int | None
    input_price_per_1k: Decimal | None
    output_price_per_1k: Decimal | None
