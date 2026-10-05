from uuid import UUID

from pydantic import BaseModel, Field

from app.models.modalidade import FormatoChaveamento
from app.schemas.common import NomeObrigatorio


class CriarPartidaManualRequest(BaseModel):
    equipe_a_id: UUID
    equipe_b_id: UUID | None = None
    rodada_numero: int = Field(ge=1)
    # TODOS_CONTRA_TODOS = fase de grupos (aceita empate);
    # MATA_MATA = eliminatoria (empate vai pro combate extra de desempate).
    formato_chaveamento: FormatoChaveamento


class ResetarChaveamentoRequest(BaseModel):
    justificativa: NomeObrigatorio
