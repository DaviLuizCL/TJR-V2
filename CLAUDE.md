# CLAUDE.md — Sistema TJR

Contexto permanente do projeto. Leia este arquivo inteiro antes de escrever qualquer código.
O que **fazer agora** está no prompt da sessão, não aqui. Aqui está **como fazer**.

---

## 1. O que é o sistema

Sistema de gestão de competições do **TJR (Torneio Juvenil de Robótica)**.

Coordenadores criam modalidades e as fichas de pontuação de cada uma. Árbitros lançam a
pontuação **pelo celular, dentro do ginásio, com internet ruim ou nenhuma**. A secretaria
consolida, e o público acompanha o placar.

Três verdades que moldam todas as decisões técnicas:

1. **O dia da competição não perdoa.** Nada pode travar por falta de rede, e nenhum ponto
   lançado pode sumir.
2. **A pontuação é jurídica.** Equipe reclama, árbitro erra, coordenador corrige. Tudo precisa
   de rastro, versão e assinatura.
3. **A ficha é dado, não código.** Modalidade nova nunca deve exigir deploy.

---

## 2. Stack

**Backend**
- Python 3.12 · FastAPI · Pydantic v2
- SQLAlchemy 2.0 (estilo declarativo, `Mapped[]`) · Alembic
- PostgreSQL 16
- Autenticação JWT (access + refresh), senha com bcrypt
- Testes: pytest + httpx AsyncClient

**Frontend**
- React 18 + TypeScript + Vite
- React Router · TanStack Query (estado de servidor) · Zustand (estado local/fila offline)
- Tailwind CSS
- PWA (vite-plugin-pwa) + IndexedDB (Dexie) para a fila offline
- Formulários: react-hook-form + zod

**Infra**
- Docker Compose (api, db, front/nginx) rodando em VPS
- Migrations sempre via Alembic. Nunca `create_all()` fora de teste.

Não introduza biblioteca nova sem perguntar antes.

---

## 3. Estrutura

```
/
├── docker-compose.yml
├── backend/
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/          # config, security, deps
│   │   ├── db/            # session, base
│   │   ├── models/        # SQLAlchemy
│   │   ├── schemas/       # Pydantic
│   │   ├── api/v1/        # routers
│   │   ├── services/      # regra de negócio (cálculo, chaveamento, sync)
│   │   └── tests/
│   └── pyproject.toml
└── frontend/
    └── src/
        ├── api/           # client + tipos gerados do OpenAPI
        ├── features/      # modalidade/, ficha/, arbitragem/, chaveamento/
        ├── components/    # UI compartilhada
        ├── hooks/
        ├── lib/           # offline queue, storage, calculo (preview)
        └── pages/
```

**Regra de camada:** router valida e delega. Toda regra de negócio vive em `services/`.
Nada de query SQLAlchemy dentro de router.

---

## 4. Comandos

```bash
docker compose up -d --build              # sobe tudo
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "descricao"
docker compose exec api pytest -q
docker compose exec api ruff check . && ruff format .

cd frontend && npm run dev
cd frontend && npm run typecheck && npm run lint
```

---

## 5. Glossário do domínio

**Termos de domínio ficam em português no código** (sem acento, sem cedilha, snake_case em
Python/DB, camelCase no TS). Termos técnicos ficam em inglês. Não traduza os termos abaixo —
use exatamente estas palavras em models, endpoints, tipos e componentes.

| Termo | Significado |
|---|---|
| `evento` | Uma edição do torneio (ex.: TJR 2026). Raiz de tudo. |
| `modalidade` | Desafio disputado (Sumô, Dança, Resgate no Plano...). Pertence a um evento. |
| `nivel` | Faixa de 1 a 4 dentro de uma modalidade. |
| `ficha` | Template de pontuação de uma modalidade/nível. **Versionada.** |
| `grupo` | Seção da ficha (ex.: "Parte Artística", "Parte Técnica"). |
| `criterio` | Linha da ficha que gera ou desconta ponto. |
| `rodada` | Uma passagem da modalidade (Rodada 1, 2, 3), com horário. |
| `arena` | Estação física de uma modalidade individual onde as equipes se apresentam a cada rodada. |
| `agendamento` | Horário e arena atribuídos a uma equipe dentro de uma rodada (modalidade individual). |
| `tentativa` | Subdivisão da rodada (ex.: "1º cubo" e "2º cubo" em Viagem ao Centro da Terra). |
| `equipe` | Time inscrito, pertence a um nível. |
| `inscricao` | Vínculo equipe ↔ modalidade. |
| `partida` | Confronto entre duas equipes (só em modalidade de confronto). |
| `lancamento` | Uma ficha preenchida por um árbitro (equipe + rodada + tentativa). |
| `item` | Uma linha do lançamento: critério + ocorrências/valor + pontos resultantes. |
| `chaveamento` | Geração e acompanhamento das chaves de confronto. |
| `consolidacao` | Como as rodadas viram a nota final da equipe. |
| `desempate` | Regras ordenadas para desempatar a classificação. |
| `rubrica` | Confirmação/assinatura do árbitro e do capitão que fecha o lançamento. |

**Nunca use:** `form`, `sheet`, `score_card`, `match_form`, `bracket_form` — é `ficha`,
`criterio`, `lancamento`, `chaveamento`.

---

## 6. Modelo conceitual

```
evento
 └── modalidade (tipo_disputa: INDIVIDUAL | CONFRONTO)
      ├── ficha (versionada; 1 por nível OU 1 única para todos)
      │    └── grupo
      │         └── criterio
      ├── rodada
      │    ├── partida        (só quando CONFRONTO)
      │    └── agendamento    (só quando INDIVIDUAL: equipe + arena + horário)
      ├── arena                (só INDIVIDUAL; pertence a UMA modalidade)
      └── inscricao ── equipe

lancamento (ficha_versao + rodada + tentativa + equipe [+ partida] + arbitro)
 └── item (criterio_snapshot + ocorrencias/valor + pontos)
```

### Tipos de critério

| tipo | comportamento |
|---|---|
| `CONTADOR` | `ocorrencias × pontos`. Respeita `max_ocorrencias`. Ex.: "+10 por lombada". |
| `BOOLEANO` | Fez ou não fez. Ex.: "Finalização com Sucesso +50". |
| `ESCALA` | Só aceita valores de `valores_permitidos`. Ex.: Dança aceita 0, 2, 5, 7 ou 10. |
| `PENALIDADE` | Igual ao CONTADOR, mas subtrai do total. |
| `MODIFICADOR` | Aplicado **depois** da soma: `PERCENTUAL` (ex.: −10% se passar de 5 min) ou `ZERA_TOTAL` (ex.: paralisação anula a apresentação). |

**Ordem de cálculo, sempre:** soma dos positivos → subtrai penalidades → aplica modificadores
percentuais → aplica zeradores → aplica piso zero (o total de um lançamento nunca é negativo,
salvo se a modalidade marcar `permite_total_negativo`).

### Chaveamento de modalidade CONFRONTO

`formato_chaveamento`: `MATA_MATA` ou `TODOS_CONTRA_TODOS`. (Dupla eliminação existiu e foi
**removida** — bracket superior/inferior confundia mais do que ajudava; se voltar a fazer sentido
um dia, é feature nova, não reintrodução do código antigo.)

- **Equipes de níveis diferentes nunca se enfrentam.** Cada nível corre seu próprio
  chaveamento/returno de forma independente dentro da mesma modalidade (`Partida.nivel`), em
  **todos** os formatos acima. Um nível pode chegar ao campeão/terminar antes de outro nível,
  com mais equipes, terminar.
- **Cada partida é decidida em `modalidade.tentativas_por_rodada` combates** (um `lancamento`
  por `tentativa` por equipe). Vencedor da partida = quem ganha mais combates individuais, não
  quem soma mais pontos. Combate empatado não conta pra nenhum lado. Se a contagem de combates
  também empatar, mata-mata libera um **combate extra de desempate** ("ponto de ouro", tentativa
  `tentativas_por_rodada + 1`, sem opção de empate) que decide a partida sem reescrever o
  resultado dos combates anteriores; se até esse combate extra empatar, aí sim a partida fica
  aberta (precisa de correção do coordenador). Todos-contra-todos não usa ponto de ouro — fecha
  `EMPATADA` direto.
- Vencedor de partida é sempre automático (compara os combates), e o avanço de rodada é
  automático assim que a última partida da rodada atual fecha — sem clique do coordenador.
- **Bye (número ímpar de equipes) é resolvido rodada a rodada, não calculado de antemão.** Se a
  contagem de sobreviventes ficar ímpar no meio do bracket (comum quando o total inicial não é
  potência de 2, ex.: 48 equipes → 48→24→12→6→3), o bye aparece nessa rodada, não
  necessariamente na primeira. Decisão consciente do usuário — a alternativa (calcular todos os
  byes na rodada 1 pra nunca mais precisar depois) foi implementada e revertida a pedido dele.

---

## 7. Regras invioláveis

Se alguma tarefa parecer exigir quebrar uma destas, **pare e pergunte**.

1. **O total é calculado no backend.** O front pode calcular preview para feedback imediato,
   mas o valor persistido é sempre o que o serviço de cálculo produziu a partir dos itens.
   Nunca aceite `total` vindo do cliente.
2. **Ficha publicada é imutável.** Editar critério de ficha publicada cria uma **nova versão**.
   Lançamentos apontam para a versão que usaram.
3. **Todo item guarda `criterio_snapshot`** (nome, tipo, pontos, regra) no momento do
   lançamento. Mudança futura de critério jamais altera pontuação já registrada.
4. **Lançamento `CONFIRMADO` é imutável.** Correção só por coordenador, com justificativa
   obrigatória, gerando registro em `audit_log` e nova `revision`.
5. **Nada de DELETE em dado de pontuação.** Anulação é status (`ANULADO`), não remoção.
6. **Toda escrita do app do árbitro é idempotente** via `client_operation_id` (UUID gerado no
   dispositivo). Reenvio retorna o mesmo recurso, nunca duplica.
7. **Datas em UTC no banco**, exibição em `America/Fortaleza`. Duração em segundos, inteiro.
8. **Autorização por papel em todo endpoint**, sem exceção: `COORDENADOR`, `ARBITRO`,
   `SECRETARIA`, `PUBLICO`.
9. **Equipes de níveis diferentes nunca se enfrentam em modalidade de confronto.** Chaveamento e
   returno são sempre separados por nível (ver seção 6).
10. **Modalidade INDIVIDUAL: nenhum lançamento sem arena atribuída.** `criar_lancamento` recusa
    com `422 EQUIPE_SEM_ARENA_ATRIBUIDA` se não existir `agendamento` (equipe + rodada + arena)
    pra aquela equipe naquela rodada. Reflete o fluxo real do dia da competição: arenas são
    montadas primeiro (podem ter dificuldade/nível diferentes), só depois o horário é gerado e as
    equipes são chamadas — não existe "equipe pontuando sem lugar pra competir". Vale só pra
    INDIVIDUAL; CONFRONTO não usa arena/agendamento neste sistema.

---

## 8. Contrato offline-first

O app do árbitro precisa funcionar com o celular no modo avião e sincronizar sozinho quando a
rede voltar.

- **Download antes da rodada:** modalidade, ficha (versão), rodadas, equipes e partidas do
  árbitro ficam em cache no IndexedDB, carimbados com `ficha_versao_id`.
- **Outbox:** todo lançamento vai primeiro para a fila local com `client_operation_id`,
  `revision` e `updated_at_client`. A UI confirma na hora; o envio é assíncrono.
- **Sync:** ao voltar rede, a fila é drenada em ordem. `POST` repetido com o mesmo
  `client_operation_id` retorna 200 com o recurso existente.
- **Conflito:** se o `revision` enviado for menor que o do servidor, responde `409` com o estado
  atual e o app mostra a divergência ao árbitro. **Não sobrescreva silenciosamente.**
- **Ficha desatualizada:** se o `ficha_versao_id` do lançamento não for a versão vigente, o
  lançamento é aceito (a versão dele é a fonte da verdade) e sinalizado para a secretaria.
- **Estado visível:** o app sempre mostra pendente / enviando / sincronizado por lançamento.

---

## 9. Convenções de API

- Prefixo `/api/v1`. Recursos no plural: `/modalidades`, `/fichas`, `/lancamentos`.
- Erro padronizado: `{"erro": {"codigo": "FICHA_PUBLICADA", "mensagem": "...", "detalhes": {}}}`.
  Código em SCREAMING_SNAKE, estável — o front decide comportamento por ele, nunca pela mensagem.
- Listagem paginada: `?page=1&size=50` → `{"itens": [], "total": n, "page": 1, "size": 50}`.
- Todo response model é Pydantic explícito. Nunca devolva model do SQLAlchemy direto.
- Tipos do front são gerados do OpenAPI. Não escreva interface TS à mão para payload de API.

---

## 10. UI

O árbitro opera **de pé, no celular, com pressa**. A tela de lançamento manda no design:

- Alvo de toque mínimo de 48px. Botões `+` e `−` grandes, um por critério.
- Nada de scroll horizontal, nada de modal para lançar ponto.
- Total parcial sempre visível e fixo na tela.
- Ação destrutiva (anular, fechar ficha) exige confirmação explícita.
- Painel do coordenador pode ser desktop-first; app do árbitro é mobile-first, sem exceção.

---

## 11. TDD — teste primeiro, sempre

Este projeto é desenvolvido em **TDD**. Não existe funcionalidade escrita antes do teste que a
descreve. Isso vale para regra de negócio, endpoint, validação e correção de bug.

**O ciclo, em toda tarefa:**

1. **Red** — escreva o teste que descreve o comportamento pedido. Rode e **mostre que ele
   falha**, pelo motivo certo (não por import quebrado ou fixture faltando).
2. **Green** — escreva o mínimo de código que faz o teste passar. Nada além disso.
3. **Refactor** — limpe o código com a suíte verde. Se ficar vermelha, volte.

**Regras:**

- Teste que nunca foi vermelho não conta. Se você escreveu o código antes, apague o código,
  escreva o teste, veja falhar, e reescreva.
- **Bug é teste primeiro.** Reproduza a falha em um teste que falha, só então corrija.
- Um comportamento por teste. Nome descreve o comportamento, não o método:
  `test_criterio_escala_rejeita_valor_fora_da_lista`, não `test_validate_criterio`.
- Cubra o caminho feliz **e** os erros. Toda regra da seção 7 (invioláveis) e toda validação de
  ficha precisa de teste que prove que o sistema recusa a operação proibida.
- Regra de pontuação tem teste de cálculo obrigatório, com valores conferidos na mão. É a parte
  do sistema que uma equipe pode contestar — ela não anda sem teste.
- Nunca ajuste o teste para passar em cima de um código errado. Se a expectativa do teste estava
  errada, diga isso explicitamente e explique o porquê antes de mudar.
- Não deixe teste pulado (`skip`/`xfail`) sem me avisar e justificar.
- Suíte tem que estar verde antes de você declarar qualquer bloco pronto. Rode
  `pytest -q` (e `npm run typecheck`) e me mostre a saída.

**Onde:** backend em `app/tests/` espelhando a estrutura de `app/` (`tests/services/`,
`tests/api/v1/`). Front: Vitest + Testing Library, teste ao lado do componente
(`Componente.test.tsx`), focado em comportamento visível, não em implementação.

**Ordem de reporte:** ao concluir uma tarefa, mostre nesta ordem — o teste escrito, a saída
vermelha, o código, a saída verde.

---

## 12. Fases do projeto

Não implemente fase futura sem pedido explícito. Modele os dados pensando nelas, mas não
escreva o código.

Backlog de próximas user stories (fora do que já está descrito aqui) fica em `HISTORIAS.md` na
raiz do repo — checar lá antes de perguntar "o que fazer agora".

1. ~~Painel de criação de modalidade e ficha~~ — completa.
2. ~~Equipes, inscrições e rodadas com horário~~ — completa.
3. ~~App do árbitro e lançamento de pontuação~~ — fluxo **online** completo (individual e
   confronto, com seletor de tentativa/partida). Fila offline (outbox/Dexie do PWA, seção 8)
   **ainda não implementada** — adiamento consciente, não esquecido.
4. **Chaveamento e placar público** ← atual. Já prontos: motor de chaveamento (mata-mata,
   todos-contra-todos) separado por nível, partida em
   melhor-de-3 combates, ranking público por modalidade (liberado pelo coordenador, formato de
   classificação varia por `tipo_disputa`/`formato_chaveamento` — nota para individual,
   vitórias/empates/derrotas/pontos para todos-contra-todos, vitórias/derrotas/eliminado-por
   para mata-mata) e painel staff (`/painel`) com abas de ranking e auditoria
   de submissões — hoje também filtrável por rodada (`RodadaSubmissoesPage`, link "Ver fichas
   enviadas" a partir da tela de Rodadas) e por equipe (`EquipeSubmissoesPage`, link
   "Submissões" a partir da tela de Equipes, sem exigir `evento_id`, já que equipe não pertence a
   um evento específico). Consolidação ganhou o modo `IGNORA_MENOR_NOTA` (soma todas as rodadas
   lançadas exceto a de menor nota; com 1 só rodada lançada, conta ela mesma).

   Agendamento de horário/arena por equipe em modalidade individual (aba "Horários" do header —
   rotação de arena por nível, restrita a COORDENADOR, geração incremental por lote de rodadas;
   ver regra inviolável 10) e aba **"Pontuar"** — fluxo principal do árbitro pra lançar nota: em
   vez de navegar Rodadas → Ver rodadas → Lançar notas escolhendo equipe/tentativa num select,
   `/eventos/:eventoId/modalidades/:modalidadeId/pontuar` mostra só a próxima pendência (rodada +
   tentativa) de cada equipe, ordenada com as mais atrasadas primeiro (equipe que termina uma
   rodada "desce" na lista, liberando espaço pras que ainda estão atrás), com badge quando a
   equipe já tem lançamento `PENDENTE` (registrado, não confirmado) esperando ação, e bloqueia
   visualmente (sem virar link, com atalho pra gerar horário) quando a equipe não tem arena
   atribuída naquela rodada — reflexo direto da regra inviolável 10. Clicar num card vai direto
   pra ficha (sem seletor de equipe/nível/tentativa) via query string
   (`?equipeId=&tentativa=`) no `LancamentoFormPage`, e confirmar o lançamento volta
   automaticamente pra tela de Pontuar. O fluxo antigo (Rodadas → Lançar notas com os seletores
   manuais) continua existindo pra pontuar fora da ordem sugerida.

   Wizard de criação/edição de modalidade (`ModalidadeWizardPage`) ganhou os campos
   `tentativas_por_rodada` e `pausa_entre_rodadas_seg` na etapa "Rodadas e duração" — antes eram
   propositalmente omitidos (havia até teste travando a ausência); decisão revertida porque
   modalidade de confronto precisa configurar "melhor de N combates" pela tela, e a ausência de
   `pausa_entre_rodadas_seg` no formulário fazia rodadas saírem coladas na geração de horário
   (regra já existia no backend em `agendamento.py`, só não tinha campo pra preencher). Criação
   (não edição) de modalidade **INDIVIDUAL** também passou a poder embutir, na mesma etapa: uma
   lista de arenas (nome + níveis atendidos) e a geração automática das `qtd_rodadas` rodadas
   vazias (sem horário) — ao salvar, o front encadeia `POST /modalidades` →
   `POST /rodadas/gerar` → `POST /arenas` × N. Não se aplica a `CONFRONTO`: `MATA_MATA` gera
   rodada dinamicamente conforme o chaveamento avança (uma de cada vez, recusa se já existir
   rodada) e `TODOS_CONTRA_TODOS` mantém "Gerar rodadas" manual em `RodadaListPage`.

   Fluxo **Pontuar** ganhou um branch pra `CONFRONTO`: a rota
   `/eventos/:eventoId/modalidades/:modalidadeId/pontuar` agora é despachada por
   `PontuarRoutePage`, que olha `modalidade.tipo_disputa` e escolhe entre a `PontuarPage`
   (individual, já descrita acima) e a
   nova `PontuarCombatePage`. Essa segunda é card **por partida**, não por equipe: lista todas as
   partidas de todas as rodadas da modalidade numa ordem estável (rodada → nível → criação, sem
   reordenar dinamicamente) — partida decidida (`ENCERRADA`/`EMPATADA`) **não some da lista**,
   fica com o card travado mostrando vencedor em verde/perdedor em vermelho (ou "Empate"/"(bye)"
   quando cabível); só a pendente é clicável. Clicar numa pendente abre `PartidaScorerPage`
   (`.../rodadas/:rodadaId/partidas/:partidaId/pontuar`), que mostra um card por combate
   (tentativa) já pré-montado pra essa partida — sem seletor de equipe nem de tentativa. Quando a
   ficha da modalidade tem exatamente 1 critério: tipo `BOOLEANO` mostra "Defina o vencedor" com
   um botão neutro por equipe + "Empate" (um clique já registra e confirma os dois lançamentos,
   só fica verde/vermelho depois de decidido); tipo `ESCALA` mostra "Defina o resultado" com um
   botão por valor não-zero de `valores_permitidos` pra cada equipe + "Empate" (clicar num valor
   de uma equipe manda ela com esse valor e a outra com 0 — fisicamente as duas não podem ter
   "resultado" no mesmo combate). Ficha com mais de 1 critério cai num link "Lançar pela ficha
   completa" pro `LancamentoFormPage` genérico, que ganhou suporte a pré-seleção via
   `?partidaId=` (esconde o seletor de partida, mantém equipe/tentativa manuais) — usado também
   como rota de escape pra esse caso. Rótulo de valor de `ESCALA` é mapeado à mão em
   `ROTULOS_ESCALA` (`PartidaScorerPage.tsx`), hoje só pro critério "Resultado do arrasto"
   (1 = "Arrasto parcial", 2 = "Arrasto pro fosso"); sem mapa, mostra o número cru.

   Limitação conhecida (não é bug, é a regra já existente em `chaveamento.py`): uma partida só
   fecha quando as `tentativas_por_rodada` tentativas estiverem `CONFIRMADO` dos dois lados —
   mesmo se o resultado já está matematicamente decidido antes disso (ex.: 2 vitórias de 3 numa
   modalidade melhor-de-3). Combate empatado (nenhum lado marca ponto) não conta pra nenhum lado;
   se o total de combates também empatar, mata-mata libera o combate extra de desempate (seção 6);
   se até ele empatar, a partida fica aberta (precisa correção manual do coordenador) e
   todos-contra-todos fecha `EMPATADA` direto, sem desempate.

   **`DUPLA_ELIMINACAO` foi removida do sistema** (modelo, migration, `chaveamento.py`,
   `consolidacao.py`, front) depois de rodar de verdade: o usuário achou o badge
   "Superior"/"Inferior" confuso e pediu pra tirar o formato inteiro, não só o rótulo visual —
   ele nunca tinha "resolvido" direito (`eliminado_por` só era preenchido pra `MATA_MATA`, gap já
   mapeado antes). Migration converte modalidade existente com esse formato pra `MATA_MATA` antes
   de estreitar o enum, e dropa a coluna `bracket`/tipo `partida_bracket`. Se compensar reintroduzir
   dupla-eliminação um dia, é decisão nova, não reaproveitar o código revertido.

   Sessão que fechou chaveamento/pontuação de combate ponta a ponta (a partir de teste real com
   bracket de 48 equipes, "só pra ver a bagaceira"):
   - **Combate extra de desempate ("ponto de ouro")**: `registrar_resultado_lancamento` tenta a
     tentativa `tentativas_por_rodada + 1` quando os combates configurados empatam (só pra
     `MATA_MATA`); `PartidaScorerPage` libera esse combate extra sem opção de "Empate" (força
     decisão). Resultado dos combates originais nunca é reescrito — é uma tentativa a mais, não
     uma correção.
   - **`PartidaScorerPage` volta sozinha pra `/pontuar`** assim que a partida decide (fechou
     `ENCERRADA`/`EMPATADA`), sem precisar clicar em nada — pensado pra agilizar lançar muitas
     partidas seguidas (bracket grande). Substituiu o banner manual "Ir para a próxima rodada".
   - **Nome de fase compartilhado** (`lib/fase-chaveamento.ts`, `nomeFase` +
     `calcularTotalRodadasPorNivel`): calcula Final/Semifinal/Quartas/Oitavas de Final por nível a
     partir de `ceil(log2(equipes da rodada 1))`; bracket grande demais (>16 equipes seguindo pro
     mesmo nome) cai de volta pra `Rodada N`. Usado tanto em `RodadaListPage` (selo por partida,
     dentro do grupo por nível) quanto em `PontuarCombatePage` (agora agrupado em **seções por
     fase**, não lista plana — `TODOS_CONTRA_TODOS` vira uma seção só, "Fase de Grupos"). Ordem
     das seções é da mais nova pra mais antiga (Final antes de Semifinal etc.) — é o que importa
     assim que uma rodada fecha e libera a próxima. Dentro de cada seção, partida pendente vem
     antes da já decidida.
   - **Badge "🏆 Campeão"** em `RodadaListPage`: teve bug real (mostrava campeão numa vitória de
     semifinal só porque aquele time depois viria a ser campeão) — corrigido comparando "essa
     partida é a última rodada conhecida do nível E é a única partida do nível ali", não mais
     comparando `equipe_id` vencedora contra "quem é o campeão".
   - `PontuarCombatePage` ganhou texto explícito "Vencedor: X" nos cards decididos (antes só tinha
     cor verde/vermelho no nome — ruim de ler rápido e pior ainda pra daltonismo vermelho-verde) e
     filtro "Filtrar por nível".
   - Bye de número ímpar de equipes continua sendo resolvido rodada a rodada (pode cair em
     qualquer rodada, não só na primeira) — ver seção 6.

   Falta: painel do público além do ranking (ex.: placar ao vivo/andamento de partida), tela de
   correção de lançamento no front (endpoint já existe no backend), desempate configurável
   (`desempates`) pra `TODOS_CONTRA_TODOS` — o campo hoje só é lido pra `INDIVIDUAL`
   (`_classificacao_todos_contra_todos` em `consolidacao.py` ordena só por `nota_final`, ties
   ficam em ordem de inserção sem sinalizar empate).

   **Header reorganizado**: eram 10 links soltos lado a lado (Eventos/Equipes/Modalidades/Fichas/
   Rodadas/Combates/Painel/Chaveamento/Horários/Pontuar). `Rodadas`+`Horários`+`Pontuar`
   (os 3 fluxos de modalidade `INDIVIDUAL`) viraram abas dentro de **`IndividualHubPage`**
   (`/eventos/:id/individual`, mesmo padrão de aba do `PainelPage` — `role="tablist"`, estado
   local, aba inicial via `?aba=`). `Chaveamento` virou aba dentro de **`ConfrontoHubPage`**
   (reaproveitou a rota `/eventos/:id/combates`, que já existia). As páginas antigas
   (`PontuarDashboardPage`, `RodadaDashboardPage`, `HorarioDashboardPage`, `CombateDashboardPage`,
   `ChaveamentoPage`) continuam existindo como componentes — só perderam o wrapper
   `<main>`/`<h1>` próprio, porque agora só renderizam como conteúdo de aba dentro do hub. Header
   final: Eventos/Equipes/Modalidades/Fichas/Individual/Combates/Painel (7 itens).

---

## 13. O que não fazer

- **Não escreva código de funcionalidade antes do teste que a descreve** (seção 11).
- Não crie tabela ou coluna sem migration Alembic.
- Não coloque regra de pontuação no front (só preview).
- Não use `create_all()`, `dict()` do Pydantic v1, ou `datetime.utcnow()` (use
  `datetime.now(timezone.utc)`).
- Não invente campo que não está no spec — pergunte.
- Não escreva teste que dependa de banco de produção ou de ordem de execução.
- Não faça commit de `.env`, dump de banco ou dado real de equipe.
- Não refatore área fora do escopo da tarefa atual sem avisar.