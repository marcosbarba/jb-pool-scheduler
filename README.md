# JB Pool Scheduler 🏊‍♂️⚡

Sistema integral y automatizado para la optimización energética y control domótico de bombas de depuración de piscinas.

El sistema calcula de forma dinámica las horas de filtración requeridas a partir de la temperatura media del agua (media de la mínima y la máxima del día) (sonda en Tuya/Smart Life), selecciona las franjas horarias más económicas del mercado regulado español (**PVPC / ESIOS de Red Eléctrica de España**), gestiona la conmutación física del relé y cuenta con protección activa antihielo basada en la temperatura exterior (estación meteorológica Netatmo).

---

## 🏗️ Arquitectura del Sistema

```
[20:45 CET Diariamente — planner.py]
   ├── 1. SQLite Storage     ───> Consulta la mínima y máxima del agua registradas hoy
   ├── 2. REE / ESIOS API    ───> Descarga los 24 precios PVPC para el día siguiente (D+1)
   ├── 3. Core Engine        ───> Heurística (horas requeridas) + Optimizador (franjas mínimas)
   ├── 4. SQLite Storage     ───> Persiste el horario óptimo en data/pool_schedule.db
   └── 5. Telegram Bot API   ───> Envía reporte detallado a los usuarios configurados

[Cada 5 minutos — executor.py]
   ├── 1. Self-Healing       ───> Verifica si hay plan para hoy; si falta, ejecuta plan de emergencia
   ├── 2. Muestreo Térmico   ───> Guarda lectura periódica de la sonda Tuya en SQLite
   ├── 3. Netatmo API        ───> Consulta temperatura exterior del aire
   │     └── Antifreeze Check: Si T_aire <= umbral, fuerza encendido (anula plan) y alerta por Telegram
   ├── 4. Tuya Cloud API     ───> Lee estado real del relé DIN (idempotencia)
   └── 5. Control & Notif.   ───> Conmuta la bomba solo si difiere y notifica eventos a Telegram
```

---

## 📋 Reglas de Dominio

### 1. Escala Heurística de Filtración (Agua)

Las horas diarias de depuración se determinan a partir de la temperatura media del agua, calculada como (mínima + máxima) / 2 del día. Cada temperatura de la tabla representa el intervalo $[T-0.5,\ T+0.5)$ (p. ej. 24 °C cubre $[23.5, 24.5)$):

| Temperatura del Agua ($T$) | Horas Asignadas |
| :--- | :--- |
| $T \ge 30.5^\circ\text{C}$ (> 30) | 12 h |
| $29.5 \le T < 30.5$ (30) | 11 h |
| $28.5 \le T < 29.5$ (29) | 10 h |
| $27.5 \le T < 28.5$ (28) | 8 h |
| $26.5 \le T < 27.5$ (27) | 7 h |
| $25.5 \le T < 26.5$ (26) | 6 h |
| $23.5 \le T < 25.5$ (24-25) | 5 h |
| $21.5 \le T < 23.5$ (22-23) | 4 h |
| $19.5 \le T < 21.5$ (20-21) | 3 h |
| $14.5 \le T < 19.5$ (15-19) | 2 h |
| $T < 14.5^\circ\text{C}$ (< 14) | 1 h |

### 2. Algoritmo de Optimización Horaria
1. Obtiene los 24 precios horarios del PVPC (mercado peninsular, `geo_id: 8741`).
2. Ordena los periodos por coste y extrae las $N$ horas más económicas.
3. Reordena cronológicamente y fusiona horas consecutivas adyacentes en intervalos continuos (`[start_hour, end_hour]`).

### 3. Protección Antihielo e Histéresis
* **Activación:** Si la temperatura del aire exterior (Netatmo) desciende hasta $\le \text{ANTIFREEZE\_TEMP\_THRESHOLD}$ (por defecto $0.0^\circ\text{C}$), se ignora el plan horario y la bomba se enciende continuamente. Se emite una alerta crítica por Telegram.
* **Recuperación:** La bomba regresa a la disciplina del plan económico únicamente cuando la temperatura sube por encima de $\ge \text{ANTIFREEZE\_TEMP\_HYSTERESIS}$ (por defecto $0.0^\circ\text{C}$), evitando ciclos intermitentes de encendido/apagado.

---

## 📁 Estructura del Proyecto

El código sigue el estándar **src-layout** (PEP 517/621):

```text
jb-pool-scheduler/
├── .env.example                # Plantilla de variables de entorno
├── .gitignore                  # Exclusiones de Git (secretos, venv, base de datos)
├── .dockerignore               # Exclusiones del contexto Docker
├── Dockerfile                  # Definición de contenedor con uv y cron
├── docker-compose.yml          # Servicio y montaje persistente de SQLite
├── crontab.txt                 # Tareas programadas (cron)
├── entrypoint.sh               # Normalización de variables y arranque del cron
├── pyproject.toml              # Definición de paquete y dependencias con uv
├── uv.lock                     # Lockfile reproducible de dependencias
├── data/                       # Almacén SQLite persistente
│   └── pool_schedule.db
├── src/
│   └── jb_pool_scheduler/
│       ├── __init__.py
│       ├── config.py           # Validación tipada con Pydantic Settings
│       ├── planner.py          # Planificador diario (20:45 CET)
│       ├── executor.py         # Orquestador y ejecutor periódico (c/5 min)
│       ├── clients/
│       │   ├── esios_client.py     # Cliente HTTP ESIOS (PVPC indicador 1001)
│       │   ├── netatmo_client.py   # API Netatmo con OAuth2 y refresco automático
│       │   ├── tuya_client.py      # Tuya OpenAPI (relé DIN y sensor térmico)
│       │   └── telegram_client.py  # Despacho de alertas y reportes multi-chat
│       ├── core/
│       │   ├── heuristic.py        # Mapeo térmico puro
│       │   └── optimizer.py        # Optimización y consolidación de tramos
│       └── storage/
│           └── repository.py       # Capa de persistencia SQLite
└── tests/                          # Batería de pruebas unitarias (pytest)
    ├── test_heuristic.py
    ├── test_optimizer.py
    ├── test_repository.py
    └── test_netatmo_client.py
```

---

## 🚀 Despliegue y Puesta en Marcha

### Prerrequisitos
* Docker y Docker Compose instalados en el host (Linux VPS o máquina local con WSL 2).
* Credenciales de acceso para:
  * **ESIOS / REE:** Token de consulta (solicitado a `consultasios@ree.es`).
  * **Tuya Developer Platform:** Proyecto Cloud con Access ID, Secret y los Device IDs del relé e interruptor.
  * **Netatmo Connect:** App con permisos `read_station`, Client ID, Secret, Refresh Token y MAC del módulo exterior.
  * **Telegram:** Bot generado con `@BotFather` y Chat ID(s) de los destinatarios.

### 1. Clonar y configurar variables de entorno

```bash
git clone https://github.com/<tu-usuario>/jb-pool-scheduler.git
cd jb-pool-scheduler
cp .env.example .env
```

Edita el archivo `.env` rellenando tus datos:

```env
TZ=Europe/Madrid
SQLITE_DB_PATH=data/pool_schedule.db

# REE / ESIOS API
ESIOS_API_TOKEN=tu_token_esios

# Tuya / Smart Life Cloud
TUYA_ACCESS_ID=tu_tuya_access_id
TUYA_ACCESS_SECRET=tu_tuya_access_secret
TUYA_ENDPOINT=https://openapi.tuyaeu.com
TUYA_PUMP_DEVICE_ID=tu_device_id_rele_bomba
TUYA_TEMP_DEVICE_ID=tu_device_id_sonda_agua

# Netatmo API (Protección Antihielo)
NETATMO_CLIENT_ID=tu_netatmo_client_id
NETATMO_CLIENT_SECRET=tu_netatmo_client_secret
NETATMO_REFRESH_TOKEN=tu_netatmo_refresh_token
NETATMO_STATION_MAC=xx:xx:xx:xx:xx:xx
ANTIFREEZE_TEMP_THRESHOLD=1.0
ANTIFREEZE_TEMP_HYSTERESIS=2.0

# Telegram Bot API (Soporta uno o múltiples IDs separados por comas)
TELEGRAM_BOT_TOKEN=tu_telegram_bot_token
TELEGRAM_CHAT_ID=123456789,987654321
TELEGRAM_NOTIFY_SWITCH_EVENTS=true
```

### 2. Compilar e iniciar el contenedor

```bash
docker compose up -d --build
```

### 3. Gestión y Monitoreo

* **Ver trazas y logs en tiempo real:**
  ```bash
  docker compose logs -f
  ```
* **Forzar ciclo de verificación de la bomba manualmente:**
  ```bash
  docker compose exec pool_scheduler uv run python -m jb_pool_scheduler.executor
  ```
* **Forzar generación manual del plan para un día concreto:**
  ```bash
  docker compose exec pool_scheduler uv run python -m jb_pool_scheduler.planner
  ```
* **Detener el servicio:**
  ```bash
  docker compose down
  ```

---

## 🛠️ Desarrollo Local

El entorno y las dependencias se gestionan con **uv**:

```bash
# Sincronizar el entorno de desarrollo
uv sync

# Ejecutar la suite de tests unitarios
uv run pytest

# Verificación de sintaxis y tipado con ruff
uv run ruff check .
```

---

## 🔒 Seguridad y Buenas Prácticas

1. **Secretos fuera del repositorio:** El archivo `.env` y cualquier fichero bajo `data/*.db` se encuentran en el `.gitignore`. **Nunca** hagas commit de secretos reales a GitHub.
2. **Fin de línea (LF):** Asegúrate de que `entrypoint.sh` y `crontab.txt` mantengan saltos de línea estilo Unix (`LF`) para evitar errores en el demonio cron de Linux.
3. **Persistencia desacoplada:** La base de datos local SQLite se almacena en el volumen montado `./data`, manteniéndose intacta ante reconstrucciones o actualizaciones de imágenes Docker.