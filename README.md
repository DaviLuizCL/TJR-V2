# TJR — Sistema de Gestão do Torneio Juvenil de Robótica

Sistema para coordenadores criarem modalidades/fichas, árbitros lançarem pontuação em campo
(pelo celular) e o público acompanhar o placar. Contexto completo do domínio e das decisões
técnicas está em [`CLAUDE.md`](./CLAUDE.md).

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Alembic
- **Frontend:** React 18 + TypeScript + Vite, Tailwind CSS
- **Infra:** Docker Compose (`db`, `api`, `front`)

## Pré-requisitos

- Docker e Docker Compose
- `make` (opcional, mas os comandos abaixo assumem que existe)

## Subindo o projeto do zero

```bash
git clone git@github.com:DaviLuizCL/TJR-V2.git
cd TJR-V2
cp .env.example .env
```

O `.env.example` já vem com valores padrão que funcionam de primeira em ambiente local
(banco `tjr`/`tjr`, chave JWT de desenvolvimento, credencial do coordenador seed). Não é preciso
editar nada para rodar localmente.

```bash
make up                          # sobe db, api e front (docker compose up -d --build)
docker compose exec api alembic upgrade head   # aplica as migrations
```

Nesse ponto o banco existe, mas está vazio (sem evento, modalidade ou equipe). Para popular um
ambiente de teste completo:

```bash
make environment
```

Esse comando sobe os containers, aplica as migrations e roda o seed — tudo em um passo só (pode
rodar `make environment` direto do zero, sem precisar dos dois comandos acima). Ele é
**idempotente**: pode rodar de novo a qualquer momento sem duplicar dado.

O que `make environment` cria:

- **1 usuário coordenador** — login `admin@tjr.app` / senha `trocar-em-producao` (valores de
  `SEED_COORDENADOR_EMAIL`/`SEED_COORDENADOR_SENHA` no `.env`).
- **1 evento** — "TJR 2026".
- **7 modalidades**, as mesmas do torneio real, já com o tipo de disputa e formato de
  chaveamento corretos: Sumô (confronto, mata-mata), Cabo de Guerra (confronto,
  todos-contra-todos), Corrida de Carros Autônomos (confronto, todos-contra-todos), Dança
  (individual), Resgate no Plano (individual), Resgate de Alto Risco (individual) e Viagem ao
  Centro da Terra (individual, com ficha por nível).
- **40 equipes** — 10 por nível (níveis 1 a 4), nomeadas `Equipe 01 - Nivel 1` etc.

As modalidades sobem sem ficha (grupos/critérios de pontuação) nem inscrição de equipe — isso é
feito pela própria interface do coordenador (`Fichas`, dentro de cada modalidade), que já é o
fluxo real de criação. O seed só monta o esqueleto para não começar do zero.

## Acessando

- Frontend: http://localhost:5173
- Backend (Swagger): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

Login como coordenador com as credenciais do seed acima para criar fichas, inscrever equipes nas
modalidades, gerar rodadas/horários e liberar o ranking.

## Comandos úteis

```bash
make up                                          # sobe tudo
make down                                        # derruba tudo
make migrate                                     # aplica migrations pendentes
make environment                                 # sobe + migra + popular banco de teste

docker compose exec api alembic revision --autogenerate -m "descricao"
docker compose exec api pytest -q                # testes do backend
docker compose exec api ruff check . && docker compose exec api ruff format .

cd frontend && npm install
cd frontend && npm run dev                       # se preferir rodar o front fora do Docker
cd frontend && npm run typecheck && npm run lint
```

## Problemas comuns

- **Porta ocupada (5432/8000/5173):** outro serviço local usando a mesma porta. Pare o serviço
  conflitante ou ajuste as portas em `docker-compose.yml`.
- **`make environment` falha na migration:** o container `api` provavelmente ainda não terminou
  de subir/buildar. Rode `docker compose ps` para conferir o status e tente de novo.
- **Front não encontra a API:** confirme que o container `api` está saudável
  (`docker compose ps`) e que `VITE_API_URL` (opcional, default `http://localhost:8000`) não foi
  sobrescrito.
