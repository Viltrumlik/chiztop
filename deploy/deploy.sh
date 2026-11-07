#!/usr/bin/env bash
# Kodni serverga yuboradi va xizmatni qayta ishga tushiradi.
# Birinchi o'rnatish uchun emas -- avval deploy/README.md.
set -euo pipefail

HOST="${1:?ishlatish: ./deploy/deploy.sh user@host [/opt/chiztop]}"
DIR="${2:-/opt/chiztop}"

echo "-> $HOST:$DIR ga yuborilmoqda"
rsync -az --delete \
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
    --exclude '.pytest_cache' --exclude '.env' --exclude '.claude' \
    ./ "$HOST:$DIR/"

echo "-> bog'liqliklar"
ssh "$HOST" "cd $DIR && .venv/bin/pip -q install -r requirements.txt"

echo "-> qayta ishga tushirish"
ssh "$HOST" "sudo systemctl restart chiztop"

echo "-> sog'liq tekshiruvi"
ssh "$HOST" "curl -sf http://127.0.0.1:8077/health" && echo "  OK"
