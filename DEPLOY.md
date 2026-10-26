# Deploy — como mexer no servidor de produção (VM em Patos)

Desde 19/10/2026 o sistema roda numa VM Ubuntu emprestada por um dev de Patos
(o EC2 antigo morreu em 10/10/2026). Este guia explica como entrar nela e como
fazer o deploy de uma mudança.

## Dados do servidor

- **Endereço do app**: `https://tjr.pontuai.online`, via **Cloudflare Tunnel**
  (o DNS do `pontuai.online` está na Cloudflare; o domínio continua registrado
  na Hostinger). Não existe porta aberta na rede da VM: o HTTPS é da própria
  Cloudflare, sem certbot/Let's Encrypt.
- **Máquina**: Ubuntu 24.04, 2 CPUs, 3,8 GB de RAM, sem swap (vale criar 2 GB),
  usuário `dev` (grupo `docker`, `sudo` sem senha).
- **Repo no servidor**: `/home/dev/TJR-V2` (clone HTTPS do GitHub, repo público).
- **Acesso**: **não tem SSH direto**. A VM expõe um terminal web (ttyd) por um
  túnel rápido `*.trycloudflare.com`, e esse link **muda sempre que a VM ou o
  túnel reinicia** — quem passa o link novo é o dev de Patos. Login: usuário
  `dev` + senha que ele passou (não fica neste repo, que é público).

## 1. Como o app chega na internet

O túnel do app é um serviço do sistema e volta sozinho no boot:

- serviço `cloudflared` (`systemctl status cloudflared`), config em
  `/etc/cloudflared/config.yml` (túnel `tjr`, `tjr.pontuai.online` →
  `http://localhost:80`) e credencial `/etc/cloudflared/<id>.json`;
- o certificado de conta (`~/.cloudflared/cert.pem`) também ficou na VM e dá
  poder de criar/apagar túneis no `pontuai.online`.

O terminal web é outro serviço, montado pelo dev de Patos
(`ttyd.service` + `cloudflared-terminal.service`). Não misturar os dois.

Os containers sobem sozinhos no boot (`restart: unless-stopped`).

## 2. Deploy de uma mudança de código

O fluxo é sempre: você desenvolve/testa local → sobe pro GitHub → o servidor
puxa do GitHub.

```bash
# 1. No seu ambiente local, commitar e enviar
git add <arquivos>
git commit -m "sua mensagem"
git push origin main

# 2. No terminal web da VM, puxar e reconstruir
cd ~/TJR-V2
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Se teve migration nova (mudança de model/tabela)
docker compose exec -T api alembic upgrade head
```

`alembic` e `python` rodam **dentro** do container (`docker compose exec -T api ...`),
não no host: não instale `alembic` pelo apt.

Banco novo do zero (foi o caso em 19/10/2026): depois do `up -d --build`, rodar
`alembic upgrade head` e `python -m app.db.seed --apenas-estrutura` (evento, modalidades,
fichas e o `admin@tjr.app`, sem equipe fictícia).

## 2b. Deploy pelo GitHub (sem precisar do terminal web)

Desde 26/10/2026 a VM tem um runner do GitHub Actions (nome `vm-patos`, rótulo `tjr-vm`,
pasta `~/actions-runner`, roda como serviço do `dev`). Ele só faz conexão de saída pro
GitHub, então não depende do link do ttyd. O workflow é `.github/workflows/deploy.yml`:

- **Automático**: todo push na `main` faz `git pull` + `up -d --build` + `alembic upgrade
  head` na VM e confere `http://localhost/api/v1/health`.
- **Manual**: GitHub → aba **Actions** → **Deploy** → **Run workflow** (dá pelo celular).

O repositório é público: a política de Actions exige aprovação pra workflow de qualquer
colaborador externo (`all_external_contributors`). Não mude isso, senão um pull request
de estranho poderia rodar comando na VM.

Instalar de novo (VM nova ou runner quebrado), no terminal web, como `dev`. O `TOKEN` sai
de GitHub → Settings → Actions → Runners → New self-hosted runner (vale 1 hora):

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -fsSL -o runner.tgz https://github.com/actions/runner/releases/download/v2.338.2/actions-runner-linux-x64-2.338.2.tar.gz
tar xzf runner.tgz
./config.sh --unattended --url https://github.com/DaviLuizCL/TJR-V2 --token TOKEN --name vm-patos --labels tjr-vm --replace
sudo ./svc.sh install dev && sudo ./svc.sh start
```

Ver se está vivo: `sudo ./svc.sh status` (na pasta) ou GitHub → Settings → Actions →
Runners (tem que estar "Idle").

## 3. Substituir o banco de produção pelo do seu ambiente local

Use isso quando você ajustou dado (equipes, chaveamento, etc.) no seu
ambiente local e quer que o servidor fique **exatamente igual**. Isso
**apaga tudo que está no banco do servidor** e coloca uma cópia do seu banco
local no lugar — só faça isso se tiver certeza que o servidor não tem
nenhuma pontuação real registrada que você queira manter (confira antes:
`select count(*) from lancamento;` deve ser 0, ou você vai perder pontuação
de verdade).

Sem SSH não tem `scp`: o arquivo do dump precisa chegar na VM por outro caminho
(ex.: link de download temporário e `curl -o` no terminal web).

```bash
# 1. No seu ambiente local: gerar o dump
docker compose exec -T db pg_dump -U tjr -d tjr --data-only --disable-triggers -F c > /tmp/tjr_data.dump

# 2. Levar o arquivo pra VM em /tmp/tjr_data.dump

# 3. Na VM: recriar o banco do zero e restaurar
cd ~/TJR-V2
docker compose stop api
docker compose exec -T db psql -U tjr -d postgres -c "DROP DATABASE tjr;"
docker compose exec -T db psql -U tjr -d postgres -c "CREATE DATABASE tjr OWNER tjr;"
docker compose start api
sleep 3
docker compose exec -T api alembic upgrade head   # recria as tabelas vazias
docker compose stop api
docker cp /tmp/tjr_data.dump $(docker compose ps -q db):/tmp/tjr_data.dump
docker compose exec -T db pg_restore -U tjr -d tjr --data-only --disable-triggers /tmp/tjr_data.dump
docker compose start api
rm -f /tmp/tjr_data.dump
```

Um erro de `duplicate key ... alembic_version_pkc` no `pg_restore` é normal
e inofensivo (a tabela de controle de migration já estava certa) — os dados
de verdade (equipe, inscrição, rodada, partida, etc.) restauram normalmente.

## 3b. Restaurar um backup baixado pelo painel

O botão **Administração → Baixar backup** gera um arquivo `tjr-backup-AAAA-MM-DD-HHMM.dump`
(formato custom do `pg_dump` 17). Pra restaurar, use o `pg_restore` **do container `api`**
(versão 17). O `pg_restore` do container `db` é versão 16 e recusa esse arquivo com
`unsupported version (1.16) in file header`.

Isso **apaga o banco atual** e põe o backup no lugar. Mesmos cuidados da seção 3.

```bash
cd ~/TJR-V2
docker compose stop api
docker compose exec -T db psql -U tjr -d postgres -c "DROP DATABASE tjr;"
docker compose exec -T db psql -U tjr -d postgres -c "CREATE DATABASE tjr OWNER tjr;"
docker compose start api
docker cp tjr-backup-XXXX.dump $(docker compose ps -q api):/tmp/backup.dump
docker compose exec -T api sh -c 'PGPASSWORD=$(python3 -c "from sqlalchemy.engine import make_url;import os;print(make_url(os.environ[\"DATABASE_URL\"]).password)") pg_restore -h db -U tjr -d tjr /tmp/backup.dump; rm /tmp/backup.dump'
docker compose restart api
```

O erro `unrecognized configuration parameter "transaction_timeout"` no `pg_restore` é
normal e inofensivo: o 17 manda um parâmetro que o servidor 16 não conhece. O resto
restaura normalmente (testado em 10/10/2026: contagens e versão da migration batem).

## 4. Comandos úteis do dia a dia (no terminal web, dentro de `~/TJR-V2`)

```bash
docker compose ps                    # ver status
docker compose logs api --tail 50    # logs da api
docker compose logs front --tail 50  # logs do front
docker compose exec -T db psql -U tjr -d tjr -c 'SELECT ...'  # consultar o banco direto
docker stats --no-stream             # memória/CPU por container
systemctl status cloudflared         # túnel do app
```

## 5. O que NÃO fazer

- Não rode `docker compose up` (sem `-f docker-compose.prod.yml`) no
  servidor — isso troca pro modo dev e derruba o acesso público.
- Não pare nem desinstale o serviço `cloudflared` (o do app) nem o
  `cloudflared-terminal`/`ttyd` (o do terminal): sem o primeiro o site some,
  sem o segundo ninguém entra na VM.
- Não crie hostname público pro terminal (porta 7681) no túnel do app sem
  proteger com Cloudflare Access — ele dá acesso total à máquina.
- Não faça commit de `.env`, `pessoas.csv`, `saida_credenciais.csv`, senha da
  VM, token de túnel ou qualquer planilha de equipe real — o repo é público.
