from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import (
    agendamentos,
    arenas,
    auth,
    chave,
    chaveamento,
    criterios,
    equipes,
    eventos,
    fichas,
    grupos,
    health,
    inscricoes,
    lancamentos,
    modalidades,
    ranking,
    rodadas,
    usuarios,
)
from app.core.config import settings
from app.core.errors import AppError

app = FastAPI(title="TJR")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(eventos.router, prefix="/api/v1", tags=["eventos"])
app.include_router(modalidades.router, prefix="/api/v1", tags=["modalidades"])
app.include_router(equipes.router, prefix="/api/v1", tags=["equipes"])
app.include_router(inscricoes.router, prefix="/api/v1", tags=["inscricoes"])
app.include_router(rodadas.router, prefix="/api/v1", tags=["rodadas"])
app.include_router(lancamentos.router, prefix="/api/v1", tags=["lancamentos"])
app.include_router(fichas.router, prefix="/api/v1", tags=["fichas"])
app.include_router(grupos.router, prefix="/api/v1", tags=["grupos"])
app.include_router(criterios.router, prefix="/api/v1", tags=["criterios"])
app.include_router(ranking.router, prefix="/api/v1", tags=["ranking"])
app.include_router(chaveamento.router, prefix="/api/v1", tags=["chaveamento"])
app.include_router(chave.router, prefix="/api/v1", tags=["chave"])
app.include_router(arenas.router, prefix="/api/v1", tags=["arenas"])
app.include_router(agendamentos.router, prefix="/api/v1", tags=["agendamentos"])
app.include_router(usuarios.router, prefix="/api/v1", tags=["usuarios"])


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    erro = {"codigo": exc.codigo, "mensagem": exc.mensagem, "detalhes": exc.detalhes}
    return JSONResponse(status_code=exc.status_code, content={"erro": erro})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "erro": {
                "codigo": "DADOS_INVALIDOS",
                "mensagem": "Dados invalidos.",
                "detalhes": {"erros": exc.errors()},
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": {"codigo": "ERRO_HTTP", "mensagem": str(exc.detail), "detalhes": {}}},
    )
