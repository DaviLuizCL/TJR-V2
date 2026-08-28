# Estagio dev: vite dev server com hot reload, codigo montado como volume
# pelo docker-compose.yml (ver `target: dev` la). E o estagio usado no dia a
# dia de desenvolvimento.
FROM node:20-slim AS dev

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]

# Estagio build: compila o bundle estatico de producao (tsc + vite build).
# Sem VITE_API_URL no ambiente de build, o front chama a API por caminho
# relativo (/api/v1/...) - funciona atras do proxy reverso do nginx
# (estagio prod abaixo), em qualquer host/IP, sem precisar fixar endereco
# nenhum na imagem.
FROM node:20-slim AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# Estagio prod (default do build, sem --target): nginx servindo o bundle
# estatico + proxy reverso de /api/ pra dentro da rede docker, pro servico
# `api`. E o estagio usado pelo docker-compose.prod.yml.
#
# nginx.https.conf x nginx.http.conf: o entrypoint decide na hora de subir
# (ver docker-entrypoint-tjr.sh) qual dos dois vira o default.conf de
# verdade, checando se o certificado do Let's Encrypt ja existe no volume
# montado em /etc/nginx/certs. Sem isso, subir num servidor sem certificado
# ainda emitido derruba o nginx inteiro (ssl_certificate apontando pra
# arquivo inexistente e erro fatal de configuracao, nao so um warning).
FROM nginx:1.27-alpine AS prod

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.https.conf /etc/nginx/nginx.https.conf
COPY nginx.http.conf /etc/nginx/nginx.http.conf
COPY docker-entrypoint-tjr.sh /docker-entrypoint-tjr.sh
RUN chmod +x /docker-entrypoint-tjr.sh

EXPOSE 80 443

ENTRYPOINT ["/docker-entrypoint-tjr.sh"]
CMD ["nginx", "-g", "daemon off;"]
