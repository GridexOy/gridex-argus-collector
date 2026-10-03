# ARGUS20_COLLECTOR_MODULES

Реестр модулей сборщика (структура — TZ_SELAIN §11). Каждый модуль — папка с `README.md` (≤ 40 строк), `contract.py`, `service.py`, `repository.py`, `tests/`. Строка обновляется в том же коммите, что и код модуля.

| Модуль | Назначение | Этап | Состояние |
|---|---|---|---|
| `api_client` | клиент, сгенерированный из OpenAPI | S1 | нет |
| `scheduler` | пакеты, аренда, бюджеты, автопродолжение | S1–S3 | нет |
| `storage` | SQLite, миграции | S1 | нет |
| `delivery` | outbox, повторы, reconcile | S1 | нет |
| `discovery` | frontier, ранжирование ссылок и разделов | S2 | нет |
| `http_fetch` | HTTP-проход | S2 | нет |
| `browser` | Playwright, действия, маршруты | S0 (smoke), S3 | нет |
| `extraction` | извлечение, привязка, FieldAudit | S2 | нет |
| `documents` | PDF/DOCX/XLSX/CSV, OCR (M2) | S4 | нет |
| `normalization` | телефоны, email, имена; дедупликация | S2 | нет |
| `evidence` | хэши, канонический текст, локаторы | S1 | нет |
| `models` | адаптер локальной модели (M2) | S4 | нет |
| `ui` | панель, props-only views | S0 | нет |
| `contract_server/` | эталонный сервер OpenAPI, только для испытаний | S1 | нет |
| `test_site/` | сайт-фикстура (§12.2) | S0 | нет |
