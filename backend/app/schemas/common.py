from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, EmailStr, StringConstraints

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

# Email tratado como case-insensitive (convencao de todo provedor real, mesmo
# o RFC permitindo case sensitivity): sem isso, duas contas com o mesmo email
# em case diferente podem coexistir, e login com case diferente do cadastro
# falha. Usado em todo schema que recebe email pra criar conta ou logar.
EmailNormalizado = Annotated[EmailStr, AfterValidator(str.lower)]
