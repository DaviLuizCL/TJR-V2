# HISTORIAS.md — Backlog de user stories

Lista de trabalho pra fechar o projeto. Cada história vira uma tarefa: eu leio, tiro dúvida se
tiver algo ambíguo, implemento em TDD (teste vermelho → código → teste verde), te mostro rodando
e a gente risca.

Preencha uma seção por história, nessa ordem de prioridade (a primeira é a próxima que eu pego).
Não precisa formalismo — só dá pra descrever o suficiente pra eu não ter que adivinhar regra de
negócio (nome de campo, quem pode fazer o quê, o que acontece no erro). Se não souber um detalhe
ainda, escreve "não sei, decide você" ou deixa em aberto que eu pergunto na hora.

Todas as fichas de modalidade estão disponiveis na raiz do projeto em uma pasta identificada, você pode olhar lá pra verificar qualquer coisa, ou me perguntar.

Sobre as arenas: Nas modalidades individuais, as arenas podem ser separadas por nível e dificuldade, sendo sorteadas no inicio das rodadas. Lembrando, se houver diferenciação de arena fácil, média e dificil, cada equipe deve rodar em cada uma das arenas disponíveis. Cada modalidade individual tem 3 rodadas, sendo excluída da soma a de menor valor, com exceção da dança que tem 2 rodadas e as duas se somam.
---

## Status

- [ ] Pendente
- [~] Em andamento
- [x] Feito

---

## 1. <título MODALIDADES DE COMBATE - CABO DE GUERRA - SUMÔ - CORRIDA DE CARROS AUTÔNOMOS .>

**Status:** Feito

**Como** <coordenador, juiz>
**Quero** <Escolher Visualizar os combates separados em rodadas, de forma bem visual, fazer a pontuação que será descrita a posteriori>
**Para** <Que no momento da competição, não tenhamos problemas com pontuação sumindo.>

Detalhes / regra de negócio (se tiver):
- Poder escolher se vai ser mata-mata ou todos contra todos(Apenas Coordenador)
- Só alterar o tipo de competição(mata-mata ou todos contra todos) caso nenhum combate tenha sido publicado ainda
- Auditoria no PDF -> Preciso conseguir gerar o ranking geral bem como todas as submissões para eventual auditoria
- Informações visuais se o envio deu certo, se deu erro, e informações visuais, como um caminho mesmo, no caso das modalidades de combate

Critério de aceite (como eu sei que ficou pronto):
- Gerado os embates, simulado uma luta, ver se as equipes que perderam ou ganharam seguiram o caminho correto dependendo do seu modo (mata mata ou todos contra todos)
- A Auditoria em PDF bate exatamente com o que foi publicado nas submissões
---
## 2. <título MODALIDADES DE COMBATE - CABO DE GUERRA>

**Status:** Feito

**Como** <juiz>
**Quero** <Escolher Visualizar os combates separados em rodadas, de forma bem visual>

**Para** <Que no momento da competição, não tenhamos problemas com pontuação sumindo.>

Detalhes / regra de negócio (se tiver):
- O cabo de guerra funciona da seguinte forma: os resultados do embate podem ser FOSSO(+2 pontos para quem puxou) Arraste Parcial(+1 ponto para quem puxou), Empate(+1 ponto para os 2), Nulo(0 pontos para os 2), quem finalizar os 3 embates com maior pontuação, vence e fica a mercê do esquema da modalidade, mata mata ou todos contra todos.

Critério de aceite (como eu sei que ficou pronto):
- Gerado os embates, simulado uma luta, ver se as equipes que perderam ou ganharam seguiram o caminho correto dependendo do seu modo (mata mata ou todos contra todos)
- A Auditoria em PDF bate exatamente com o que foi publicado nas submissões
---
## 3. <título MODALIDADES DE COMBATE - Sumô>

**Status:** Feito

**Como** <juiz>
**Quero** <Escolher Visualizar os combates separados em rodadas, de forma bem visual>

**Para** <Que no momento da competição, não tenhamos problemas com pontuação sumindo.>

Detalhes / regra de negócio (se tiver):
- O Sumô funciona da seguinte forma: os resultados do embate podem ser Ippon, que significa que o oponente foi tirado da arena em menos de 30 segundos(+2 pontos para quem fez) Waza-ari, que significa que o oponente foi tirado da arena em mais de 30 segundos(+1 ponto para quem fez), Empate(+1 ponto para os 0), quem finalizar os 3 embates com maior pontuação, vence a rodada e fica a mercê do esquema da modalidade, mata mata ou todos contra todos.

Critério de aceite (como eu sei que ficou pronto):
- Gerado os embates, simulado uma luta, ver se as equipes que perderam ou ganharam seguiram o caminho correto dependendo do seu modo (mata mata ou todos contra todos)
- A Auditoria em PDF bate exatamente com o que foi publicado nas submissões
---
## 4. <título MODALIDADES DE COMBATE - Corrida de carros autônomos>

**Status:** Feito — ficha com os 6 campos da ficha oficial (Evitar a colisão,
as 4 violações de derrota automática, Carro que ficou na frente). Cai no
formulário genérico de ficha (mais de 1 critério), não no fluxo rápido de
1 clique.

**Como** <juiz>
**Quero** <Escolher Visualizar os combates separados em rodadas, de forma bem visual>

**Para** <Que no momento da competição, não tenhamos problemas com pontuação sumindo.>

Detalhes / regra de negócio (se tiver):
- A corrida de carros autônomos funciona da seguinte forma: Serão 3 corridas por rodada. Sobre as pontuações: Evitar Colisão(+1 ponto para cada vez que acontecer para a equipe que evitou) Colisão com a parte traseira do outro(A equipe que colidiu perde automaticamente a corrida), Evasão da pista( A equipe que evadiu perde automaticamente a corrida), Posicionamento Transversal(A equipe que fez isso perde automaticamente a corrida), Percurso em sentido contrário(A equipe que fez isso perde automaticamente a corrida) Carro ficou na frente(Em outras palavras, o carro que venceu a corrida, quando for marcada, a equipe vence automaticamente).

Critério de aceite (como eu sei que ficou pronto):
- Gerado os embates, simulado uma luta, ver se as equipes que perderam ou ganharam seguiram o caminho correto dependendo do seu modo (mata mata ou todos contra todos)
- A Auditoria em PDF bate exatamente com o que foi publicado nas submissões
---


## 5. <título MODALIDADES INDIVIDUAIS - Resgate no Plano, Resgate de Alto Risco, Dança e Viagem ao Centro da Terra>

**Status:** Feito — fichas das 4 modalidades já batiam com os PDFs oficiais (conferido
critério a critério, nada precisou mudar) e o relatório de auditoria em PDF já era genérico
por `tipo_disputa` (funciona pra individual sem trabalho extra). O que faltava de verdade era
a estimativa de horário: `services/agendamento.py::estimar_horarios` + rota
`GET /agendamentos/estimativa?modalidade_id=`, consumida pela aba Horários
(`HorarioPage.tsx`), que substitui silenciosamente o horário planejado de cada bateria ainda
não pontuada pelo horário reprojetado (sem badge de atraso, só o valor mostrado muda) — ver
seção 12 pra detalhe do algoritmo.

**Como** <juiz>
**Quero** <Escolher Visualizar os combates separados em rodadas, de forma bem visual>

**Para** <Que no momento da competição, não tenhamos problemas com pontuação sumindo.>

Detalhes / regra de negócio (se tiver):
- As pontuações estão presentes nos PDFS das fichas, vide para pegar a pontuação.

Critério de aceite (como eu sei que ficou pronto):
- Gerado as rodadas, cada rodada deve acontecer no horário estipulado, retornando uma estimativa de quanto tempo cada bateria está demorando pra acontecer, levando em consideração tempo máximo de rodada + tempo de pausa.
- A Auditoria em PDF bate exatamente com o que foi publicado nas submissões
---




<!-- Copia o bloco "## N. <título>" acima pra cada história nova. Quando terminar de preencher,
me avisa aqui na conversa (não precisa colar o conteúdo, eu leio o arquivo direto). -->
