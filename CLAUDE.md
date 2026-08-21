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
3. ~~App do árbitro e lançamento de pontuação~~ — fluxo online completo (individual e confronto,
   com seletor de tentativa/partida) **+ outbox de envio** (Dexie, seção 8): lançamento grava na
   fila local na hora do clique, sincroniza sozinho quando a rede volta, nunca sobrescreve
   conflito em silêncio. Cache de leitura offline (baixar ficha/rodadas/equipes/partidas antes da
   rodada, pra abrir o app sem rede nenhuma) continua **fora de escopo** — adiamento consciente,
   não esquecido; ver detalhe no fim da seção 12.
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

   **Sessão de correção de um relatório de testes de terceiro** (20/08/2026, commit `399793b`
   testado, `RELATORIO_TESTES_TJR_V2.pdf` — um amigo do usuário rodou os fluxos manualmente e
   achou 7 defeitos reais apesar de toda a suíte automatizada estar verde). Todos corrigidos em
   TDD, um por vez, plano aprovado antes de começar:

   - **Outbox de envio (Dexie) finalmente implementado** — `frontend/src/lib/db.ts` (tabela
     `lancamentoOutbox`), `outbox.ts` (`enfileirarCriarLancamento`/`enfileirarConfirmarLancamento`
     — só gravam local, nunca chamam `api`), `sync.ts` (`sincronizar()`, drena a fila em ordem,
     reentrância via flag `precisaNovaPassada` — sem isso uma segunda chamada durante uma
     drenagem em andamento era descartada em silêncio), `lancamento-outbox-view.ts`
     (`derivarLancamentoAtivo`, função pura que decide o que mostrar a partir só do outbox —
     **não depende do refetch da listagem da rodada**, porque esse refetch pode demorar mais que
     o sync e deixar a tela mostrando "nada" por um instante). `LancamentoFormPage.tsx` foi
     reescrito: clique em Registrar/Confirmar grava no Dexie (via `useLiveQuery` de
     `dexie-react-hooks`) e dispara `sincronizar()` em paralelo, nunca mais espera `api.POST`
     direto. `App.tsx` chama `useSincronizarOutbox()` (sync no mount + no evento `online` da
     janela). Conflito de negócio (409 `LANCAMENTO_JA_EXISTE`, 422 `LANCAMENTO_NAO_PENDENTE`) vira
     estado `CONFLITO`/`ERRO` no item da fila — mostrado num bloco vermelho na ficha, sem retry
     automático, sem sobrescrever nada; o árbitro precisa envolver a secretaria/coordenação.
     **Escopo explicitamente cortado pelo usuário**: só a fila de escrita. Cache de leitura
     offline (baixar ficha/rodadas/equipes/partidas antes da rodada) continua de fora — não é a
     seção 8 completa, é a metade que faltava resolvida.
   - **Seed agora deixa o ambiente pronto pra pontuar** — `backend/app/db/seed.py` ganhou
     `seed_arenas`/`seed_rodadas`/`seed_agendamentos` (reaproveitando os services de
     arena/rodada/agendamento, não duplicando lógica de bracket/agendamento), chamados em
     `_main()` depois de `seed_inscricoes`. As 4 modalidades `INDIVIDUAL` do seed passaram a
     definir `duracao_maxima_rodada_seg`/`pausa_entre_rodadas_seg` (antes ficavam `NULL`, o que
     derrubava a geração de horário com `422 DURACAO_RODADA_NAO_CONFIGURADA`). `make environment`
     em banco limpo agora entrega rodadas + arena + agendamento completo pra toda equipe inscrita,
     sem nenhum passo manual — validado rodando migration+seed do zero numa stack Docker isolada
     (projeto `docker compose -p` separado, sem tocar no banco de dev real) até criar um
     lançamento de verdade via API.
   - **Tela Pontuar (individual) não confunde "sem rodada" com "tudo completo"** —
     `PontuarPage.tsx` agora tem um terceiro estado vazio explícito (`rodadasOrdenadas.length ===
     0`) com aviso âmbar e link "Gerar rodadas →"; antes, zero rodadas caía no mesmo texto verde
     de "✓ todas já completaram".
   - **Árbitro não cai mais na área administrativa por padrão** — `EventoSelectPage` roteia
     árbitro pra `/eventos/:id/individual` ao clicar num evento (mesma convenção que
     `Header.tsx` já usava pros links do cabeçalho). O botão "Liberar/Ocultar ranking" em
     `ModalidadeListPage` ficou restrito a `ehCoordenador` (mesmo padrão dos outros controles da
     página) e `alternarRanking()` passou a mostrar erro na tela em vez de falhar em silêncio.
     **Decisão consciente**: a rota `/modalidades` em si **não** foi fechada com `ProtectedRoute
     papeisPermitidos` — SECRETARIA e ARBITRO têm leitura legítima ali por design (backend
     `_PAPEIS_LEITURA` inclui os dois pra GET, só escrita é `COORDENADOR`-only); fechar a rota
     inteira quebraria esse padrão já coberto por teste.
   - **Sessão renova sozinha** — `frontend/src/api/client.ts` chama `POST /api/v1/auth/refresh`
     no primeiro 401 (clonando a request original **antes** dela ser consumida pelo fetch real, e
     guardando o clone num `Map` por `id` da requisição, já que não dá pra clonar depois), repete
     a chamada original com o token novo, e só desloga se o refresh também falhar. Refreshes
     concorrentes (duas chamadas recebendo 401 ao mesmo tempo) dividem a mesma promise em voo, só
     um `POST /auth/refresh` sai. `createClient()` do `openapi-fetch` captura `globalThis.fetch`
     uma única vez na criação — por isso o client usa `fetch: (r) => globalThis.fetch(r)`
     (indireção, não a referência direta), senão nenhum teste conseguiria trocar o fetch global.
   - **Header não quebra mais em celular** — `gap-6` virou `flex-wrap gap-x-6 gap-y-2`; a
     navegação agora quebra linha em vez de forçar rolagem horizontal.
   - **Nome só com espaços é rejeitado** — `NomeObrigatorio` novo em
     `backend/app/schemas/common.py` (`Annotated[str, StringConstraints(strip_whitespace=True,
     min_length=1)]`), primeiro uso desse padrão no projeto (nenhum schema usava
     `field_validator`/`StringConstraints` antes), aplicado em equipe/evento/modalidade/arena/
     usuário. Frontend: `.trim()` adicionado nos schemas zod de `EquipeListPage` e
     `EventoSelectPage`.
   - **Dependências**: `bcrypt` fixado em `<4.1` no `pyproject.toml` (passlib 1.7.4, sem release
     desde 2020, sonda `bcrypt.__about__`, removido no bcrypt 4.1+ — gerava
     `AttributeError` a cada hash/verificação de senha, sem quebrar o login mas poluindo os logs).
     `react-router-dom` atualizado de `^6.26.2` pra `7.18.2` (a série 6.x inteira tem as duas
     CVEs do `npm audit`, não existe patch 6.x — só 7.18+; upgrade major mas de baixo risco pro
     uso deste projeto, API clássica `BrowserRouter`/`Routes`/`Route`, sem o modo "framework" do
     v7; confirmado com suíte completa + `npm run build` depois do bump).
   - **Pegadinha de Docker**: pacote instalado via `docker compose exec <serviço> npm install
     ...` só grava no filesystem efêmero do container (ou no volume anônimo de `node_modules`)
     daquele momento — **não fica na imagem**. Depois de qualquer `npm install`/`pip install`
     assim durante uma sessão, é preciso `docker compose build <serviço>` e, se o volume anônimo
     de `node_modules` sobrepuser o node_modules novo da imagem ao recriar, `docker compose rm
     -fsv <serviço>` (o `-v` remove o volume anônimo) antes de `up -d` de novo — só rodar os
     testes dentro do container já quente não garante que a mudança sobreviva a um restart.

   **Sessão de redirecionamento de escopo pro TJR 2026** (21/08/2026). Com o tempo curto pra
   virada, decisão consciente do usuário: parar de modelar pensando em reaproveitar o sistema
   pra outras instâncias/competições futuras e focar só nas modalidades já existentes do
   evento atual — sem fechar a porta (abas, modelo de dados e a estrutura de `modalidade`/
   `ficha` seguem genéricas), só sem investir tempo extra em generalização que não vai ser
   usada agora. Quatro entregas:

   - **`formato_chaveamento` trava depois que a modalidade tem rodada criada** —
     `atualizar_modalidade` (`services/modalidade.py`) recusa com `422
     FORMATO_CHAVEAMENTO_TRAVADO` se o valor mudar e já existir `Rodada` pra aquela modalidade.
     Motivado por caso real de confronto (Cabo de Guerra, Sumô, Corrida de Carros Autônomos):
     coordenador escolhe mata-mata ou todos-contra-todos, e trocar no meio da competição
     bagunça a leitura de classificação (`consolidacao.py` decide o cálculo pelo campo).
   - **Reset de chaveamento** (`resetar_chaveamento` em `services/chaveamento.py`, rota `POST
     /modalidades/{id}/chaveamento/reset`, só `COORDENADOR`, exige `justificativa`) — via de
     escape do item acima: apaga de verdade rodada/partida/lançamento/item daquela modalidade e
     libera trocar o formato e gerar chaveamento do zero. **Exceção deliberada à regra
     inviolável 5** ("nada de DELETE em dado de pontuação"), decidida explicitamente com o
     usuário depois de confirmar que ele queria desfazer de verdade (não só corrigir/anular) um
     caso em que o árbitro rodou o formato errado. Antes de apagar, grava um snapshot completo
     (`_dump`, via `inspect(obj).mapper.column_attrs` + `json.dumps(default=str)`) no
     `audit_log` como `acao="RESET_CHAVEAMENTO"` — o rastro sobrevive mesmo sem as linhas
     originais, só que fora das tabelas de pontuação. Front: botão vermelho "Resetar
     chaveamento" em `ChaveamentoPage.tsx`, só pra coordenador, com modal de confirmação que
     exige justificativa preenchida antes de habilitar o envio.
   - **Aba "Ranking" tirada do Painel interno** (`PainelPage.tsx`) — investigação mostrou que
     não existe nenhum link de navegação pro ranking público hoje (só URL direta), então não
     tinha o que esconder ali; o único lugar do sistema com link de fato pra visualização de
     ranking era essa aba do painel staff. Removida temporariamente (reversível — a aba e o
     componente `RankingClassificacao` continuam existindo, só desconectados), decisão do
     coordenador: tempo curto, ranking ainda não está pronto pra mostrar nem pro staff.
   - **Relatório de auditoria em PDF** — `services/relatorio.py`
     (`gerar_relatorio_auditoria_pdf`, nova dependência `reportlab`) monta, por modalidade, a
     classificação completa (reaproveita `consolidacao.calcular_classificacao`, mesma fonte do
     `RankingOut`) e todos os lançamentos com seus itens (rodada, tentativa, status, total,
     árbitro, critério a critério) — pensado pra equipe contestar resultado e a secretaria
     conferir na mão. Rota `GET /ranking/modalidades/{id}/relatorio-auditoria.pdf`, mesmo grupo
     de papéis que já vê ranking não liberado (`COORDENADOR`/`ARBITRO`/`SECRETARIA`). Front:
     botão "Baixar relatório (PDF)" em `ModalidadeListPage.tsx`, ao lado de
     "Liberar/Ocultar ranking", usando `parseAs: "blob"` do `openapi-fetch` +
     `URL.createObjectURL` (primeiro download binário do projeto — sem precedente de
     `parseAs`/blob antes desta sessão).

   Fichas específicas de Cabo de Guerra/Sumô/Corrida de Carros Autônomos (o seed já cria essas
   três modalidades, `db/seed.py`, hoje com uma ficha genérica `_FICHA_RESULTADO_COMBATE`
   compartilhada) ficaram de fora desta sessão — o usuário vai detalhar critério a critério no
   `HISTORIAS.md`, tarefa separada.

   **Fichas reais de Cabo de Guerra/Sumô/Corrida de Carros Autônomos** (mesma sessão, depois de
   comparar `HISTORIAS.md` com as fichas oficiais em PDF na pasta `FICHAS-DE-PONTUAÇÃO/` — achou
   3 divergências reais entre o texto e o PDF, perguntado e resolvido antes de implementar):
   - **Cabo de Guerra e Sumô: `tentativas_por_rodada=2`**, não 3 (a ficha oficial só tem Round 1
     e Round 2). O combate extra de desempate ("ponto de ouro", seção 6) cobre o caso de empate
     em `MATA_MATA` sem precisar de um 3º round fixo. `_FICHA_CABO_DE_GUERRA`/`_FICHA_SUMO`
     (`db/seed.py`) viraram 1 único critério `ESCALA` cada — `"Resultado do arrasto"` (Cabo de
     Guerra) e `"Resultado do combate"` (Sumô), `valores_permitidos=[0, 1, 2]` — pra caber no
     fluxo rápido de 1 clique do `PartidaScorerPage` (ficha com mais de 1 critério cai no
     formulário genérico). Decisão consciente: **Empate (+1 pra cada) e Nulo (0 pra cada) da
     ficha oficial do Cabo de Guerra viram o mesmo "Empate" no sistema** — pro resultado do round
     dá no mesmo (ninguém vence), e distinguir os dois exigiria sair do fluxo de 1 clique. Rótulo
     de `ESCALA` por nome de critério em `ROTULOS_ESCALA` (`PartidaScorerPage.tsx`): Cabo de
     Guerra já existia (`1 = "Arrasto parcial", 2 = "Arrasto pro fosso"`, de uma sessão anterior
     de teste manual), Sumô novo (`1 = "Waza-ari", 2 = "Ippon"`).
   - **Corrida de Carros Autônomos: `tentativas_por_rodada=3` sempre**, pra toda partida —
     simplificação deliberada da ficha oficial (que só exige 1 corrida eliminatória em partida
     normal, e só a Final sempre roda 2 corridas + 3ª de desempate). Implementar o "só a Final
     tem número de corridas diferente" exigiria `tentativas_por_rodada` variar por partida
     dentro da mesma modalidade, coisa que o modelo atual não suporta (é um campo fixo por
     modalidade) — trabalho de modelagem novo, fora de escopo por ora. Nível da modalidade
     confirmado como normal (separado por nível como as demais, mesmo a ficha oficial mostrando
     "NÍVEL: ÚNICO" — era só o valor de exemplo preenchido no modelo).

     `_FICHA_CORRIDA_DE_CARROS` (`db/seed.py`) **inicialmente** virou 1 critério `BOOLEANO`
     (`"Venceu a corrida"`) pra caber no fluxo rápido de 1 clique — mas ao testar ao vivo (depois
     de zerar e resemear o banco de dev, seção seguinte) o usuário viu que faltavam as opções
     reais da ficha (Evitar a colisão, as 4 violações, Carro que ficou na frente) e pediu o
     detalhamento de volta, mesmo saindo do fluxo rápido. Ficha final com 6 critérios num grupo
     só ("Eventos da corrida"): `"Evitar a colisão"` (`CONTADOR`, `PONTUACAO`, +1 por vez, sem
     `max_ocorrencias`); `"Colisão com a parte traseira do outro"`, `"Evasão da pista"`,
     `"Posicionamento transversal"`, `"Percurso em sentido contrário"` (todos `BOOLEANO`,
     `PENALIDADE`, -1 cada — só registro, o árbitro que decide o vencedor observando a
     jurisprudência já impressa na ficha oficial); `"Carro que ficou na frente"` (`BOOLEANO`,
     `PONTUACAO`, **+10** — de propósito bem acima da soma de todas as penalidades e de qualquer
     acúmulo razoável de "Evitar a colisão", pra garantir que quem o árbitro marcar como vencedor
     sempre tenha o total maior na comparação de tentativa que decide a partida, mesmo que o
     carro perdedor tenha marcado "Evitar a colisão" várias vezes). Com >1 critério, essa
     modalidade cai no formulário genérico de ficha (`LancamentoFormPage`), não no
     `PartidaScorerPage` de 1 clique — trade-off aceito conscientemente pela riqueza de dado pro
     relatório de auditoria.

   **`PartidaScorerPage` ganhou um scorer inline pra ficha com vários critérios BOOLEANO/CONTADOR**
   (motivado pela Corrida de Carros Autônomos, mas genérico por `tipo` de critério, não hard-coded
   por nome/modalidade — qualquer ficha de combate futura nesse formato ganha o mesmo tratamento
   de graça). Antes, ficha com mais de 1 critério caía direto no link "Lançar pela ficha completa"
   pro `LancamentoFormPage` genérico (selecionar equipe uma de cada vez, formulário abstrato). O
   usuário testou ao vivo e pediu layout organizado por equipe com botão selecionável, sem sair da
   tela — `suportaScorerInline(criterios)` (`PartidaScorerPage.tsx`) libera o novo
   `MultiCriterioScorer` quando **todos** os critérios da ficha são `BOOLEANO` ou `CONTADOR`
   (`ESCALA`/`MODIFICADOR` misturado ainda cai no link de fallback, sem suporte inline ainda).
   Componente mostra duas colunas (Equipe A / Equipe B), botão toggle pra cada critério `BOOLEANO`
   (`aria-pressed`) e contador +/− pra cada `CONTADOR` (respeita `max_ocorrencias`), acumulando
   estado local por lado até o árbitro clicar "Registrar" — que envia os dois lançamentos de uma
   vez via `enviarCombate` (mesma função já usada pelos fluxos BOOLEANO/ESCALA de 1 critério, com
   outbox/idempotência/auto-navegação quando a partida decide). **Achado de bug corrigido no
   caminho**: a primeira versão definia o componente de coluna (`ColunaEquipe`) *dentro* do corpo
   de `MultiCriterioScorer` — como toda função aninhada tem identidade nova a cada render, o React
   desmontava/remontava a subárvore inteira a cada clique, e o segundo clique em sequência (ex.:
   "+1" duas vezes) caía num nó DOM já destacado, perdendo o efeito. Corrigido subindo o
   componente de coluna (`ColunaEquipeMultiCriterio`) pro nível de módulo — mesmo padrão que
   `ColunaRodada` já usa em `ChaveamentoPage.tsx`. Lição: **nunca declarar componente dentro do
   corpo de outro componente** neste projeto, sempre no nível de módulo, mesmo quando parece
   "só uma função auxiliar local".

   **Ajustes visuais no `MultiCriterioScorer` depois do usuário testar ao vivo**: colunas lado a
   lado (`grid grid-cols-2`) com as opções empilhadas dentro de cada coluna (`flex-col`, antes era
   `flex-wrap`); cor por `categoria` do critério (`corCriterio`, novo campo `categoria` em
   `CriterioItem`) — verde (`PONTUACAO`) pro que faz a equipe ganhar, vermelho (`PENALIDADE`) pro
   que faz perder, já visível na borda em repouso (não só no hover, pra funcionar em touch);
   **exclusividade entre equipes pra critério `BOOLEANO`** — marcar um critério (ex.: "Carro que
   ficou na frente") pra uma equipe desmarca automaticamente o mesmo da outra, já que fisicamente
   as duas não podem "ganhar" o mesmo evento ao mesmo tempo. `CONTADOR` ("Evitar a colisão") fica
   de fora dessa regra por construção — cada lado usa seu próprio contador independente
   (`alterar`), só `BOOLEANO` passa por `alternar`, que agora zera o lado oposto ao ligar.

   **Bug real de decisão de partida corrigido — `Modalidade.decisao_partida`** (achado ao vivo:
   usuário marcou "Arrasto pro fosso" pra uma equipe num round e "Arrasto parcial" pra outra num
   outro round, cada equipe venceu 1 round, e o sistema fechou a partida como empate). Causa: a
   regra inviolável 6 original ("vencedor da partida = quem ganha mais combates individuais, não
   quem soma mais pontos") é adequada pra Corrida de Carros (melhor-de-3 corridas, tipo tênis),
   mas **não é o que Cabo de Guerra/Sumô precisam** — ali cada round vale um número de pontos
   diferente (Fosso=2, Arraste Parcial=1 / Ippon=2, Waza-ari=1) e isso tem que se acumular pra
   decidir quem vence, não só contar quantos rounds cada lado ganhou. Confirmado com o usuário
   antes de mexer (regra 6 é inviolável, exigia parar e perguntar) que a soma é o comportamento
   correto pra essas duas modalidades especificamente.

   Solução: novo campo `Modalidade.decisao_partida` (enum `DecisaoPartida`:
   `COMBATES_VENCIDOS` default / `SOMA_PONTOS`, migration `353d40a6fcc5`). Em
   `services/chaveamento.py::registrar_resultado_lancamento`, o cálculo de quem vence a partida
   agora bifurca por esse campo — `vitorias_a/vitorias_b` (contagem, comportamento antigo
   preservado pra tudo que não configurar o contrário) vs `soma_a/soma_b` (soma dos `total` de
   cada tentativa confirmada). O combate extra de desempate ("ponto de ouro", só `MATA_MATA`)
   segue existindo nos dois modos: em `COMBATES_VENCIDOS` ele soma +1 vitória pra quem tiver mais
   pontos nesse combate extra; em `SOMA_PONTOS` ele soma o total do combate extra na soma
   corrente de cada lado (sem reescrever os combates anteriores, mesmo espírito de antes). Seed:
   Cabo de Guerra e Sumô ganharam `decisao_partida=SOMA_PONTOS`; Corrida de Carros Autônomos
   ficou no default (`COMBATES_VENCIDOS` — decisão correta pra ela: normal ou melhor-de-3 por
   corrida, contar corridas vencidas é o que já reflete o "quem chega na frente primeiro na
   maioria das vezes" real).

   Front (`PartidaScorerPage.tsx`) também precisou saber do modo: o cálculo de "empate técnico"
   (que decide se libera o banner + o card do combate extra) era só por contagem de vitórias,
   independente do que o backend ia realmente decidir. Provado por álgebra que, com exatamente 2
   tentativas (config atual de Cabo de Guerra/Sumô), empate na soma sempre implica empate na
   contagem — mas isso é coincidência de N=2, não vale em geral pra N≥3 (testado no front com um
   cenário de 3 combates pra provar a divergência: contagem 2-1 mas soma empatada 2-2).
   Corrigido pra sempre bater com o backend em qualquer N: soma quando
   `modalidade.decisao_partida === "SOMA_PONTOS"`, contagem senão. Texto do banner também virou
   condicional ("Empate na soma dos pontos" vs "Empate na contagem de combates").

   **Reset do banco de dev depois de mudar ficha de modalidade já seedada**: como
   `_obter_ou_criar_ficha` (`db/seed.py`) é idempotente por design (não sobrescreve ficha
   publicada existente), rodar `python -m app.db.seed` de novo **não** troca a ficha de uma
   modalidade que já tinha sido seedada antes com o formato antigo — só cria o que ainda não
   existe. Depois de trocar o conteúdo de `FICHAS_TJR`/`MODALIDADES_TJR` no código, quem já tinha
   rodado o seed antes precisa: (a) sem lançamento nenhum na ficha antiga — apagar direto
   `criterio`/`grupo`/`ficha` daquela modalidade (nessa ordem, sem `ondelete=` cascata) e rodar o
   seed de novo; ou (b) já tem lançamento de teste em cima — mais simples zerar o banco `tjr`
   inteiro (`DROP DATABASE`/`CREATE DATABASE`, sem mexer no `tjr_test` dos testes automatizados)
   e rodar `alembic upgrade head` + `python -m app.db.seed` do zero. Achado ao vivo: o dev tinha
   um evento avulso "debug" (05/08) e o evento "TJR 2026" com as 3 modalidades de combate já
   seedadas com a ficha genérica antiga (`"Venceu o combate"`) e rodadas/partidas/lançamentos de
   teste em cima — resolvido com reset completo (opção b).

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