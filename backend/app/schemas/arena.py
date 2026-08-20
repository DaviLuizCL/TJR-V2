from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import NomeObrigatorio


class ArenaCreate(BaseModel):
    modalidade_id: UUID
    nome: NomeObrigatorio
    niveis_aplicaveis: list[int] | None = None
    ativo: bool = True


class ArenaUpdate(BaseModel):
    nome: NomeObrigatorio | None = None
    niveis_aplicaveis: list[int] | None = None
    ativo: bool | None = None


class ArenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    modalidade_id: UUID
    nome: str
    niveis_aplicaveis: list[int] | None
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
