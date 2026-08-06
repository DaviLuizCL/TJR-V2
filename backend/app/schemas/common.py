from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    itens: list[T]
    total: int
    page: int
    size: int
