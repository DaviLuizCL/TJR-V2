# TJR — Sistema de Gestão do Torneio Juvenil de Robótica

Sistema para coordenadores criarem modalidades/fichas, árbitros lançarem pontuação em campo
(pelo celular) e o público acompanhar o placar. Contexto completo do domínio e das decisões
técnicas está em [`CLAUDE.md`](./CLAUDE.md).

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, Alembic
- **Frontend:** React 18 + TypeScript + Vite, Tailwind CSS
- **Infra:** Docker Compose (`db`, `api`, `front`/nginx em produção)

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
- **Fichas publicadas** para as 7 modalidades (com grupos e critérios reais — pontuação,
  penalidade, escala e modificador), prontas pra lançar pontuação sem precisar montar nada na
  mão. Viagem ao Centro da Terra ganha uma ficha por nível (1 a 4).
- **16 equipes credenciadas** — `Nível 1 - Equipe A` a `Nível 4 - Equipe D` (4 por nível) —, cada
  uma já inscrita em todas as 7 modalidades do seu nível.

Tudo isso é o mesmo conteúdo (modalidade, ficha, critério, equipe, inscrição) que já existe hoje
no ambiente de desenvolvimento do time.

## Acessando

- Frontend: http://localhost:5173
- Backend (Swagger): http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

Login como coordenador com as credenciais do seed acima. Com o ambiente populado dá pra ir direto
pra rodadas/horários (individual) ou chaveamento (confronto) e lançar pontuação — fichas e
equipes já estão prontas.

## Rodando em modo produção

```bash
make up-prod      # builda e sobe db + api + front (nginx) em modo producao
make down-prod    # derruba
```

Diferenças do modo dev (`docker-compose.prod.yml`, sobreposto ao `docker-compose.yml` — mesmo
banco/volume, não duplica dado):

- **Um único ponto de entrada público:** `front` builda o bundle estático (`npm run build`) e
  serve via nginx na porta **80**, que também faz proxy reverso de `/api/` pro container `api` —
  não existe mais `VITE_API_URL` fixo em lugar nenhum, o front chama a API na mesma origem da
  página, então funciona em qualquer IP/host sem configuração (celular na mesma rede, VPS com
  domínio real, etc. — só trocar o que acessa a porta 80).
- `api` e `db` deixam de publicar porta pro host (só alcançáveis um pelo outro, dentro da rede
  do Docker) — só o `front` fica exposto.
- `api` roda sem `--reload` e sem montar o código do host como volume (roda só o que foi
  buildado na imagem).

Acesso: `http://<ip-da-maquina>` (sem porta) a partir de qualquer dispositivo na mesma rede.
Pra descobrir o IP local: `hostname -I` (Linux) ou `ipconfig` (Windows).

Antes de expor isso numa rede que não seja só o time de confiança (ex.: VPS pública), troque em
`.env`: `JWT_SECRET_KEY` (o repo já não versiona `.env`, só o `.env.example` com placeholder) e
considere trocar a senha do coordenador seed (`SEED_COORDENADOR_SENHA`) e a senha do Postgres
(`POSTGRES_PASSWORD` em `docker-compose.yml`, hoje `tjr` fixo) — nenhuma dessas foi trocada
automaticamente porque são credenciais que vocês usam pra logar/conectar, mudar sem avisar
quebraria o acesso que já está em uso.

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

## O que aconteceu na última rodada de correções

Sessão de teste real em campo (celular batendo no IP da rede local) revelou e corrigiu, nesta
ordem:

1. **`crypto.randomUUID()` quebrava em HTTP puro** — essa função só existe em "contexto seguro"
   (HTTPS/localhost); por HTTP simples (o caso real do ginásio) ela simplesmente não existe no
   navegador, e todo lançamento falhava com "Não foi possível registrar/confirmar o lançamento
   neste dispositivo". Corrigido com uma implementação própria em `frontend/src/lib/uuid.ts`
   (via `crypto.getRandomValues()`, sem essa restrição). **Qualquer `crypto.randomUUID()` novo
   que apareça no código deve usar esse helper, nunca a API nativa.**
2. **QA cego** (agente sem contexto do projeto, testando com conta de árbitro dedicada) achou um
   bug crítico: editar os critérios depois de "Registrar lançamento" só atualizava o preview,
   nunca o lançamento de verdade — "Confirmar" fechava com o valor antigo, sem aviso. Corrigido
   travando os campos assim que existe lançamento ativo (`PENDENTE`/`CONFIRMADO`).
3. **Seed gerava o Sumô errado** — modalidade `MATA_MATA` (chaveamento real, depende de quem
   ganha) estava sendo populada com o mesmo pareamento round-robin fixo do
   `TODOS_CONTRA_TODOS`, pré-gerando as 5 rodadas inteiras sem nenhuma depender do resultado da
   anterior. Corrigido: seed agora gera só a Rodada 1 do bracket pra `MATA_MATA`, e as próximas
   nascem sozinhas conforme os resultados chegam.
4. **Avanço de rodada não era por nível** — pontuar todas as partidas de um nível não gerava a
   final desse nível enquanto outro nível (maior ou só mais lento de pontuar) ainda estivesse em
   aberto. Cada nível corre seu próprio chaveamento e devia avançar sozinho; corrigido em
   `services/chaveamento.py::avancar_se_rodada_completa`.

Todas corrigidas em TDD (teste vermelho → código → teste verde), suíte completa validada, e
aplicadas ao banco em produção com verificação visual no navegador. Detalhe técnico completo de
cada uma está em [`CLAUDE.md`](./CLAUDE.md), seção 12.

## Testando manualmente (QA humano)

Contas disponíveis pra teste (seed):

- **Coordenador** — `admin@tjr.app` / `trocar-em-producao` (ou o que estiver em
  `SEED_COORDENADOR_EMAIL`/`SEED_COORDENADOR_SENHA` no `.env`). Enxerga tudo, inclusive
  "Staff" no cabeçalho pra cadastrar árbitro/secretaria com senha na hora
  (`/usuarios` → "Novo usuário").
- **Árbitro** — não vem pronto no seed; cadastre um pela tela "Staff" acima (papel `ARBITRO`),
  ou use uma conta de árbitro que já exista no ambiente que você está testando.

Pra testar pelo celular (mesma rede Wi-Fi da máquina que roda o sistema):

1. Suba em modo produção: `make up-prod` (serve pelo nginx na porta 80, sem `VITE_API_URL` fixo
   — funciona em qualquer IP da rede, não só `localhost`).
2. Descubra o IP da máquina: `hostname -I` (Linux).
3. No navegador do celular, acesse `http://<esse-ip>` (sem porta, e repare: é HTTP, não HTTPS —
   isso é esperado dentro da rede local do ginásio).

Roteiro sugerido de teste (cobre os fluxos reais do dia da competição):

- **Individual** (Dança, Resgate no Plano, Resgate de Alto Risco, Viagem ao Centro da Terra):
  Competições → Individual → escolher modalidade → aba "Pontuar" → lançar e confirmar pelo menos
  1 rodada de 1 equipe. Conferir que a aba "Horários" reprojeta o horário da próxima equipe da
  fila depois da confirmação.
- **Confronto todos-contra-todos** (Cabo de Guerra, Corrida de Carros Autônomos): Competições →
  Combate → escolher modalidade → "Pontuar" → decidir uma partida (o card de 1 clique, ou o
  scorer multi-critério da Corrida). Conferir que o card trava com vencedor/empate depois de
  decidido.
- **Confronto mata-mata** (Sumô), o roteiro mais sensível a bug de chaveamento:
  1. Gerar o chaveamento inicial (Combate → aba "Chaveamento" → modalidade Sumô → "Gerar
     chaveamento", só aparece se ainda não existir rodada).
  2. Pontuar **só as partidas de um nível** (ex.: só Nível 1), deixando os outros níveis em
     aberto de propósito.
  3. Voltar em Combate → Chaveamento → selecionar Sumô → selecionar o nível pontuado: a próxima
     rodada (ou a final, se só sobrou 1 confronto) **deve aparecer sozinha**, sem precisar que os
     outros níveis também terminem. Esse é exatamente o bug corrigido no item 4 acima — se a
     rodada não aparecer, é regressão.
  4. Reset (perigoso, só coordenador): botão "Resetar chaveamento" na mesma aba, some com
     rodada/partida/lançamento daquela modalidade e libera gerar de novo — usar só se realmente
     quiser desfazer, não para simples correção pontual.
- **Painel** (`/painel`, coordenador/secretaria): aba Ranking mostra a classificação de cada
  modalidade; aba Submissões lista os lançamentos, filtrável por rodada/equipe, com os combates
  já agrupados mostrando quem venceu.
- **Offline**: ativar modo avião no celular, lançar uma pontuação (fica "pendente" na fila
  local), voltar a rede e conferir que sincroniza sozinho sem duplicar.

Ao terminar um ciclo de teste no ambiente publicado, avise antes de eu rodar qualquer reset — os
lançamentos de teste ficam no mesmo banco que o torneio real vai usar.

## Problemas comuns

- **Porta ocupada (5432/8000/5173):** outro serviço local usando a mesma porta. Pare o serviço
  conflitante ou ajuste as portas em `docker-compose.yml`.
- **`make environment` falha na migration:** o container `api` provavelmente ainda não terminou
  de subir/buildar. Rode `docker compose ps` para conferir o status e tente de novo.
- **Front não encontra a API:** confirme que o container `api` está saudável
  (`docker compose ps`). Em dev, `VITE_API_URL` vem fixo em `http://localhost:8000` no
  `docker-compose.yml`; em produção não existe essa variável (o front chama a API pela mesma
  origem, via proxy do nginx) — se aparecer erro de rede em produção, o suspeito é o proxy
  `/api/` em `frontend/nginx.conf`, não `VITE_API_URL`.
