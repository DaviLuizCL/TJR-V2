# Deploy — como mexer no servidor de produção (EC2)

Este projeto roda em produção num servidor EC2 separado do seu ambiente de
desenvolvimento local. Este guia explica como qualquer notebook seu consegue
se conectar nele e como fazer o deploy de uma mudança.

## Dados do servidor

- **Endereço**: `tjr.pontuai.online` (também responde pelo IP direto, mas o
  domínio é mais estável)
- **Usuário SSH**: `ec2-user`
- **Chave**: `tjr-2026.pem` — é a chave privada, dá acesso total ao servidor.
  **Nunca** faça commit dela no git, nunca mande por e-mail/chat em texto
  puro. Transfira só por canal seguro (AirDrop, pen drive, `scp` entre suas
  próprias máquinas, ou um gerenciador de senhas com anexo).
- **Repo no servidor**: `/home/ec2-user/TJR-V2`

## 1. Configurar um notebook novo

Copie o arquivo `tjr-2026.pem` pra dentro de `~/.ssh/` do notebook novo (por
qualquer canal seguro dos listados acima), depois:

```bash
chmod 400 ~/.ssh/tjr-2026.pem
```

Adicione isso ao final do seu `~/.ssh/config` (crie o arquivo se não existir):

```
Host tjr-ec2
  HostName tjr.pontuai.online
  User ec2-user
  IdentityFile ~/.ssh/tjr-2026.pem
  IdentitiesOnly yes
```

Teste:

```bash
ssh tjr-ec2
```

Se conectar sem pedir senha, está pronto. (Nesta máquina aqui — a que o
Claude Code está usando — esse atalho já está configurado.)

## 2. Deploy de uma mudança de código

O fluxo é sempre: você desenvolve/testa local → sobe pro GitHub → o servidor
puxa do GitHub.

```bash
# 1. No seu ambiente local, commitar e enviar
git add <arquivos>
git commit -m "sua mensagem"
git push origin main

# 2. No servidor, puxar e reconstruir
ssh tjr-ec2
cd TJR-V2
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 3. Se teve migration nova (mudança de model/tabela)
docker compose exec -T api alembic upgrade head
```

`docker compose` aqui **não precisa de `sudo`** — o usuário `ec2-user` já
está no grupo `docker`.

O front detecta sozinho se existe certificado HTTPS
(`/etc/letsencrypt/live/tjr.pontuai.online/`, já configurado nesse servidor)
e sobe em HTTPS automaticamente — não precisa fazer nada extra com isso.

## 3. Substituir o banco de produção pelo do seu ambiente local

Use isso quando você ajustou dado (equipes, chaveamento, etc.) no seu
ambiente local e quer que o servidor fique **exatamente igual**. Isso
**apaga tudo que está no banco do servidor** e coloca uma cópia do seu banco
local no lugar — só faça isso se tiver certeza que o servidor não tem
nenhuma pontuação real registrada que você queira manter (confira antes:
`select count(*) from lancamento;` deve ser 0, ou você vai perder pontuação
de verdade).

```bash
# 1. No seu ambiente local: gerar o dump
docker compose exec -T db pg_dump -U tjr -d tjr --data-only --disable-triggers -F c > /tmp/tjr_data.dump

# 2. Enviar pro servidor
scp -i ~/.ssh/tjr-2026.pem /tmp/tjr_data.dump tjr-ec2:/tmp/tjr_data.dump
# (com o Host configurado no ~/.ssh/config, dá pra usar so "tjr-ec2:/tmp/..." mesmo sem repetir -i)

# 3. No servidor: recriar o banco do zero e restaurar
ssh tjr-ec2
cd TJR-V2
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
cd TJR-V2
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

## 4. Comandos úteis do dia a dia

```bash
ssh tjr-ec2 "cd TJR-V2 && docker compose ps"                    # ver status
ssh tjr-ec2 "cd TJR-V2 && docker compose logs api --tail 50"    # logs da api
ssh tjr-ec2 "cd TJR-V2 && docker compose logs front --tail 50"  # logs do front
ssh tjr-ec2 "cd TJR-V2 && docker compose exec -T db psql -U tjr -d tjr -c 'SELECT ...'"  # consultar o banco direto
```

## 5. O que NÃO fazer

- Não rode `docker compose up` (sem `-f docker-compose.prod.yml`) no
  servidor — isso troca pro modo dev e derruba o acesso público.
- Não apague `/etc/letsencrypt` nem mexa nos arquivos de certificado —
  quem renova é o certbot do próprio host, fora do docker.
- Não faça commit de `tjr-2026.pem`, `.env`, `pessoas.csv`,
  `saida_credenciais.csv` ou qualquer planilha de equipe real — todos já
  estão no `.gitignore`, mas confira antes de qualquer `git add` mais amplo.
