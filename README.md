# skud_local

Local production-like SKUD backend for Django + PostgreSQL with a short decision path for turnstile access checks and an integration layer for IronLogic Z-5R Web BT over Web-JSON.

The repository also contains `Example_in_basic_python/` with plain Python reference snippets. That directory is intentionally not part of the Django application and is left untouched.

## What this project does

- stores people, wristbands, controllers, access points, policies, events, and audit logs
- resolves access decisions by RFID/NFC wristband UID
- exposes internal REST API for operators and administrators
- accepts HTTP POST callbacks from IronLogic-compatible Web-JSON controllers
- returns access decisions and pending controller commands in the same response
  using the documented controller envelope `{"date","interval","messages":[...]}` for real Z5R Web BT requests
- keeps a controller task queue for offline fallback and synchronization scenarios

## Stack

- Python 3.12+
- Django 5.2.12
- Django REST Framework 3.16.0
- PostgreSQL
- Gunicorn
- Docker Compose

## Architecture

Core principles:

- apps are split by bounded context
- business logic lives in services
- read paths live in selectors
- serializers handle API input/output validation
- views stay thin
- integration-specific assumptions are isolated in `apps.ironlogic_integration`

Main apps:

- `apps/core`: shared models, health endpoints, pagination, test/demo helpers
- `apps/people`: person records
- `apps/wristbands`: wristband identifiers and validation logic
- `apps/access`: access points, time rules, policies, access decision service
- `apps/controllers`: controller registry, controller task queue, sync planning
- `apps/events`: access events and audit logs
- `apps/ironlogic_integration`: Web-JSON adapters, endpoint, response builders, raw request logging

Hot path for `check_access`:

1. resolve controller and access point
2. normalize wristband UID
3. fetch wristband with `select_related("person")`
4. validate wristband and person state
5. fetch active policies with `select_related("timezone_rule")`
6. evaluate time window and policy priority
7. write `AccessEvent`
8. return `granted/denied` and a batched list of pending controller commands

## Project layout

```text
.
|-- apps/
|   |-- access/
|   |-- controllers/
|   |-- core/
|   |-- events/
|   |-- ironlogic_integration/
|   |-- people/
|   `-- wristbands/
|-- requirements/
|-- skud_local/
|   |-- settings/
|   |-- api_urls.py
|   `-- urls.py
|-- Dockerfile
|-- docker-compose.yml
`-- manage.py
```

## Quick start

1. Copy environment defaults:

```bash
cp .env.example .env
```

For local commands executed from the host machine, keep `POSTGRES_HOST=127.0.0.1` in `.env`.  
`docker compose` overrides the application container to use the internal Docker hostname `db`.

2. Start PostgreSQL and Django:

```bash
docker compose up --build
```

If you need the Django container to see the real source IP of LAN devices such as the Fondvision reader, start the web service with the host-network override instead of the default published-port setup:

```bash
docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up --build
```

This mode is intended for reader/controller integrations where Docker NAT would otherwise replace the sender IP with the Docker gateway address.

3. Run migrations manually if needed:

```bash
docker compose run --rm web python manage.py migrate
```

4. Create a superuser:

```bash
docker compose run --rm web python manage.py createsuperuser
```

5. Optionally load demo data:

```bash
docker compose run --rm web python manage.py seed_demo_data
```

6. Open the service:

- admin: `http://localhost:8000/admin/`
- live probe: `http://localhost:8000/health/live`
- ready probe: `http://localhost:8000/health/ready`

## Environment variables

Baseline values live in `.env.example`.

General:

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_LANGUAGE_CODE`
- `DJANGO_TIME_ZONE`

Database:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `DATABASE_CONN_MAX_AGE`
- `DATABASE_CONNECT_TIMEOUT`

Web process:

- `WEB_PORT`
- `GUNICORN_WORKERS`
- `GUNICORN_THREADS`
- `GUNICORN_TIMEOUT`

IronLogic integration:

- `IRONLOGIC_WEBJSON_SHARED_TOKEN`
- `IRONLOGIC_ALLOWED_IPS`
- `IRONLOGIC_TRUST_X_FORWARDED_FOR`
- `IRONLOGIC_RESPONSE_INTERVAL_SECONDS`
- `IRONLOGIC_TASK_BATCH_SIZE`
- `IRONLOGIC_TASK_BATCH_MAX_BYTES`
- `IRONLOGIC_TASK_SENT_RETRY_SECONDS`
- `IRONLOGIC_SYNC_WRISTBAND_CHUNK_SIZE`

Fondvision integration:

- `FONDVISION_CONTROLLER_USERNAME`
- `FONDVISION_CONTROLLER_PASSWORD`
- `FONDVISION_CONTROLLER_TIMEOUT_SECONDS`
- `FONDVISION_COMMAND_RELAY_URL`
- `FONDVISION_COMMAND_RELAY_TOKEN`
- `FONDVISION_COMMAND_RELAY_TIMEOUT_SECONDS`
- `FONDVISION_QR_PASSWORD`
- `FONDVISION_QR_B_SUFFIX_REQUIRED_FROM`

SQLite is intentionally not supported.

## Docker Real-IP Mode

The default `docker compose up` path publishes `8000:8000`, which is convenient for local development but can hide the real client IP behind Docker Desktop's network gateway. For hardware integrations that identify readers by source IP, use the host-network override:

```bash
docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up -d --build
```

Requirements:

- Docker Desktop 4.34+
- Docker Desktop setting `Enable host networking` turned on

In this mode:

- `web` runs with `network_mode: host`
- incoming requests reach Gunicorn without the normal published-port NAT layer
- `web` connects to PostgreSQL through the host-published database port on `127.0.0.1`

Do not use the default `web` ports mapping and the host-network override at the same time.
If Docker prints a warning that published ports are discarded in host network mode, that is expected.

## Migrations

Apply migrations:

```bash
docker compose run --rm web python manage.py migrate
```

If you are working without Docker in a prepared local Python environment:

```bash
python manage.py migrate
```

## Demo data

The project includes an idempotent management command:

```bash
python manage.py seed_demo_data
```

It creates or refreshes:

- 1 demo controller
- 2 access points
- 3 people
- 4 wristbands
- 4 access policies
- pending controller tasks
- sample access events
- an audit log entry

Useful demo identifiers:

- controller serial: `DEMO-Z5R-001`
- entry access point code: `main-entry`
- exit access point code: `main-exit`
- employee wristband UID: `04DEMO000001`
- visitor wristband UID: `04DEMO000002`
- blocked wristband UID: `04DEMO000003`
- spare unassigned wristband UID: `04DEMO000004`

## Fondvision Relay On Windows Host

If Django runs in Docker Desktop and the container cannot route directly to the controller LAN, use the host relay:

1. In `.env` set:

```dotenv
FONDVISION_COMMAND_RELAY_URL=http://host.docker.internal:8099/open-door
FONDVISION_COMMAND_RELAY_TOKEN=change-me
FONDVISION_CONTROLLER_USERNAME=z5rweb
FONDVISION_CONTROLLER_PASSWORD=97679A55
```

2. Start the relay on the Windows host:

```bash
set FONDVISION_RELAY_TOKEN=change-me
python scripts/fondvision_relay.py
```

3. Rebuild the web container:

```bash
docker compose up -d --build
```

The relay keeps the SKUD logic in Django while sending the final `cgi-bin/command` request from the Windows host, which can reach the LAN controller directly.

## Tests

Run the focused suite:

```bash
python manage.py test apps.wristbands apps.access apps.controllers apps.ironlogic_integration
```

If tests are run from the host machine instead of inside Docker, PostgreSQL must be reachable via the host values from `.env`, typically:

- `POSTGRES_HOST=127.0.0.1`
- `POSTGRES_PORT=5432`

If you prefer running tests inside Docker:

```bash
docker compose run --rm web python manage.py test apps.wristbands apps.access apps.controllers apps.ironlogic_integration
```

Covered areas:

- wristband validation rules
- access decision service
- controller task lifecycle and batching
- full/delta wristband sync planning
- `POST /api/ironlogic/webjson/` integration scenarios

## Internal REST API

Authentication:

- `SessionAuthentication`
- `BasicAuthentication`
- `IsAdminUser`

Main endpoints:

- `GET/POST /api/people/`
- `GET/POST /api/wristbands/`
- `GET/POST /api/controllers/`
- `GET/POST /api/access-points/`
- `GET/POST /api/access-policies/`
- `GET /api/access-events/`
- `GET /api/controller-tasks/`

Special actions:

- `POST /api/wristbands/{id}/assign/`
- `POST /api/wristbands/{id}/unassign/`
- `POST /api/wristbands/{id}/block/`
- `POST /api/wristbands/{id}/unblock/`
- `POST /api/controllers/{id}/open-door/`
- `POST /api/controllers/{id}/read-cards/`
- `POST /api/controllers/{id}/set-door-params/`
- `POST /api/controllers/{id}/sync-wristbands/`

Example `curl`:

```bash
curl -u admin:password \
  "http://localhost:8000/api/people/?status=active"
```

```bash
curl -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"uid":"04DEMO000010","person":1,"status":"active"}' \
  http://localhost:8000/api/wristbands/
```

```bash
curl -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"person_id": 1}' \
  http://localhost:8000/api/wristbands/1/assign/
```

```bash
curl -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"access_point_id": 1, "duration_seconds": 3}' \
  http://localhost:8000/api/controllers/1/open-door/
```

```bash
curl -u admin:password \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:8000/api/controllers/1/read-cards/
```

```bash
curl -u admin:password \
  -H "Content-Type: application/json" \
  -d '{"open":10,"open_control":10,"close_control":10}' \
  http://localhost:8000/api/controllers/1/set-door-params/
```

Example `httpie`:

```bash
http --auth admin:password GET :8000/api/access-events/?decision=granted
```

```bash
http --auth admin:password POST :8000/api/controllers/1/sync-wristbands/ force_full:=true
```

## IronLogic Web-JSON endpoint

Endpoint:

- `POST /api/ironlogic/webjson/`

Supported operations:

- `power_on`
- `ping`
- `check_access`
- `events`

Current response capabilities:

- documented controller envelope with `date`, `interval`, and `messages`
- automatic `set_active` response on `power_on` while the controller is still inactive
- access decision payload for `check_access`
- `events_success` acknowledgement for `events`
- pending controller commands mapped to documented operations like `open_door`, `set_door_params`, `add_cards`, `del_cards`, `clear_cards`, `read_cards`
- task acknowledgement processing
- `read_cards` result logging into controller events for reconciliation/debugging
- controller runtime state refresh from device fields like `fw`, `conn_fw`, `active`, `mode`, `controller_ip`, `auth_hash`
- raw request/response logging in `WebJsonRequestLog`

Documented request envelope example:

```json
{
  "type": "Z5-R WEB BT",
  "sn": "DEMO-Z5R-001",
  "messages": [
    {
      "id": 1001,
      "operation": "check_access",
      "card": "04DEMO000001",
      "reader": 1
    }
  ]
}
```

Example `curl`:

```bash
curl -H "Content-Type: application/json" \
  -d '{"type":"Z5-R WEB BT","sn":"DEMO-Z5R-001","messages":[{"id":1001,"operation":"check_access","card":"04DEMO000001","reader":1}]}' \
  http://localhost:8000/api/ironlogic/webjson/
```

Example `httpie`:

```bash
http POST :8000/api/ironlogic/webjson/ \
  type='Z5-R WEB BT' \
  sn='DEMO-Z5R-001' \
  messages:='[{"id":2001,"operation":"ping","active":1,"mode":0}]'
```

Example `events` request:

```json
{
  "type": "Z5-R WEB BT",
  "sn": "DEMO-Z5R-001",
  "messages": [
    {
      "id": 3001,
      "operation": "events",
      "events": [
        {
          "event": 4,
          "card": "04DEMO000001",
          "time": "2026-03-11 10:00:00",
          "flag": 0,
          "reader": 1
        }
      ],
      "last_event": 3160
    }
  ]
}
```

## Health endpoints

- `GET /health/live`
- `GET /health/ready`

## Operational limitations

- offline fallback is only partially implemented on the backend side; real autonomous controller behavior depends on confirmed device protocol semantics
- tasks are marked `sent` when included in an HTTP response; without hardware acknowledgement there is still a retry/deduplication risk
- new or unknown card UIDs are denied by policy evaluation and logged in `AccessEvent` with `credential_uid` and `reason_code`, but they are not auto-enrolled into `Wristband`
- time rules support weekly windows and overnight intervals, but not holiday calendars or exception dates
- the integration layer assumes canonical uppercase UIDs and uppercase controller serial numbers
- the internal REST API is admin-oriented and expects a trusted local network segment

## Hardware assumptions

- ASSUMPTION: real Z5R Web BT callbacks arrive in the documented envelope `{"type","sn","messages":[...]}` with per-message fields like `id`, `operation`, `card`, `reader`, `events`, `success`
- ASSUMPTION: legacy flat payloads are still supported for compatibility with tests and manual debugging, but real hardware integration should prefer the documented `messages[]` envelope
- ASSUMPTION: task acknowledgements may come either in documented per-message forms like `{"id":123,"success":1}` or in pragmatic compatibility fields like `task_results`, `completed_task_ids`, `failed_tasks`
- ASSUMPTION: `power_on` and `ping` are handled as command-poll notifications and therefore receive a commands-only response envelope unless there are explicit business results to return, like `check_access` or `events_success`
- Design note: when Z5R reports `power_on` with `active=0`, the server proactively returns `set_active(active=1, online=1)` so the controller can leave bootstrap mode and stop repeating `power_on`
- ASSUMPTION: one controller can expose one or more access points identified by `access_point_code` or `device_port`
- ASSUMPTION: the controller accepts command batching in a single JSON response and can map device terminology like `cards` to the domain `wristbands`

These assumptions are intentionally isolated inside `apps.ironlogic_integration`.

## Production TODO

- verify real IronLogic Web-JSON payloads on hardware and tighten adapters/response builders accordingly
- add stronger transport and protocol security if the backend is exposed beyond a tightly controlled local network
- define a device acknowledgement strategy that removes ambiguity around `sent` vs `executed`
- add holiday calendars and richer scheduling rules if business requirements need them
- add end-to-end tests against a real or simulated controller
- add observability and alerting around controller availability and queue backlog

## Key files

- `skud_local/settings/base.py`: global settings and environment-driven configuration
- `skud_local/api_urls.py`: main API router
- `apps/access/services.py`: access decision service
- `apps/controllers/services.py`: controller queue, batching, and sync planning
- `apps/ironlogic_integration/services.py`: Web-JSON orchestration
- `apps/ironlogic_integration/adapters.py`: protocol normalization
- `apps/core/demo_data.py`: idempotent demo seed logic
- `apps/controllers/management/commands/seed_demo_data.py`: demo data command
