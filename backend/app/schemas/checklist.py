from uuid import UUID

from pydantic import BaseModel

from app.models.modalidade import TipoDisputa


class ChecklistItem(BaseModel):
    codigo: str
    ok: bool
    mensagem: str


class ChecklistModalidade(BaseModel):
    modalidade_id: UUID
    nome: str
    tipo_disputa: TipoDisputa
    itens: list[ChecklistItem]


class ChecklistOut(BaseModel):
    gerais: list[ChecklistItem]
    modalidades: list[ChecklistModalidade]
