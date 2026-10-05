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
- Vencedor de partida é sempre automático (compara os combates). **Chaveamento, não** — desde
  out/2026 todo confronto é montado na mão pelo coordenador (`criar_partida_manual`: rodada +
  tipo "Fase de grupos"/`TODOS_CONTRA_TODOS`, aceita empate, ou "Eliminatória"/`MATA_MATA`, empate
  vai pro ponto de ouro, aceita bye). O sistema não gera chaveamento, não gera round-robin, não gera
  fase de grupos e não avança rodada sozinho — semifinal/final também são criadas à mão. Ver
  seção 12.

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

~~10. Modalidade INDIVIDUAL: nenhum lançamento sem arena atribuída.~~ **Removida em 28/08/2026**
(véspera do TJR 2026), pedido direto do coordenador — na prática as arenas de uma modalidade são
fisicamente equivalentes no ginásio real, então a trava só bloqueava o card de pontuar sem
carregar informação útil nenhuma. `criar_lancamento` não exige mais `Agendamento` pra
INDIVIDUAL; `PontuarPage.tsx` mostra arena/horário como informação extra quando existir, nunca
mais como pré-requisito. Ver histórico na seção 12. Não reintroduzir sem pedido explícito.

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

   **Estimativa de horário previsto (história 5 do `HISTORIAS.md`)** (22/08/2026). Antes de
   implementar, conferiu-se as 4 fichas de modalidade individual (Dança, Resgate no Plano,
   Resgate de Alto Risco, Viagem ao Centro da Terra) contra os PDFs oficiais em
   `FICHAS-DE-PONTUAÇÃO/Individuais/` — já batiam 100%, nada pra corrigir (ficaram certas desde
   que foram escritas, mesmo sem terem passado pela sessão de conferência que pegou os 3 erros
   de combate). O relatório de auditoria em PDF também já era genérico por `tipo_disputa`, sem
   trabalho extra pra individual. Sobrou só o critério de aceite de horário, que era ambíguo e
   foi fechado com o usuário antes de codar: gatilho = confirmação de lançamento (não relógio),
   exibição = só o horário previsto recalculado, **sem** badge/aviso de atraso, e o efeito
   **cascateia** pras próximas rodadas da modalidade (não fica preso só na rodada em andamento).

   `services/agendamento.py::estimar_horarios` (nova função, sem migration — tudo calculado on
   the fly, não persiste em `Agendamento.horario_inicio`, que continua sendo o horário
   oficialmente gerado): por modalidade, percorre as rodadas com agendamento em ordem de
   `numero`; por arena, anda a fila (`ordem_na_arena`) mantendo um "horário corrente" e um
   "ritmo" (`pace_por_arena`, em segundos, começa em `duracao_maxima_rodada_seg` e é
   **substituído** pelo intervalo real observado assim que duas confirmações consecutivas
   existirem naquela arena — não é média histórica, é o último intervalo real observado, reage
   rápido a arena acelerando/atrasando). Pra cada agendamento da fila: se a equipe já tem
   `lancamento` `CONFIRMADO` naquela rodada (usa `max(atualizado_em)` entre os confirmados —
   cobre o caso de mais de uma tentativa por rodada, tipo "1º cubo"/"2º cubo" da Viagem, sem
   precisar saber quantas tentativas a modalidade espera), o horário corrente vira esse horário
   real e **não entra no resultado** (já aconteceu, não há "previsto" a mostrar — só bateria
   pendente aparece na resposta). Se não tem confirmação, previsto = horário corrente + ritmo da
   arena, e isso vira o novo horário corrente pra próxima da fila. Fim de rodada = maior horário
   corrente entre as arenas + `pausa_entre_rodadas_seg`, que vira o início estimado da próxima
   rodada — mesma fórmula de `gerar_agendamentos`, só que alimentada por dado real em vez do
   grid uniforme teórico. Sem nenhuma confirmação ainda, a função devolve exatamente o mesmo
   grid que `gerar_agendamentos` gerou (sanity check coberto por teste). Rota
   `GET /agendamentos/estimativa?modalidade_id=`, mesmo grupo de leitura de
   `GET /agendamentos` (`COORDENADOR`/`ARBITRO`/`SECRETARIA`).

   Front: `HorarioPage.tsx` busca a estimativa em paralelo (`refetchInterval: 30_000`, pra
   atualizar sozinha enquanto a tela fica aberta no dia da competição) e troca o valor exibido
   pelo previsto quando existe entrada pra aquele `agendamento.id`, caindo de volta pro
   `horario_inicio` original quando não existe (bateria já confirmada, ou estimativa ainda não
   carregou) — nenhum texto/cor de atraso em lugar nenhum, só o número muda, exatamente como
   pedido. Verificado ao vivo (não só suíte automatizada): confirmado um lançamento de teste via
   API pra "Resgate no Plano" no ambiente de dev, e a aba Horários no navegador mostrou a equipe
   confirmada mantendo o horário original enquanto as próximas da fila reprojetaram pro horário
   real de confirmação + 3min (duração da rodada daquela modalidade no seed) — sem nenhum aviso
   de atraso na tela.

   **Sessão de redução de escopo pro dia real da competição** (22/08/2026) — cinco pedidos
   independentes do coordenador, todos implementados em TDD e verificados ao vivo no navegador:

   - **Evento único** — `services/evento.py::criar_evento` recusa com `422
     EVENTO_UNICO_JA_EXISTE` se já existir qualquer `Evento` no banco (checagem simples de
     `count()`, sem flag nem config — o sistema nunca vai precisar rodar dois eventos ao mesmo
     tempo). Front: `EventoSelectPage.tsx` perdeu o formulário "Criar novo evento" inteiro (react-
     hook-form + zod + mutation), pra todo mundo, não só pra quem não é coordenador — a tela virou
     puramente uma lista com link pro evento existente. Testes que criavam 2+ eventos via
     `POST /eventos`/`criar_evento` num mesmo teste (pagination, filtro de modalidade por
     `evento_id`) precisaram trocar pra inserção direta via model (`db.add(Evento(...))`), já que
     o segundo `POST` real passou a ser rejeitado — documentado inline em cada teste.
   - **Relatório de auditoria em PDF, geral por evento** — `relatorio.py` foi refatorado sem mudar
     o output do relatório por modalidade existente: extraiu `_carregar_dados_modalidade` (busca
     crua) e `_montar_secao_modalidade` (monta os flowables de classificação+lançamentos de uma
     modalidade) do meio de `gerar_relatorio_auditoria_pdf`, e a nova
     `gerar_relatorio_auditoria_evento_pdf` chama as duas por modalidade do evento (ordenadas por
     nome), separadas por `PageBreak()`. Rota nova `GET
     /ranking/eventos/{evento_id}/relatorio-auditoria.pdf`, mesmo grupo de papéis
     (`COORDENADOR`/`ARBITRO`/`SECRETARIA`) da rota por modalidade — que continua existindo (não
     foi removida, só parou de ter botão no front). `ModalidadeListPage.tsx`: botão "Baixar
     relatório (PDF)" por linha de modalidade virou um único "Baixar relatório geral (PDF)" no
     cabeçalho da página (ao lado de "Nova modalidade"), usando `evento_id` da URL.
   - **Rodadas da Dança: 2, somando as duas** — `db/seed.py` mudou `Dança` de `qtd_rodadas=3` +
     `Consolidacao.IGNORA_MENOR_NOTA` pra `qtd_rodadas=2` + `Consolidacao.SOMA_RODADAS` (decisão
     tomada via pergunta direta ao usuário, porque o pedido original leu de um jeito
     autocontraditório — "3 rodadas, exceção a Dança que tem 2... pode deixar só com 1"). As
     outras 3 modalidades individuais (Resgate no Plano, Resgate de Alto Risco, Viagem) já
     estavam em `qtd_rodadas=3`, sem mudança. Nenhum teste quebrou porque as asserções de
     `test_seed.py` já liam `modalidade.qtd_rodadas` dinamicamente, nunca hard-codado.
   - **Ranking fica em segredo — botão de liberar removido** — `ModalidadeListPage.tsx` perdeu o
     botão "Liberar/Ocultar ranking" (e a função `alternarRanking`) de vez, não só escondido; o
     campo `ranking_liberado` nem é mais buscado pelo componente. Backend intocado de propósito
     (endpoint `PATCH /modalidades/{id}` com `ranking_liberado` continua existindo, só sem UI pra
     acioná-lo) — reversível se for reaberto depois, mesmo padrão já usado quando a aba Ranking
     saiu do Painel numa sessão anterior. Nenhuma modalidade do seed nasce com
     `ranking_liberado=true`, então a remoção do botão já é suficiente pra "manter em segredo" —
     não precisou mexer na rota pública de ranking.
   - **Cards de combate no Painel viraram "quem jogou contra quem, quem ganhou"** — antes, cada
     lançamento (uma ficha = um lado de um combate) tinha seu próprio card genérico com a grade
     "Pontuados/Não pontuados/Penalidades/Modificadores" (`CardSubmissao`, pensado pra modalidade
     individual, onde 1 lançamento = 1 apresentação inteira). Pra confronto, isso mostrava dois
     cards separados, cada um só com o critério cru daquele lado — ruim de ler quem venceu.
     `LancamentoAuditoriaOut` (schema) e `listar_lancamentos_auditoria` (service) ganharam o campo
     `partida_id` (só preenchido pra lançamento de modalidade `CONFRONTO`, `None` pra
     `INDIVIDUAL`). Front: `ListaSubmissoes.tsx` ganhou `agruparPorCombate` — separa a lista crua
     da API em lançamentos individuais (seguem indo pro `CardSubmissao` de sempre) e grupos por
     `partida_id + tentativa` (até 2 lançamentos, os dois lados do mesmo combate), renderizados
     pelo novo `CardCombate`: nome da modalidade/nível/rodada/tentativa, e cada lado num bloco
     lado a lado mostrando só a equipe e o total — o lado com total maior ganha um "Vencedor" em
     verde, iguais viram "Empate", e falta um lado ainda mostra "Aguardando a equipe adversária"
     em vez de travar esperando os dois. Decisão de design: "vencedor" aqui é sempre por
     comparação direta de `total` entre os dois lançamentos daquele combate específico — não
     reaproveita `Modalidade.decisao_partida` (`COMBATES_VENCIDOS`/`SOMA_PONTOS`) porque esse
     campo decide quem vence a *partida inteira* (view de `PartidaScorerPage`/`chaveamento.py`),
     enquanto aqui a granularidade é *um combate* (uma tentativa) — comparar total bate com os
     dois modos na prática (`SOMA_PONTOS` soma o total do combate diretamente; `COMBATES_VENCIDOS`
     não tem uma pontuação "errada" pra inverter numa ficha de 1 critério ESCALA/BOOLEANO só).

   **Sessão seguinte, dois ajustes rápidos no que acabou de sair** (22/08/2026):

   - **PDF de auditoria: confronto explícito** — `relatorio.py` ganhou `agrupar_lancamentos_por_combate`
     (mesma ideia do `agruparPorCombate` do front, mas do lado do PDF: agrupa as linhas
     `(Lancamento, Rodada, Equipe, Usuario)` por `partida_id + tentativa`, item individual fica
     sozinho no próprio grupo) e `descrever_resultado_combate` (placar + "Vencedor: X" ou
     "Empate"). A seção "Lançamentos" do relatório passou a imprimir, antes dos dois lados de um
     combate, uma linha em negrito tipo `Confronto — Rodada 1 · Tentativa 1: Equipe A 0 x 1
     Equipe D — Vencedor: Equipe D`, com o detalhe de critério por critério de cada lado embaixo,
     inalterado — ao contrário da simplificação da sessão anterior no Painel, aqui o pedido foi só
     **acrescentar** explicitação, não remover detalhe (PDF de auditoria continua precisando do
     critério a critério pra contestação). Verificado extraindo texto de verdade do PDF gerado
     (`pdftotext -layout`, já que o conteúdo dos streams do reportlab vem comprimido/glyph-index e
     não dá pra conferir com `grep`/`strings` cru) contra um cenário real do Cabo de Guerra.
   - **Navegação: "Individual" e "Combates" viraram abas dentro de uma `CompeticoesPage` só**
     (`/eventos/:eventoId/competicoes`, substituindo as duas rotas separadas `/individual` e
     `/combates`). Mesmo padrão de tablist raiz (`?aba=individual|combate`) usado em
     `PainelPage`/`IndividualHubPage`/`ConfrontoHubPage`. `IndividualHubPage` e `ConfrontoHubPage`
     continuam existindo como componentes — mesmo tratamento já dado antes a
     `PontuarDashboardPage`/`RodadaDashboardPage`/etc: perderam o `<main>`/`<h1>` próprio, agora só
     renderizam como conteúdo da aba dentro do hub novo. Isso criou uma colisão de nome: as duas
     hub pages já liam sua **própria** aba interna (Pontuar/Rodadas/Horários e
     Modalidades/Chaveamento) do parâmetro `?aba=`, que agora também é usado pela aba **externa**
     (Individual/Combate) na mesma URL — resolvido renomeando o parâmetro interno das duas hub
     pages pra `?sub=` (`aba` = nível de cima, `sub` = nível de baixo). Todo link que apontava pra
     `/individual?aba=X` ou `/combates` direto (botão "Voltar" de `PontuarPage`/`HorarioPage`,
     `PontuarCombatePage`, `Header`, redirecionamento de árbitro em `EventoSelectPage`) foi
     atualizado pra `/competicoes?aba=individual&sub=X` ou `/competicoes?aba=combate`. Header
     perdeu os dois links soltos "Individual"/"Combates" e ganhou um só "Competições". Decisão
     consciente de manter o redirecionamento do coordenador ao clicar num evento como estava (vai
     pra `/modalidades`, área administrativa) — só o destino do **árbitro** (que já ia direto pro
     fluxo operacional) trocou de `/individual` pra `/competicoes`, porque foi o único caso citado
     no pedido. Verificado ao vivo no navegador: header mostra só "Competições", clicar leva pra
     `/competicoes` com aba Individual selecionada por padrão (Pontuar/Rodadas/Horários das 4
     modalidades individuais do seed, cada uma com link "Pontuar" direto), aba Combate mostra as
     3 modalidades de confronto com "Pontuar"/"Ver rodadas" cada.

     **Correção na mesma sessão**: o usuário pediu que clicar no evento também mandasse o
     coordenador pra `/competicoes` (não só o árbitro) — `destinoDoEvento` em
     `EventoSelectPage.tsx` perdeu de vez a bifurcação por papel, agora é sempre
     `/eventos/:id/competicoes` pra qualquer usuário logado. Área administrativa
     (Modalidades/Fichas/Equipes) continua alcançável, só que agora exclusivamente pelo Header,
     não mais como destino padrão do clique no evento.

   **Sessão de deploy "como se fosse prod"** (22/08/2026, motivada por o usuário querer testar
   pelo celular e pedir pra "organizar já como se fosse pra produção, já que estamos
   finalizando"). `docker-compose.yml` original só tinha modo dev: `front` rodando `vite dev`
   direto no container, com `VITE_API_URL` fixo em `http://localhost:8000` — funciona no navegador
   da própria máquina, mas quebra de qualquer outro dispositivo na rede (o valor fixo não existe
   fora dela). Resolvido implementando de vez o `front/nginx` que a seção 2 (Stack) já citava
   como arquitetura pretendida, mas nunca tinha sido feito:

   - **`frontend/Dockerfile` virou multi-stage**: `dev` (o que já existia, `npm run dev`, usado
     pelo `docker-compose.yml` normal via `build.target: dev`), `build` (`npm run build`, estágio
     intermediário só pra gerar o bundle) e `prod` (`nginx:alpine` servindo o bundle +
     `frontend/nginx.conf` fazendo proxy reverso de `/api/` pro container `api` — client e API na
     **mesma origem**, então não existe mais `VITE_API_URL` fixo em lugar nenhum. Funciona em
     qualquer IP/host sem configuração alguma, porque não tem host nenhum hardcoded).
   - **`docker-compose.prod.yml`** — override (não arquivo standalone) rodado junto com o
     `docker-compose.yml` normal (`docker compose -f docker-compose.yml -f
     docker-compose.prod.yml up -d --build`, ou `make up-prod`): mesmo projeto/volume de banco
     (não duplica dado ao alternar entre dev e prod na mesma máquina). Usa as tags de merge
     `!reset`/`!override` do Compose Specification (suportado desde Docker Compose 2.24, versão
     instalada aqui é 5.5.0) — necessário porque `ports`/`volumes` fazem merge por concatenação
     entre arquivos por padrão, não substituição; sem a tag, a porta antiga continuava vazando
     junto com a nova. `db`/`api` perdem porta publicada pro host (só alcançáveis um pelo outro,
     dentro da rede docker); `api` roda sem `--reload` e sem bind mount do código do host (só o
     que foi buildado na imagem); `front` fica com a única porta pública (80).
   - **Achado ao rodar de verdade** (só apareceu testando, não em code review): com
     `VITE_API_URL` ausente, o fallback óbvio "`?? \"\"`" (string vazia = caminho relativo) quebra
     o `openapi-fetch` em qualquer chamada que precise montar um `new URL(...)` internamente (ex.:
     serialização de query string) — `new URL()` de uma string relativa sem base lança
     `TypeError: Invalid URL`. Sintoma enganoso: chamada sem query string (o POST de login, sem
     parâmetro nenhum) funcionava normal, escondendo o problema até testar uma tela com paginação
     de verdade. Corrigido usando `window.location.origin` como fallback em vez de string vazia
     em `frontend/src/api/client.ts` — sempre uma URL absoluta válida, mesmo efeito de "mesma
     origem da página" sem o caminho relativo cru. Pego pelos testes automatizados
     (`client.test.ts`), não só pela verificação manual.
   - **`JWT_SECRET_KEY` do `.env`** trocado de `troque-esta-chave-em-producao` (literalmente um
     placeholder pedindo pra ser trocado) pra uma chave aleatória de 32 bytes
     (`secrets.token_hex(32)`). Efeito colateral esperado e aceito: invalida qualquer sessão
     logada antes da troca (precisa logar de novo). **Decisão consciente de não mexer** na senha
     do coordenador seed (`SEED_COORDENADOR_SENHA`) nem na senha do Postgres
     (`POSTGRES_PASSWORD`, hoje `tjr` fixo em `docker-compose.yml`) — ao contrário da chave JWT
     (troca invisível, só desloga sessão), essas são credenciais que o time já está usando
     ativamente pra logar/conectar; trocar sem avisar quebraria acesso em uso. Documentado no
     README como pendência pra antes de expor numa rede que não seja só o time de confiança.
   - Verificado de ponta a ponta simulando acesso de celular de verdade: Chromium headless
     batendo em `http://192.168.1.11` (IP da rede local, não `localhost`) — login, clique no
     evento, navegação até Competições e até uma tela com paginação (`/equipes`, que exercita o
     código de query string que achou o bug acima) sem nenhum erro de console nem request
     falhando. Suíte completa (backend 450 + frontend 329) verde depois da correção do
     `client.ts`; a suíte frontend rodou via uma imagem `dev`-target avulsa, já que o container
     `front` rodando em modo prod é `nginx:alpine` (sem node, não dá pra rodar vitest nele
     diretamente).

   **Dois achados do primeiro uso real em campo** (mesmo dia, usuário testando pelo celular de
   verdade contra o `http://192.168.1.11` que a sessão anterior deixou no ar):

   - **Colisão de tag de imagem Docker entre dev e prod** — `docker-compose.yml` e
     `docker-compose.prod.yml` deixavam o `front` sem `image:` explícito, então os dois caíam no
     mesmo nome derivado por padrão (`tjr-front`), mesmo apontando pra estágios diferentes do
     Dockerfile (`dev` = node/vite, `prod` = nginx). Sintoma real: em algum momento entre uma
     mensagem e outra, alguém/algo rodou um `docker compose up` sem `-f docker-compose.prod.yml`
     (provavelmente sem querer) — isso recriou os containers com a config de **portas** de dev
     (5173) só que reaproveitando a imagem `tjr-front` que por acaso era a de **prod** (nginx,
     buildada por último) porque não tinha `--build`; resultado: `front-1` de pé mas mudo (nginx
     não escuta em 5173, e a porta 80 não estava mais publicada) — daí o "this site can't be
     reached" do celular. Corrigido dando nome de imagem próprio pra cada um
     (`image: tjr-front-dev` / `image: tjr-front-prod`), então de agora em diante um rebuild de
     um nunca mais pisa na tag do outro. **Não resolvido** (decisão consciente, não bug): os dois
     ainda usam o mesmo nome de *serviço* (`front`) no mesmo projeto compose, então rodar
     `docker compose up`/`make up` (dev) enquanto o prod está no ar ainda **substitui** o
     container de produção pelo de dev — a alternativa (projeto/nome separado pra prod) faria
     dev e prod terem bancos diferentes, o que é pior. Recado prático: não rodar `make up` /
     `docker compose up` sem o `-f docker-compose.prod.yml` enquanto o ambiente publicado
     estiver valendo pra alguém de verdade.
   - **`crypto.randomUUID()` não existe fora de contexto seguro** — bug real, achado só ao
     tentar lançar ponto de verdade pelo celular contra `http://192.168.1.11` (HTTP puro, IP, sem
     HTTPS): a função trava o app inteiro nessa condição, porque `crypto.randomUUID()` (usada em
     `lib/outbox.ts` pra gerar `client_operation_id`/`lancamentoLocalId`, e em
     `PartidaScorerPage.tsx` pro `client_operation_id` do lançamento de combate) só existe em
     "contexto seguro" (HTTPS ou `localhost`) — o spec do Web Crypto restringe especificamente
     essa função, não o `crypto` inteiro. Em qualquer outro host por HTTP simples (exatamente o
     caso do ginásio, celular batendo no IP da máquina que roda o sistema), `crypto.randomUUID`
     não existe no objeto `crypto`, e a chamada lança, caindo direto no `catch` genérico que
     mostra "Não foi possível registrar/confirmar o lançamento neste dispositivo" — mensagem
     _correta_ no sentido literal (era mesmo aquele dispositivo/contexto), mas sem pista nenhuma
     da causa raiz. **Por que nenhum teste pegou isso antes**: os testes automatizados rodam em
     jsdom (via vitest), que não simula a restrição de contexto seguro do navegador de verdade —
     `crypto.randomUUID()` funciona liso em jsdom independente de HTTP/HTTPS/host, então a suíte
     inteira passava mesmo com o bug presente. Só apareceu batendo com um dispositivo real contra
     o IP real. **Corrigido** com `frontend/src/lib/uuid.ts` (`randomUUID()` implementado na mão
     via `crypto.getRandomValues()` — essa função *não* tem a restrição de contexto seguro, é
     anterior a essa exigência do spec e segue disponível em qualquer origem) — usada agora nos
     4 pontos que antes chamavam `crypto.randomUUID()` direto. Testado com um teste de formato
     puro (`uuid.test.ts`, regex de UUID v4 + verificação de unicidade) e, mais importante,
     verificado **de verdade**: fluxo completo de registrar + confirmar lançamento via Chromium
     headless batendo em `http://192.168.1.11`, mesma condição exata do celular do usuário, sem
     nenhum erro. Lição value pro projeto inteiro: **qualquer `crypto.randomUUID()` novo que
     apareça no código daqui pra frente deve usar `lib/uuid.ts::randomUUID()` em vez da API
     nativa** — nada nesse app pode assumir HTTPS, é o oposto do contrato real (celular no
     ginásio, rede local, sem certificado).

   Efeito colateral chato dessas verificações: cada rodada de teste real (essa sessão e a
   anterior) deixou lançamentos de teste reais no banco de produção que está no ar agora (equipe
   fictícia tipo "Nível 1 - Equipe A" com total 0 em Viagem ao Centro da Terra, e outros
   acumulados antes). **Resolvido ainda na mesma sessão** (ver bloco seguinte) — o reset virou
   necessário mesmo pra aplicar a correção da ficha da Viagem, então aproveitou pra limpar tudo
   de uma vez.

   **Ranking interno de volta no Painel + dois bugs achados testando com o coordenador de
   verdade** (mesmo dia):

   - **Aba Ranking reconectada** — pedido explícito do coordenador: "preciso ter, como
     coordenador, quem tá ganhando ou perdendo, até pra eu conseguir ver aqui nos testes se tá
     certo". A aba e o componente `RankingClassificacao` nunca tinham sido apagados (só
     desconectados numa sessão anterior por falta de tempo) — restaurado o `PainelPage.tsx`
     exatamente como era antes (`git show` do commit inicial), tablist Ranking/Submissões com
     Ranking selecionado por padrão. Uso continua só interno (só quem vê o link "Painel" no
     Header — coordenador/secretaria), sem tocar em `ranking_liberado` nem na exposição pública:
     `RankingClassificacao` já buscava o ranking por modalidade independente dessa flag (rota
     `/ranking/modalidades/{id}` já é liberada pra staff mesmo sem `ranking_liberado`), então
     "religar a aba" e "expor pro público" sempre foram coisas independentes.
   - **Achado no caminho: só `ModalidadeListPage` gravava o "evento atual"** — desde a sessão
     anterior, clicar num evento passou a levar direto pra `/competicoes` (não mais
     `/modalidades` primeiro), mas só `ModalidadeListPage` chamava
     `useEventoStore().definirEventoAtual(eventoId)`. Resultado: pra quem chegava via
     Competições sem nunca ter passado por Modalidades, os outros links do Header (Painel,
     Modalidades, Fichas) caíam de volta pra `/eventos` porque `eventoAtualId` continuava nulo —
     bug que já existia antes (nem `/individual` nem `/combates` setavam isso), só ficou visível
     agora que Competições virou o destino padrão do clique no evento. Corrigido adicionando o
     mesmo `useEffect` em `CompeticoesPage.tsx`.
   - **Modelo errado de "tentativa" pra Viagem ao Centro da Terra** — achado pelo usuário
     testando pontuação de verdade. Os "1º cubo"/"2º cubo" da ficha oficial **não são duas
     tentativas separadas** (duas pontuações/lançamentos independentes) — são as duas metades de
     **uma corrida só**, dentro da mesma rodada: ida até o centro, pega o 1º cubo, volta,
     entrega, vai de novo, pega o 2º cubo. O sistema estava com `tentativas_por_rodada=2` pra
     essa modalidade, o que fazia `PontuarPage.tsx` (lógica 100% genérica, dirigida por
     `modalidade.tentativas_por_rodada`, sem nenhuma mudança de código necessária ali) abrir 2
     cards de pendência por equipe por rodada — errado, porque cada card vira um `lancamento`
     independente com confirmação própria, e na prática é uma corrida contínua. "Saída da arena"
     durante a corrida já era coberto pelo critério de penalidade "Atravessar a borda"
     (-5/ocorrência) — tentativa não entra nessa conta, o robô reinicia mas continua na mesma
     rodada. Corrigido em `db/seed.py`: `tentativas_por_rodada` da Viagem virou `1`, e
     `_ficha_viagem` foi reestruturada de 1 grupo único ("Percurso") pra 2 grupos ("1º Cubo",
     "2º Cubo"), cada um com os mesmos 6 critérios de pontuação + "Atravessar a borda" — o
     próprio PDF oficial diz que atravessar a borda zera os pontos "daquele cubo" especificamente
     (jurisprudência que já era simplificada antes pra um desconto fixo por ocorrência, mantido
     assim, só duplicado por cubo pra dar rastro de qual lado falhou). "Reinício entre as
     rodadas" (níveis 3-4) continua num grupo à parte ("Modificadores"), porque esse é por
     rodada, não por cubo. Testado via `test_seed.py` (estrutura de grupos/critérios + 1
     tentativa por rodada) e verificado ao vivo: fluxo Pontuar mostra 1 card por equipe/rodada
     agora, e a ficha abre com as duas seções "1º Cubo"/"2º Cubo" dentro do MESMO formulário, um
     só "Registrar lançamento" no fim. **Exigiu reset completo do banco** (mesma sessão, mesmo
     motivo do bloco anterior) porque já existia lançamento real em cima da ficha antiga de
     Viagem — seed é idempotente, não sobrescreve ficha/config de modalidade já existente.

   **Correção rápida na sequência, mesma sessão**: usuário testando de verdade achou o rótulo
   "Atingir os 6 Cn..." confuso (jargão da ficha oficial, não óbvio pra árbitro de campo) —
   confirmou que a regra em si (pontuar por vértice individual, `CriterioTipo.CONTADOR`) estava
   certa, só o texto precisava melhorar. Renomeado pra "Atingir vértice sem/com o alvo, na
   ida/volta" nos dois critérios de `_grupo_cubo_viagem` (`db/seed.py`) + `test_seed.py`
   atualizado (TDD: teste vermelho com o nome novo antes de mudar o seed).

   **Gotcha operacional achado ao vivo, vale registrar**: com o ambiente publicado em modo
   produção (`docker-compose.prod.yml`, sem bind mount de código), `docker compose exec api
   pytest` roda contra o código **baked na imagem**, não contra edição nenhuma feita depois do
   último `--build` — parece rodar normal (não dá erro nenhum), só que silenciosamente ignora
   qualquer mudança de arquivo, dando falso-verde ou, pior, "not found" pra teste novo que nem
   existe na imagem antiga. Pra fazer TDD de verdade com o ambiente de prod no ar, é preciso
   `docker compose up -d api` (sem `-f docker-compose.prod.yml`, volta o bind mount) antes de
   editar/rodar teste, e só depois `docker compose -f docker-compose.yml -f
   docker-compose.prod.yml up -d` de novo pra devolver o hardening (sem porta publicada, sem
   bind mount) quando terminar. Aplicar uma correção de `seed.py` num banco de prod já rodando,
   sem lançamento em cima da ficha afetada, não precisa do reset completo (`DROP
   DATABASE`/`CREATE DATABASE`) — só apagar `criterio`/`grupo`/`ficha` daquela modalidade
   (nessa ordem) e rodar `python -m app.db.seed` de novo, que já documentado na seção 12 mas
   fácil de esquecer no calor de uma sessão com o ambiente ativo.

   **QA cego com agente sem contexto do projeto** (mesmo dia, a pedido do usuário: "dá uma testada
   100%... coloca um agente que não tem contexto do projeto, dá uma conta de juiz pra ele").
   Criada conta dedicada `agente-teste@tjr.app` (ARBITRO) só pra isso — não reaproveitar
   `juiz@tjr.app`, que é a conta que o usuário usa manualmente, pra não misturar rastro. Agente
   `general-purpose` sem nenhum contexto desta conversa, testou via Chromium real (mesmo truque
   de `docker run node:20-slim` + Playwright já usado nesta sessão) contra `http://192.168.1.11`,
   cobrindo as 4 modalidades individuais e as 3 de confronto.

   **Achou 1 bug crítico real**: depois de clicar "Registrar lançamento" (que cria o lançamento
   `PENDENTE` na fila local), os campos de critério continuavam clicáveis e o "Preview" no rodapé
   atualizava ao vivo — mas nenhuma dessas edições chegava no lançamento de verdade.
   "Confirmar lançamento" confirmava os itens de quando foi registrado, não os editados depois —
   o árbitro via um número diferente do que ia ser persistido, **sem aviso nenhum**. Reproduzido,
   confirmado com teste (`LancamentoFormPage.test.tsx`) e corrigido: `CriterioPreview`
   (`features/ficha/FichaPreviewPage.tsx`) ganhou uma prop `disabled`, e
   `LancamentoFormPage.tsx` passa `disabled={!!lancamentoAtivo}` — assim que existe um
   lançamento ativo (`PENDENTE` ou `CONFIRMADO`), os campos travam de vez (sem mecanismo de
   "editar antes de confirmar" — se precisar corrigir algo depois de registrado, é o fluxo de
   correção do coordenador, não reabrir os campos). A linha "Preview: X" também some nesse
   estado, já que não tem mais nada a pré-visualizar.

   **Achou 1 dúvida que virou bug pequeno confirmado**: abrir a ficha direto (link salvo, botão
   voltar do navegador, card desatualizado) pra uma equipe que já tinha lançamento `CONFIRMADO`
   nessa rodada+tentativa mostrava o formulário **em branco**, como se nada tivesse sido lançado
   — o backend já recusava duplicata (`409 LANCAMENTO_JA_EXISTE`, sem risco de dado duplicado),
   mas a tela enganava antes disso. Causa: a lógica que decide "existe lançamento pra essa
   equipe/rodada/tentativa" só olhava status `PENDENTE`, ignorando `CONFIRMADO` de propósito (pra
   voltar direto pra confirmação em vez de deixar tentar registrar de novo) — só que também
   deixava passar batido o caso já confirmado. Corrigido incluindo `CONFIRMADO` no mesmo filtro
   (`lancamentoExistente` em `LancamentoFormPage.tsx`).

   Os widgets de pontuação em si (contador +/-, booleano toggle, escala, o scorer rápido de 1
   clique de combate, o multi-critério da Corrida de Carros) e o cálculo de total bateram certo
   em todos os testes do agente — nenhum problema achado ali. Os dois bugs foram testados (TDD)
   e verificados batendo o cenário exato do relatório contra o ambiente de produção publicado.

   **Bug estrutural real no seed pra MATA_MATA, achado o usuário perguntando "por que o Sumô já
   tem as rodadas prontas? Não depende de quem ganhou antes?"** — pergunta certeira, revelou que
   `seed_rodadas` (`db/seed.py`) chamava `rodada_service.gerar_rodadas` pra **toda** modalidade
   `CONFRONTO` igual, sem checar `formato_chaveamento`. Essa função usa pareamento round-robin
   ("método do círculo" — o próprio docstring dela diz "mata-mata (chaveamento de fato) fica pra
   Fase 4", comentário nunca atualizado depois que a Fase 4 implementou o bracket de verdade em
   `chaveamento.py`) — certo pra `TODOS_CONTRA_TODOS` (Cabo de Guerra, Corrida de Carros), **errado
   pra `MATA_MATA`** (Sumô): pré-gerava as 5 `qtd_rodadas` inteiras com confrontos decididos de
   antemão, sem nenhuma depender de quem vencia a rodada anterior — o oposto do que a seção 6 já
   documentava. Pior: isso também deixava `gerar_chaveamento_inicial` (o gerador de bracket
   correto) inacessível depois, porque ele recusa com `409 CHAVEAMENTO_JA_INICIADO` assim que
   existe qualquer rodada pra aquela modalidade.

   **A UI do coordenador nunca teve esse bug** — `RodadaListPage.tsx` já mostra "Gerar
   chaveamento" (não "Gerar rodadas") pra modalidade `MATA_MATA`, chamando o serviço certo
   (`chaveamento.gerar_chaveamento_inicial`). O problema era só no seed, que contornava essa
   distinção. Corrigido: `seed_rodadas` agora bifurca por `formato_chaveamento` — `MATA_MATA`
   chama `_obter_ou_gerar_chaveamento_inicial` (só a Rodada 1, idempotente por checar
   `Rodada.numero == 1` direto em vez de depender da exceção do serviço); todo o resto continua
   no `gerar_rodadas` de sempre. Testado (TDD): `test_seed_rodadas_mata_mata_nao_pre_gera_rodadas_futuras`
   prova que só existe Rodada 1 pro Sumô depois do seed; os testes que somavam
   `qtd_rodadas` pra todo mundo (`test_seed_rodadas_cria_qtd_rodadas_para_cada_modalidade`,
   `test_seed_rodadas_e_idempotente`) ganharam uma exceção pra `MATA_MATA` (`_qtd_rodadas_esperada_no_seed`).

   **Aplicado no ambiente publicado, com aprovação explícita do usuário** — a chamada de
   `POST /modalidades/{id}/chaveamento/reset` tinha sido bloqueada pelo classificador do modo
   automático (ação destrutiva batendo numa API já publicada); parei e expliquei em vez de
   contornar, usuário respondeu "pode rodar". Sequência executada: `POST
   /modalidades/{sumo_id}/chaveamento/reset` com justificativa (apaga rodada/partida/lançamento
   antigos do Sumô, grava snapshot em `audit_log`) → `POST /api/v1/chaveamento/gerar` (rota real,
   não aninhada em `/modalidades/{id}/...` — cuidado, é `/api/v1/chaveamento/gerar` com
   `modalidade_id` no body). Resultado verificado: só existe Rodada 1 pro Sumô agora, com 4
   equipes por nível → 2 partidas por nível (bracket real, não round-robin) — conferido tanto
   via API quanto visualmente na aba Chaveamento (mostra só "Rodada 1", sem inventar rodadas
   futuras, e o botão vira "Resetar chaveamento" assim que o bracket existe).

   **Bug real seguinte, achado pelo usuário pontuando o próprio Sumô que acabara de ser
   corrigido acima**: "pontuei o sumô e não apareceu a final aqui". `avancar_se_rodada_completa`
   (`services/chaveamento.py`) checava se **todas as partidas da rodada inteira** (todos os
   níveis juntos) estavam `ENCERRADA` antes de gerar a próxima rodada — contradizendo o próprio
   docstring da função, que já dizia "cada nível corre seu próprio chaveamento, independente dos
   outros". Como o avanço é automático (chamado de dentro de `registrar_resultado_lancamento`
   assim que uma partida fecha, sem clique de coordenador nenhum), o nível 1 fechava suas 2
   partidas mas a final dele só apareceria quando TODOS os outros níveis também fechassem — o
   inverso da regra inviolável 9. Achado real de teste também revelado no caminho: os testes
   existentes de independência por nível (`test_mata_mata_avanca_niveis_de_tamanhos_diferentes_independente`
   e `test_mata_mata_avanca_pareando_vencedores_em_ordem`) fechavam TODAS as partidas de TODOS os
   níveis num loop e só depois chamavam `avancar_se_rodada_completa` manualmente uma vez no final —
   nunca exercitando o gatilho automático no meio do caminho, com outro nível ainda aberto. Pior:
   como a função não tinha nenhuma checagem de idempotência (sempre criava
   `Rodada(numero=rodada.numero+1)` sem olhar se já existia uma), essas chamadas manuais no fim do
   teste criavam uma **segunda rodada duplicada** com o mesmo `numero` por trás do pano — mascarado
   porque o teste só validava o objeto retornado pela própria chamada, nunca o estado real do
   banco.

   Corrigido: o gate de "fechou tudo" e a decisão de gerar passaram a ser por nível (agrupa
   partidas por `partida.nivel`, cada grupo decide sozinho se está pronto), e a função agora
   procura uma `Rodada` já existente com `numero = rodada.numero + 1` antes de criar uma nova —
   se já existe (porque outro nível avançou primeiro), só adiciona a partida do nível que acabou
   de fechar nela, sem duplicar. Teste novo
   (`test_mata_mata_gera_proxima_rodada_de_um_nivel_sem_esperar_outro_nivel_fechar`) fecha só o
   nível 1 de uma modalidade com 2 níveis, via `confirmar_lancamento` real (não chama
   `avancar_se_rodada_completa` manualmente em nenhum momento — só o gatilho automático), e
   consulta o banco direto pela `Rodada numero=2`. Os dois testes antigos que mascaravam o bug de
   duplicação foram ajustados pra não fazer mais a chamada manual redundante — em vez disso
   consultam o banco direto pra confirmar o que o gatilho automático já gerou sozinho, e a chamada
   manual extra que sobrou em cada um agora é asserted como no-op (`is None`), provando a
   idempotência.

   **Aplicado ao ambiente publicado**: como o Sumô já tinha partidas reais pontuadas contra o
   código antigo, corrigir o código sozinho não gera retroativamente a final que já devia ter
   sido criada — o evento de fechamento do nível 1 já tinha disparado e sido bloqueado silenciosamente
   uma vez. Resolvido chamando `avancar_se_rodada_completa` diretamente por script (`docker compose
   exec -T api python3`, sessão via `app.db.session.AsyncSessionLocal`, usando o `usuario_id` do
   coordenador seedado) contra o banco `tjr` real, uma única vez pra `rodada_id` da Rodada 1 do
   Sumô — gerou a Rodada 2 (nível 1: Equipe A × Equipe B) sem tocar nas partidas já fechadas.
   Confirmado visualmente na aba Chaveamento (`/competicoes` → Combate → Chaveamento → selecionar
   "Sumô") depois de restaurar o stack pra modo produção
   (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`).

   **Sessão de import real de equipes + últimos ajustes antes da competição** (27/08/2026).
   Objetivo: sair do estado de seed fictício e deixar produção pronta com as equipes de verdade.

   - **Import real da planilha oficial em produção** — sequência: reset do banco de produção
     (apagou `equipe`/`inscricao`/`rodada`/`partida`/`agendamento` fictícios do seed normal, sem
     tocar `evento`/`modalidade`/`ficha`/`usuario`), `python -m app.db.seed --apenas-estrutura`
     pra criar as modalidades que só existiam no código (`Sumô RC 1,5 kg`, `Sumô 3 kg`, do
     refactor da sessão anterior — produção ainda tinha a `Sumô Controlado` antiga, que ficou
     órfã, sem equipe, decisão consciente de não mexer), e então
     `scripts/lista_2026/importar.py` rodado de fato contra a planilha real
     (`LISTA 2026 (1).xlsx`, nunca commitada — tem dado real de mentor/escola). 174 linhas, 139
     equipes novas, 166 inscrições, 2 linhas ignoradas de propósito (teste + Registro
     Multimidiático). Correções manuais pedidas pelo coordenador em cima do import (via script
     avulso usando os services direto, mesmo padrão de outras sessões): `Antônio` (nível 2,
     Resgate no Plano) renomeada pra `ABCMP`; `Hefesto Tech` consolidada — a planilha tinha essa
     equipe cadastrada com **nome de robô** em 3 modalidades diferentes (`Lidenbrock` na Viagem
     nível 4, `Fauna-flora` na Dança nível 3, `hefestos tech - war cable` no Cabo de Guerra nível
     3); renomeadas as duas primeiras, a inscrição de Cabo de Guerra movida pra cima da equipe
     nível 3 renomeada (evitando duplicar `Hefesto Tech` nível 3 duas vezes), a equipe órfã
     resultante desativada (não apagada); mais 2 modalidades novas pra ela (Corrida de Carros
     Autônomos nível 1/ABSOLUTO, Sumô nível 3 — confirmado com o usuário, já que ela não tinha
     nível único). `JARVIS`/`STARK` (já em Sumô RC 1,5kg, nível 1) ganharam inscrição também em
     Sumô "autônomo" tradicional, reaproveitando a mesma equipe (nível 1 é aceito lá também,
     `niveis_aplicaveis` default é `[1,2,3,4]`). Achado no caminho: a planilha também tinha
     `Antônio 2` (Viagem ao Centro da Terra, mesma escola/mentor/cidade de `Antônio`) — mesma
     pegadinha nome-de-robô-como-nome-de-equipe da Hefesto Tech; decisão do usuário foi virar
     `ABCMP 2` como equipe distinta (não mesclar com a primeira), e ele mesmo ajustou depois pela
     tela de Editar já que essa opção passou a existir nesta sessão.
   - **Busca de equipe por nome** — campo `Buscar equipe` em `EquipeListPage.tsx`, filtro
     client-side (case-insensitive) sobre a lista já carregada, ao lado dos filtros de
     nível/modalidade que já existiam.
   - **Editar equipe ganhou gestão de modalidades inline** — o que já existia (renomear/mudar
     nível) e o que só dava pra fazer indo em cada modalidade (`InscricaoPage`) foram juntados:
     clicar em "Editar" agora mostra, junto do formulário de nome/nível, um painel
     (`EquipeModalidadesPanel`) com as modalidades já inscritas (+ "Remover") e um seletor pra
     adicionar uma nova, já filtrado pelo nível da equipe (`niveis_aplicaveis`). Primeira versão
     tinha um botão "Modalidades" separado do "Editar" — unificado a pedido do usuário depois de
     testar ("faltou eu conseguir adicionar modalidade quando clicar em editar").
   - **Criar equipe já nasce inscrita** — o formulário "Criar nova equipe" ganhou uma seção de
     checkboxes de modalidade, também filtrada pelo nível escolhido no próprio formulário
     (reage à mudança de nível ao vivo). Ao submeter, cria a equipe e depois um `POST
     /inscricoes` por modalidade marcada, sequencial. Sem isso, cadastrar uma equipe nova sempre
     exigia um segundo passo (editar → adicionar modalidade).
   - **Rodadas das individuais: 3 → 2** — Resgate no Plano, Resgate de Alto Risco e Viagem ao
     Centro da Terra tinham `qtd_rodadas=3` (Dança já era 2); pedido do usuário, aplicado no
     `seed.py` e também diretamente no banco de produção via script avulso (nenhuma rodada real
     existia ainda pra essas modalidades, sem risco de discrepância com dado já lançado).
   - **Chaveamento manual — três desenhos até chegar no atual, todos em TDD**. Motivação:
     coordenador reclamou do mata-mata puramente automático/sorteado e queria controlar quem
     enfrenta quem. Primeira tentativa (`gerar_chaveamento_manual`, `ordem_por_nivel`): o
     coordenador informava a ordem de todas as equipes de um nível de uma vez, sistema pareava
     consecutivo; exigia `modalidade.formato_chaveamento` travado em `MATA_MATA` antes de usar.
     Descartada pelo usuário antes de ir pro ar — ele queria montar confronto por confronto, não
     a lista inteira de uma vez, e não queria precisar travar formato pra isso. Segunda versão
     (a que ficou): `criar_partida_manual(modalidade_id, equipe_a_id, equipe_b_id)` cria **uma
     partida por vez** (equipe_b `None` = bye), sempre na Rodada 1 (cria ou reaproveita),
     validando nível igual entre as duas equipes e que nenhuma já tem partida na modalidade — sem
     exigir formato travado. Isso expôs uma lacuna real no dispatcher automático
     (`gerar_chaveamento_confronto`): ele recusava rodar (`CHAVEAMENTO_JA_INICIADO`) assim que
     *qualquer* rodada existisse, mesmo que só 1 dos vários níveis da modalidade tivesse sido
     montado na mão — bloqueando o automático completar os outros níveis (o caso real de Sumô:
     nível com ≤5 equipes deve continuar automático/todos-contra-todos, nível com mais o
     coordenador monta manualmente). Corrigido: o dispatcher agora calcula quais níveis já têm
     *qualquer* partida (`niveis_com_partida`) e só gera pros que faltam, reaproveitando a Rodada
     1 existente em vez de tentar criar outra; só recusa com `CHAVEAMENTO_JA_INICIADO` quando não
     sobra nada pra gerar. Verificado ao vivo (não só teste automatizado): criado nível pequeno +
     nível grande numa modalidade de teste, montado o nível grande na mão via API, rodado
     `/chaveamento/gerar`, e só o nível pequeno foi preenchido automaticamente — o manual ficou
     intacto, sem duplicar rodada. Frontend: botão "Montar chaveamento manual" ao lado do "Gerar
     chaveamento" em `RodadaListPage` (some só se o formato estiver travado explicitamente em
     `TODOS_CONTRA_TODOS`, onde ordem manual não faz sentido — round-robin joga todo mundo contra
     todo mundo de qualquer forma), abre `ChaveamentoManualBuilder`: seletor de nível (só
     aparece com mais de 1 nível elegível), dois selects (Equipe A / Equipe B, com opção de bye),
     lista ao vivo dos confrontos já montados naquele nível. Terceiro ajuste, achado testando ao
     vivo com dado real (Sumô, várias equipes por nível): o modal não tinha altura máxima nem
     rolagem própria — com vários confrontos já montados, a caixa crescia mais que a tela e,
     por ficar centralizada (`items-center`), cortava o topo (seletor de nível) e o rodapé
     (botão "Fechar") **igualmente** pra fora da janela, os dois sumiam ao mesmo tempo. Corrigido
     com `max-h-[90vh] overflow-y-auto` no card do modal; confirmado ao vivo numa janela baixa
     (1024×550) com confrontos reais pré-criados que o "Fechar" continua alcançável via rolagem
     interna.

     **Pendência explícita pro dia seguinte** (nota do usuário, textual: "amanhã vamos ter que
     pensar melhor nesse negócio do chaveamento pq ele bagunçou tudo"): mesmo com o bug de
     overflow corrigido e a suíte 100% verde, o coordenador não ficou satisfeito com o desenho
     geral do fluxo de chaveamento manual depois de usar de verdade — sem detalhe ainda de
     *o quê* especificamente incomodou (UX de montar partida por partida, a convivência
     automático+manual no mesmo nível, outra coisa). Não presumir o problema nem tentar
     redesenhar sozinho antes de ouvir o que ele achou confuso/errado na prática.

   **Reset de equipes pra reimportar a planilha oficial + fase de grupos ("chave")** (28/08/2026).
   O usuário achou erros reais no import anterior (equipes de robô virando equipe separada tipo
   "Bananabot"/"Bananabot2", equipe real faltando) e pediu reset total de equipe/inscrição/
   rodada/partida (local e produção são **o mesmo banco** nesta máquina — dev e prod só mudam o
   modo do compose, `docker-compose.prod.yml` reaproveita o volume de propósito, documentado no
   próprio arquivo) pra reimportar devagar e conferir. Confirmado zero lançamento antes de apagar
   (`DELETE` direto, sem passar pelo `resetar_chaveamento` porque não era por modalidade, era o
   banco inteiro) — `evento`/`modalidade`/`ficha`/`usuario` ficaram intactos.

   Na sequência, pedido novo do coordenador pra Cabo de Guerra/Corrida de Carros Autônomos/Sumô/
   Sumô 3 kg (**não** Sumô RC 1,5 kg, que fica mata-mata puro): fase de grupos "estilo Copa do
   Mundo" — equipes de um nível divididas em grupos menores (cada grupo joga todos-contra-todos
   entre si, garante pelo menos 2 jogos por equipe), e depois da fase de grupos o próprio
   coordenador monta o mata-mata (quartas/semi/final) na mão a partir da classificação de cada
   grupo. Decisão consciente de **não automatizar o cruzamento entre grupos pro mata-mata** (tipo
   "1º do A pega 2º do B") — é a parte que o coordenador achou complicada quando tentou pensar
   nisso sozinho, e ele topou montar esse cruzamento na mão com a ferramenta de chaveamento manual
   que já existia (seção anterior). Nome de domínio novo aprovado pelo usuário: **"chave"** (ex.:
   "Chave A", "Chave B") — diferente de "grupo" (já reservado pra seção de ficha).

   Arquitetura (planejada em `EnterPlanMode` antes de codar, TDD do início ao fim): **sem** valor
   novo no enum `FormatoChaveamento` (evita `ALTER TYPE ... ADD VALUE`, sem precedente nas
   migrations do projeto) — fase de grupos é ortogonal a esse enum, as partidas de chave continuam
   `formato_chaveamento=TODOS_CONTRA_TODOS` (é logicamente o que são), só que agora carregam
   `Partida.chave_id` (nullable, migration `6a506624890d`, depois de `101da0b8d6c0` criar as
   tabelas `chave`/`chave_equipe`) pra saber de qual chave vieram. Isso deixa
   `gerar_chaveamento_confronto` (dispatcher automático) **inalterado** — como ele já pula
   (`niveis_com_partida`) qualquer nível que já tenha qualquer partida, um nível que passou por
   fase de grupos manual fica de fora do automático de graça.

   - `services/chave.py` (novo): `criar_chave`/`adicionar_equipe`/`remover_equipe`/`listar_chaves`
     — regra nova `EQUIPE_JA_TEM_CHAVE` (409): equipe só pode estar numa chave por modalidade
     (permitido a mesma equipe estar em chaves de modalidades diferentes). `remover_equipe`
     recusa (`CHAVE_JA_TEM_PARTIDA`) se a chave já tem jogo gerado — sem reset granular por chave
     nesta entrega, o caminho de correção é o `resetar_chaveamento` de sempre (modalidade
     inteira).
   - `services/chaveamento.py::gerar_fase_de_grupos` (novo) — mesmo esqueleto do bloco
     `niveis_liga` de `gerar_chaveamento_confronto` (reaproveita `_gerar_pareamento`/
     `_rodadas_necessarias` de `rodada.py`), só que agrupado por `chave_id` em vez de `nivel`;
     idempotente (chave que já tem partida é pulada). Extraído `_obter_ou_criar_rodada` (antes uma
     função aninhada só de `gerar_chaveamento_confronto`) pra nível de módulo, reaproveitado pelos
     dois.
   - **Achado central do desenho** (só apareceu ao encadear os testes, não era óbvio de antemão):
     `criar_partida_manual` tinha a rodada-alvo **fixa** em `numero=1` e a checagem
     `EQUIPE_JA_TEM_PARTIDA` olhava a **modalidade inteira** — isso bloquearia incorretamente uma
     equipe que já jogou a fase de grupos (ela já tem partida, só que numa rodada anterior) de
     entrar no mata-mata manual. Corrigido: rodada-alvo passou a ser calculada (maior
     `Rodada.numero` com partida daquele nível, +1 — mas só avança se essa última rodada foi
     `TODOS_CONTRA_TODOS`; se já for `MATA_MATA`, reaproveita o mesmo número, porque é outra
     chamada manual ainda montando a mesma rodada), e a checagem de duplicata passou a filtrar só
     pela rodada-alvo, não mais a modalidade toda. Efeito colateral bom, provado por teste
     (`test_avancar_se_rodada_completa_funciona_sozinho_a_partir_da_segunda_rodada_pos_grupos`):
     como a fase de grupos nunca aciona `avancar_se_rodada_completa` (só `MATA_MATA` aciona) e a
     1ª rodada manual pós-grupos já nasce `MATA_MATA`, a partir da 2ª rodada (ex.: semifinal→final)
     o avanço automático que já existia cuida sozinho — só a 1ª rodada pós-grupos precisa ser
     montada na mão.
   - `services/consolidacao.py` — extraído `_computar_stats_liga` (vitórias/empates/derrotas +
     nota_final) do meio de `_classificacao_todos_contra_todos` sem mudar comportamento (coberto
     pela suíte já existente, sem teste de regressão redundante); nova
     `calcular_classificacao_chave(db, chave_id)` reaproveita esse helper + o mesmo desempate por
     confronto direto, filtrando partidas por `Partida.chave_id` direto (mais simples que a
     variante por nível, que precisa passar pela modalidade inteira).
   - Endpoints novos (`api/v1/chave.py`, router registrado em `main.py`): CRUD de chave
     (`POST/GET /modalidades/{id}/chaves`, `POST/DELETE /chaves/{id}/equipes[/{equipe_id}]`) e
     `GET /chaves/{id}/classificacao` — todos `_PAPEIS_LEITURA`/`COORDENADOR`, **sem** `PUBLICO`
     (o projeto mantém ranking fora do público de propósito desde a sessão anterior). Mais
     `POST /modalidades/{id}/chaveamento/fase-de-grupos/gerar` em `chaveamento.py`.
   - Frontend: `FaseDeGruposBuilder.tsx` (novo, mesmo esqueleto de estado/modal do
     `ChaveamentoManualBuilder.tsx`) — criar chave, adicionar/remover equipe, "Gerar fase de
     grupos"; botão novo "Fase de Grupos" em `RodadaListPage.tsx` ao lado de "Montar chaveamento
     manual" (mesma condição de exibição — some só em `TODOS_CONTRA_TODOS` explícito).
     `ChaveamentoManualBuilder.tsx` ganhou a mesma correção de rodada-alvo do backend (antes fixo
     em `numero===1`), buscando partidas de **todas** as rodadas em vez de só a 1. `lib/fase-
     chaveamento.ts::calcularTotalRodadasPorNivel` deixou de assumir "rodada 1 = início do
     bracket" — agora acha, por nível, a primeira rodada cujas partidas são `MATA_MATA` (rodadas
     antes dela podem ser fase de grupos); sem isso os rótulos "Final/Semifinal" saíam errados
     pra qualquer nível que passasse por chave. `PontuarCombatePage.tsx::grupoDaPartida` passou a
     rotular partida de fase de grupos pelo **nome da chave** (lookup vivo via
     `GET .../chaves`, mesmo padrão de resolução de nome já usado pra equipe) em vez do rótulo
     fixo "Fase de Grupos", com prioridade de ordenação baixa (aparece depois do mata-mata assim
     que ele existir).
   - Suíte: backend 530 (+35 dessa sessão), frontend 397 (+23), typecheck/lint/ruff limpos.
     **Sem verificação ao vivo contra o banco compartilhado desta vez** — decisão consciente, pra
     não sujar o evento real no meio do reimport da planilha que o usuário estava fazendo em
     paralelo; a suíte automatizada já cobre a cadeia completa (chave → fase de grupos → mata-mata
     manual → avanço automático) em nível de serviço.

   **Import real da `LISTA_FINAL.xlsx`, montagem dos grupos e reversão da trava Sumô/Sumô RC**
   (mesma data). Corrigido um bug real no `scripts/lista_2026/importar.py` no caminho: a
   planilha final salva a coluna de nível como float (`"0.0"`, `"2.0"`) em vez do inteiro puro
   da planilha anterior, e `int(nivel_bruto)` quebra nesse formato — trocado por
   `int(float(nivel_bruto))`. Depois da correção: 135 equipes, 161 inscrições, 2 linhas
   ignoradas de propósito, zero erro.

   Configuração de formato aplicada por modalidade de confronto, via `PATCH /modalidades/{id}`
   (override explícito de `formato_chaveamento`) quando a contagem real de equipes não bateria
   com o que o usuário queria: Sumô RC 1,5 kg forçado `MATA_MATA`; Corrida de Carros Autônomos
   forçado `TODOS_CONTRA_TODOS` (sem forçar, 6 equipes reais cairia em mata-mata pela regra
   automática de contagem); Sumô 3 kg deixado automático (só 3 equipes, a regra de contagem já
   resolve sozinha). Cabo de Guerra e Sumô (os "restantes", os que tinham gente demais pra
   round-robin simples) ganharam fase de grupos de verdade: script avulso (`docker compose exec
   -T api python3`, mesmo padrão de outras sessões) criou as chaves e distribuiu as equipes —
   **primeira tentativa foi em ordem alfabética** (mais fácil de auditar visualmente), mas o
   usuário pediu pra trocar por sorteio de verdade ("senão nego vai reclamar") — resetado via
   `resetar_chaveamento` (zero lançamento em risco, só acabara de gerar) e remontado com
   `random.shuffle` antes de distribuir round-robin nas chaves. Tamanho de grupo é decisão livre
   do assistente (sem instrução numérica do usuário): alvo de ~4-5 equipes por chave, arredondado
   pra cima quando sobra 1-2 equipes, sem nenhuma fórmula fixa — Cabo de Guerra nível 2 (14
   equipes → 3 chaves de 5/5/4), nível 3 (22 → 5 chaves de 5/5/4/4/4), nível 4 (8 → 2 chaves de
   4/4); Sumô nível 3 (11 → 3 chaves de 4/4/3), nível 4 (6 → 2 chaves de 3/3). Sumô nível 2 (só 4
   equipes) ficou de fora de propósito — já vira todos-contra-todos sozinho pela regra de
   contagem, grupo ali seria só burocracia extra.

   **Selo visual de chave nas telas de combate** — pedido do usuário depois de montar os grupos
   ("da uma informação visual... pra ficar melhor de ler"): sem isso, um nível com 5 chaves virava
   uma lista corrida de 10 confrontos sem nenhuma pista de qual chave era qual.
   `RodadaListPage.tsx::CombateRodada` passou a sub-agrupar `partidasDoNivel` por `chave_id`
   (fallback pra lista plana quando nenhuma partida do nível tem chave — mata-mata automático
   continua igual) com um rótulo pequeno (nome da chave, resolvido ao vivo via
   `GET /modalidades/{id}/chaves`, nunca hardcoded) acima de cada bloco.
   `ChaveamentoPage.tsx::ColunaRodada` ganhou o mesmo rótulo dentro de cada card de partida.
   Confirmado ao vivo no navegador nas duas telas.

   **Trava Sumô ↔ Sumô RC 1,5 kg removida** (`_recusar_se_par_conflitante_em_andamento` e
   `_MODALIDADES_COMBATE_CONFLITANTE`, `services/chaveamento.py`) — essa regra existia desde uma
   sessão anterior (parte deliberada do design: as duas modalidades competem com o mesmo robô
   físico possível, e a trava impedia gerar o chaveamento de uma enquanto a outra tivesse combate
   em aberto, pra nunca ter árbitro chamando a mesma equipe pras duas ao mesmo tempo). Bloqueou a
   geração do Sumô RC 1,5 kg nesta sessão (Sumô já tinha fase de grupos aberta) — o usuário decidiu
   que a trava atrapalha mais do que ajuda ("vai dar muita dor de cabeça"), porque ele quer montar
   TODOS os chaveamentos com antecedência pra revisar antes do dia, e prefere resolver qualquer
   choque de agenda manualmente no dia (árbitro chama a próxima equipe se a anterior estiver
   competindo em outro lugar) em vez de o sistema bloquear a geração adiantada. Removida a função,
   a constante, a chamada em `gerar_chaveamento_confronto`, o `try/except` que a engolia em
   `db/seed.py::seed_rodadas` (virou dead code) e a exceção correspondente em
   `test_seed.py::_qtd_rodadas_esperada_no_seed`; o teste que provava o bloqueio virou o teste que
   prova o oposto (`test_gerar_chaveamento_confronto_permite_sumo_rc_mesmo_com_sumo_em_andamento`).
   Se esse tipo de conflito de agenda (duas modalidades competindo pelo mesmo robô/equipe ao
   mesmo tempo) precisar de alguma ajuda de sistema no futuro, é feature nova (ex.: aviso, não
   bloqueio) — não reintroduzir a trava antiga.

   **Ajustes de véspera (28/08/2026, véspera do evento)**: (1) grupos do Cabo de Guerra
   reduzidos de 4-5 pra 3-4 equipes por chave (76 → 54 partidas) — coordenador achou o total
   grande demais; grupo de 3 é o mínimo que ainda garante "pelo menos 2 jogos por equipe", Sumô
   já estava nesse tamanho e não mudou. (2) Rodadas de todas as 4 modalidades individuais
   geradas de uma vez (`POST /rodadas/gerar`) — Resgate no Plano/Alto Risco/Viagem também
   tiveram `qtd_rodadas` reduzido de 3 pra 2 e `consolidacao` trocada pra `SOMA_RODADAS` (nota
   final = soma das duas), igualando à Dança. (3) Criadas as 22 contas de staff reais a partir
   de `pessoas.csv` (16 `ARBITRO`/"Juiz", 6 `COORDENADOR`/"Admin"), senha inicial `tjr2026` pra
   todo mundo — a conta seed (`admin@tjr.app`) segue existindo à parte.

   **Regra inviolável 10 removida** (arena obrigatória pra lançamento em modalidade INDIVIDUAL,
   `EQUIPE_SEM_ARENA_ATRIBUIDA` em `services/lancamento.py::criar_lancamento`) — pedido direto do
   coordenador na véspera: no ginásio real as arenas de uma modalidade são fisicamente
   equivalentes, então a distinção "equipe tem arena atribuída nesta rodada" não carrega
   informação nenhuma pra ele, só trava o card de pontuar sem necessidade. Removida a validação
   no backend (teste que provava o bloqueio virou
   `test_criar_lancamento_individual_funciona_mesmo_sem_arena_atribuida`, provando o oposto) e a
   UI de bloqueio em `PontuarPage.tsx` — o card agora é **sempre** clicável; se existir
   `Agendamento` pra aquela equipe/rodada, a arena/horário aparece como informação extra (não
   mais como pré-requisito). **Decisão consciente de escopo**: não removi o resto do sistema de
   arena/agendamento (models, migrations, tela "Horários", geração automática de horário) — só a
   trava de bloqueio no fluxo de pontuar. Ficou como recurso morto/opcional, não uma regra
   quebrada; se um dia fizer sentido tirar essa tela também, é decisão nova.

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

   **Pós-TJR 2026: chaveamento de combate 100% manual + lata girada no Resgate de Alto Risco**
   (05/10/2026). Feedback do coordenador depois do evento: o chaveamento vai ser montado fora do
   sistema (ChatGPT) e populado na mão, então **toda geração automática de combate saiu**:
   `gerar_chaveamento_inicial`, `gerar_chaveamento_confronto` (e `POST /chaveamento/gerar`),
   `gerar_fase_de_grupos` (e `POST .../fase-de-grupos/gerar`), `avancar_se_rodada_completa`
   (fechar partida eliminatória não cria mais a próxima rodada), o round-robin de
   `rodada.gerar_rodadas` (agora recusa `CONFRONTO` com `422 GERAR_RODADAS_SO_INDIVIDUAL`, só
   cria rodadas vazias de individual) e a geração de combate no seed e no `AbrirEventoModal`
   (que agora só lista individuais). `criar_partida_manual` ganhou `rodada_numero` e
   `formato_chaveamento` obrigatórios (antes a rodada era calculada e não dava pra abrir rodada
   2+ de mata-mata na mão); a mesma equipe pode jogar em rodadas diferentes, só não duas vezes na
   mesma. Chave virou só rótulo: partida de fase de grupos herda `chave_id` sozinha quando as duas
   equipes estão na mesma `Chave` da modalidade; eliminatória nunca carrega chave; bye só em
   eliminatória (`422 BYE_SO_EM_ELIMINATORIA`). `FaseDeGruposBuilder` ficou só com criar
   chave/distribuir equipe/classificação; `ChaveamentoManualBuilder` ganhou campos **Rodada**
   (default = última rodada existente) e **Tipo**; os dois botões aparecem em toda modalidade de
   combate. `LIMITE_EQUIPES_TODOS_CONTRA_TODOS` mudou pra `consolidacao.py` (só prévia de
   classificação de nível sem partida). `scripts/dados_teste/pontuar_simulacao.py` ainda chama o
   gerador antigo — script de simulação obsoleto, não atualizado.

   Ficha do Resgate de Alto Risco ganhou `"Objeto lata girado"` (`BOOLEANO`, +50), separado do
   `"invertido"` — soma se o árbitro marcar os dois. Só no seed: produção ainda tem a ficha
   publicada antiga (ficha publicada é imutável → aplicar lá exige nova versão).

   Outros feedbacks do evento, **ainda não implementados**: corrigir combate decidido errado
   pelo árbitro (hoje não tem tela; endpoint de correção existe no backend) e marcar presença da
   equipe antes de montar o chaveamento.

