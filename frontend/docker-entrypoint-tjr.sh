#!/bin/sh
set -e

CERT="/etc/nginx/certs/live/tjr.pontuai.online/fullchain.pem"

if [ -f "$CERT" ]; then
    echo "[tjr] certificado encontrado ($CERT) -- servindo HTTPS"
    cp /etc/nginx/nginx.https.conf /etc/nginx/conf.d/default.conf
else
    echo "[tjr] sem certificado ainda ($CERT) -- servindo HTTP puro"
    cp /etc/nginx/nginx.http.conf /etc/nginx/conf.d/default.conf
fi

exec /docker-entrypoint.sh "$@"
