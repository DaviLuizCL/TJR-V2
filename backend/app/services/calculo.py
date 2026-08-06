from app.core.errors import AppError
from app.models.criterio import CategoriaCriterio, CriterioTipo, ModificadorTipo
from app.models.ficha import Ficha
from app.models.modalidade import Modalidade
from app.schemas.simulacao import (
    DetalheCriterio,
    ModificadorAplicado,
    SimulacaoRequest,
    SimulacaoResponse,
)


def calcular(ficha: Ficha, modalidade: Modalidade, dto: SimulacaoRequest) -> SimulacaoResponse:
    valores_por_criterio = {v.criterio_id: v for v in dto.valores}

    subtotais_por_grupo: dict[str, float] = {}
    detalhamento: list[DetalheCriterio] = []
    modificadores_aplicados: list[ModificadorAplicado] = []

    soma_positivos = 0.0
    soma_penalidades = 0.0
    efeitos_multiplicativos: list[float] = []
    zera_total = False

    for grupo in ficha.grupos:
        subtotal_grupo = 0.0

        for criterio in grupo.criterios:
            valor_simulado = valores_por_criterio.get(criterio.id)

            if criterio.tipo == CriterioTipo.MODIFICADOR:
                aplicado = bool(valor_simulado and valor_simulado.aplicado)
                if aplicado:
                    valor_modificador = (
                        float(criterio.modificador_valor)
                        if criterio.modificador_valor is not None
                        else None
                    )
                    if criterio.modificador_tipo == ModificadorTipo.PERCENTUAL:
                        # Penalidade reduz o total (efeito negativo); pontuacao e bonus
                        # (efeito positivo).
                        sinal = 1 if criterio.categoria == CategoriaCriterio.PONTUACAO else -1
                        efeitos_multiplicativos.append(sinal * valor_modificador)
                    elif criterio.modificador_tipo == ModificadorTipo.ZERA_TOTAL:
                        zera_total = True
                    modificadores_aplicados.append(
                        ModificadorAplicado(
                            criterio_id=criterio.id,
                            nome=criterio.nome,
                            tipo=criterio.modificador_tipo.value,
                            valor=valor_modificador,
                        )
                    )
                continue

            if criterio.tipo == CriterioTipo.ESCALA:
                valor = (
                    valor_simulado.valor
                    if valor_simulado and valor_simulado.valor is not None
                    else 0
                )
                if valor not in (criterio.valores_permitidos or []):
                    raise AppError(
                        codigo="CRITERIO_VALOR_FORA_DA_ESCALA",
                        mensagem=(
                            f"Valor {valor} nao esta entre os valores permitidos de "
                            f"'{criterio.nome}'."
                        ),
                        status_code=422,
                    )
                pontos = float(valor)
                if criterio.categoria == CategoriaCriterio.PENALIDADE:
                    soma_penalidades += pontos
                    subtotal_grupo -= pontos
                    pontos_exibidos = -pontos
                else:
                    soma_positivos += pontos
                    subtotal_grupo += pontos
                    pontos_exibidos = pontos
                detalhamento.append(
                    DetalheCriterio(
                        criterio_id=criterio.id,
                        nome=criterio.nome,
                        tipo=criterio.tipo.value,
                        entrada={"valor": valor},
                        pontos=pontos_exibidos,
                    )
                )
                continue

            ocorrencias = (
                valor_simulado.ocorrencias
                if valor_simulado and valor_simulado.ocorrencias is not None
                else 0
            )

            if criterio.tipo == CriterioTipo.BOOLEANO and ocorrencias not in (0, 1):
                raise AppError(
                    codigo="CRITERIO_BOOLEANO_INVALIDO",
                    mensagem=f"Criterio booleano '{criterio.nome}' aceita apenas 0 ou 1.",
                    status_code=422,
                )

            if criterio.max_ocorrencias is not None and ocorrencias > criterio.max_ocorrencias:
                raise AppError(
                    codigo="CRITERIO_MAX_OCORRENCIAS_EXCEDIDO",
                    mensagem=(
                        f"'{criterio.nome}' excede max_ocorrencias ({criterio.max_ocorrencias})."
                    ),
                    status_code=422,
                )

            pontos = float(ocorrencias) * float(criterio.pontos or 0)

            if criterio.categoria == CategoriaCriterio.PENALIDADE:
                soma_penalidades += pontos
                subtotal_grupo -= pontos
                pontos_exibidos = -pontos
            else:
                soma_positivos += pontos
                subtotal_grupo += pontos
                pontos_exibidos = pontos

            detalhamento.append(
                DetalheCriterio(
                    criterio_id=criterio.id,
                    nome=criterio.nome,
                    tipo=criterio.tipo.value,
                    entrada={"ocorrencias": ocorrencias},
                    pontos=pontos_exibidos,
                )
            )

        subtotais_por_grupo[str(grupo.id)] = subtotal_grupo

    total = soma_positivos - soma_penalidades

    for efeito in efeitos_multiplicativos:
        total = total * (1 + efeito / 100)

    if zera_total:
        total = 0.0

    if total < 0 and not modalidade.permite_total_negativo:
        total = 0.0

    # Multiplicacao de floats (ex.: 100 * 1.1) pode gerar ruido de ponto
    # flutuante (110.00000000000001); arredondar evita expor isso ao usuario.
    total = round(total, 4)

    return SimulacaoResponse(
        total=total,
        subtotais_por_grupo=subtotais_por_grupo,
        detalhamento_por_criterio=detalhamento,
        modificadores_aplicados=modificadores_aplicados,
    )
