from fastapi import status


class AppError(Exception):
    def __init__(
        self,
        codigo: str,
        mensagem: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detalhes: dict | None = None,
    ) -> None:
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_code = status_code
        self.detalhes = detalhes or {}
        super().__init__(mensagem)
