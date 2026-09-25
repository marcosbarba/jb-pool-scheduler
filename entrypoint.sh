#!/bin/sh
set -e

# Exportar variables de entorno para que cron las reconozca
printenv | grep -Ev '^(PATH|PWD|SHLVL|_)' > /etc/environment

# Eliminar retornos de carro de Windows (\r) y forzar un salto de línea final
tr -d '\r' < /app/crontab.txt > /tmp/crontab_clean.txt
echo "" >> /tmp/crontab_clean.txt

# Instalar el crontab saneado
crontab /tmp/crontab_clean.txt

echo "Pool Scheduler iniciado. Cron operativo en zona horaria: $TZ"

# Iniciar cron en primer plano
exec cron -f