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
| `browser` | Playwright, действия, маршруты | S0 (smoke), S3 | S0: план запуска (Chrome на Windows, Chromium в CI), постоянный профиль, видимое окно, отдельный процесс-лаунчер `python -m argus_collector.browser`; smoke-тест против тестового сайта |
| `extraction` | извлечение, привязка, FieldAudit | S2 | нет |
| `documents` | PDF/DOCX/XLSX/CSV, OCR (M2) | S4 | нет |
| `normalization` | телефоны, email, имена; дедупликация | S2 | нет |
| `evidence` | хэши, канонический текст, локаторы | S1 | нет |
| `models` | адаптер локальной модели (M2) | S4 | нет |
| `runtime` | каталог данных пользователя, `VERSION` + `build.json`, `config.yaml`, kill switch `STOP` | S0 | S0: готов; единственный владелец путей `%LOCALAPPDATA%\Gridex\ArgusCollector` |
| `diagnostics` | факты о машине и их состояния (Windows, Chrome, NVIDIA, RAM, диск, модель) | S0 | S0: Python-правила + `scripts/diagnose.ps1 -Json`; расхождение состояний = ошибка |
| `ui` | панель, props-only views | S0 | S0: tkinter, одно окно, светлая тема; версия/дата внизу слева, `Yhteys: Ei yhteyttä`, кнопки сбора неактивны, Resurssit из `diagnostics`, «Avaa työselain», баннер STOP |
| `contract_server/` | эталонный сервер OpenAPI, только для испытаний | S1 | нет |
| `test_site/` | сайт-фикстура (§12.2) | S0 | S0: `server.py` (stdlib), `fixture_oy` — главная + контакты (3 человека) + footer, gold `gold/fixture_oy.json`; остальные фикстуры §12.2 — S2–S3 |
