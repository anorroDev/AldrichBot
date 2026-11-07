# AldrichBot
В разработке


## Сервер

Бот работает на виртуалке Azure (той же, что и телеграм-бот) отдельной службой `dsbot`.
Нужен файл `.env` со строкой `BOT_TOKEN=…` (в git не попадает) и Azure CLI (`az login`).

```bash
bash deploy/azure.sh deploy   # залить код из этой папки и перезапустить бота
bash deploy/azure.sh logs     # логи
bash deploy/azure.sh status   # статус и память сервера
```

На сервере: `/opt/dsbot/app` — код, `/opt/dsbot/data/mybot.db` — база (деплой её не трогает),
`/opt/dsbot/backups` — копия базы раз в сутки, хранятся 14. Веб-заглушка `keep_alive` (Flask для
UptimeRobot) запускается только на Render — на своём сервере бот и так работает 24/7.
