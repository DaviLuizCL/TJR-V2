from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, StringConstraints

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    itens: list[T]
    total: int
    page: int
    size: int


# Nome nunca pode ser vazio nem so espacos (BUG-07): tira espaco das pontas e
# exige pelo menos 1 caractere depois disso. Usado em todo schema que tem um
# campo `nome` de criacao/edicao (equipe, evento, modalidade, arena, usuario).
NomeObrigatorio = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
