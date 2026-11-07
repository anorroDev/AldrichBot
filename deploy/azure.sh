#!/usr/bin/env bash
# Развёртывание Discord-бота AldrichBot на виртуалку Azure (та же VM, что и у телеграм-бота).
#
#   bash deploy/azure.sh deploy   — залить код из этой папки + .env и перезапустить бота
#   bash deploy/azure.sh logs     — последние строки логов бота
#   bash deploy/azure.sh status   — статус службы и память сервера
#
# На сервере бот — отдельная служба dsbot со своим пользователем: /opt/dsbot/app — код,
# /opt/dsbot/data — база (обновление кода её не трогает), /opt/dsbot/backups — копии базы.
# Первый запуск: база берётся из локального mybot.db; потом живую базу деплой не перезаписывает.
# Входящие порты на VM закрыты: управление через `az vm run-command`.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash на Windows: не превращать /opt/... в C:\...

RG="${AZ_RG:-tgbot-rg}"
VM="${AZ_VM:-tgbot-vm}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# az — Windows-программа, ей нужны Windows-пути к файлам.
winpath() { command -v cygpath >/dev/null && cygpath -w "$1" || echo "$1"; }

run_remote() {  # $1 — путь к shell-скрипту, выполняется на VM от root
  az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript \
    --scripts "@$(winpath "$1")" --query "value[0].message" -o tsv
}

cmd_deploy() {
  grep -q '^BOT_TOKEN=.' .env 2>/dev/null || { echo "Нет файла .env со строкой BOT_TOKEN=токен_Discord"; exit 1; }
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  local pkg db=""
  pkg="$(tar --exclude=__pycache__ --exclude='*.db' -czf - main.py keep_alive.py cogs misc requirements.txt | base64 -w0)"
  [ -f mybot.db ] && db="$(gzip -c mybot.db | base64 -w0)"
  local env_b64; env_b64="$(tr -d '\r' < .env | base64 -w0)"

  # Run Command выполняет скрипт через /bin/sh (dash) — без bash-специфики.
  cat > "$tmp/remote.sh" <<EOF
set -eu
export DEBIAN_FRONTEND=noninteractive
APP=/opt/dsbot
dpkg -s python3-venv >/dev/null 2>&1 || { apt-get update -q && apt-get install -y -q python3-venv; }
id dsbot >/dev/null 2>&1 || useradd --system --home-dir \$APP --shell /usr/sbin/nologin dsbot
mkdir -p \$APP/data \$APP/backups

# Код целиком заменяем свежим (база — отдельно, в data/).
rm -rf \$APP/app && mkdir -p \$APP/app
echo '$pkg' | base64 -d | tar -xzf - -C \$APP/app
printf '%s\n' '$env_b64' | base64 -d > \$APP/.env
chmod 600 \$APP/.env

# База — только при первом запуске: живую никогда не перезаписываем.
if [ ! -f \$APP/data/mybot.db ]; then
  if [ -n '$db' ]; then echo '$db' | base64 -d | gunzip > \$APP/data/mybot.db && echo "db: из локального mybot.db"
  else echo "db: новая пустая"; fi
fi

[ -d \$APP/.venv ] || python3 -m venv \$APP/.venv
\$APP/.venv/bin/pip install -q --upgrade pip
\$APP/.venv/bin/pip install -q -r \$APP/app/requirements.txt
chown -R dsbot:dsbot \$APP

# Копия базы раз в сутки, хранятся последние 14 (sqlite backup — согласованный снимок на ходу).
cat > /etc/cron.d/dsbot-backup <<'CRON'
40 3 * * * dsbot cd /opt/dsbot && .venv/bin/python -c "import sqlite3,datetime; s=sqlite3.connect('data/mybot.db'); d=sqlite3.connect('backups/mybot-%s.db' % datetime.date.today()); s.backup(d); d.close()" && ls -1t backups/mybot-*.db | tail -n +15 | xargs -r rm -f
CRON

cat > /etc/systemd/system/dsbot.service <<'UNIT'
[Unit]
Description=Discord bot AldrichBot
After=network-online.target
Wants=network-online.target

[Service]
User=dsbot
# Рабочая папка — data: бот открывает mybot.db по относительному пути.
WorkingDirectory=/opt/dsbot/data
EnvironmentFile=/opt/dsbot/.env
ExecStart=/opt/dsbot/.venv/bin/python /opt/dsbot/app/main.py
Restart=always
RestartSec=5
# На VM всего 1 ГБ: если у Discord-бота «потечёт» память, пусть упадёт он сам, а не телеграм-бот
# рядом (systemd его тут же перезапустит).
MemoryMax=350M

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable -q dsbot
systemctl restart dsbot
sleep 15
echo "status: \$(systemctl is-active dsbot)"
journalctl -u dsbot -n 15 --no-pager -o cat
EOF
  run_remote "$tmp/remote.sh"
}

cmd_logs() {
  local tmp; tmp="$(mktemp)"
  echo "journalctl -u dsbot -n ${1:-50} --no-pager -o short-iso" > "$tmp"
  run_remote "$tmp"; rm -f "$tmp"
}

cmd_status() {
  local tmp; tmp="$(mktemp)"
  echo "systemctl status dsbot --no-pager | head -n 12; echo; free -m" > "$tmp"
  run_remote "$tmp"; rm -f "$tmp"
}

case "${1:-}" in
  deploy) cmd_deploy ;;
  logs)   cmd_logs "${2:-50}" ;;
  status) cmd_status ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
