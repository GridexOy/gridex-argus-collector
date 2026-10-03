# ARGUS20_COLLECTOR_MODULES

Реестр модулей сборщика (структура — TZ_SELAIN §11). Каждый модуль — папка с `README.md` (≤ 40 строк), `contract.py`, `service.py`, `repository.py`, `tests/`. Строка обновляется в том же коммите, что и код модуля.

Слои (import-linter): `ui` → `walk` → `browser | extraction | diagnostics` → `discovery | models | evidence` → `normalization | storage` → `runtime`. Вход в чужой модуль — только `contract.py`.

| Модуль | Назначение | Этап | Состояние |
|---|---|---|---|
| `api_client` | клиент, сгенерированный из OpenAPI | S1 | нет |
| `scheduler` | пакеты, аренда, бюджеты, автопродолжение | S1–S3 | нет |
| `storage` | SQLite `state/collector.db`, миграции | S1 | 0.4.1.0: `connect()` с WAL и миграциями; таблицы `schema_version`, `model_calls`, `evidence_manifest`, `runs`, `observations`; чужие таблицы пишут свои `repository.py` |
| `delivery` | outbox, повторы, reconcile | S1 | нет |
| `discovery` | frontier, ранжирование ссылок и разделов | S2 | 0.4.1.0: approved hosts (seed + redirect, точное совпадение, без суффиксов — K7), запрет соцсетей (K8), запрет документов, ранжирование по словам contact/team/yhteystiedot/henkilöstö, ключ состояния URL + хеш |
| `http_fetch` | HTTP-проход | S2 | нет |
| `browser` | Playwright, действия, маршруты | S0 (smoke), S3 | 0.4.1.0: `WalkBrowser` (`session.py`) — постоянный профиль, видимое окно, `goto`/`click`/`scroll`/`observe` → `PageState` с нумерованными кандидатами (`data-argus-idx`); `mailto:`/`tel:` не нажимаются; submit не нажимается |
| `extraction` | извлечение, привязка, FieldAudit | S2 | 0.4.1.0: детерминированные каналы (`tel:`, `mailto:`, JSON-LD, `data-cfemail`, обфускации в тексте) и verbatim-проверка карточек модели (`verify_card`): поле живёт только с quote в тексте снимка или с совпадением канала из HTML; FieldAudit — S2 |
| `documents` | PDF/DOCX/XLSX/CSV, OCR (M2) | S4 | нет |
| `normalization` | телефоны, email, имена; дедупликация | S2 | 0.4.1.0: E.164 (FI), email с декодированием `(at)`/`[dot]`/cfemail, имена, `same_value`; правила дублей сервера — S2 |
| `evidence` | хэши, канонический текст, локаторы | S1 | 0.4.1.0: канонический текст, sha256, `find_span` (`text_span`), снимки `evidence/<sha[:2]>/<sha>.html|.txt` атомарно + строка `evidence_manifest` |
| `models` | адаптер локальной модели (M2) | S4 | 0.4.1.0: OpenAI-совместимый endpoint на loopback (Ollama `http://127.0.0.1:11434/v1`, `qwen2.5:14b-instruct`), без системного прокси, JSON-режим, каждая попытка — строка `model_calls` (`cost_eur=0`); `health()` → `GET /models` |
| `walk` | обход одного сайта: браузер + модель | S3/S4 (решение владельца 03.10.2026) | 0.4.1.0: цикл страница → снимок → каналы → карточки модели (verbatim) → действие модели из списка (navigate/click/scroll/finish); бюджет страниц, STOP, «Pysäytä»; строки `runs`, `observations`; интеграционный тест на `test_site` с подменой модели |
| `runtime` | каталог данных пользователя, `VERSION` + `build.json`, `config.yaml`, kill switch `STOP` | S0 | S0: готов; 0.4.1.0: `Config` + `model.name`, `walk.page_budget` |
| `diagnostics` | факты о машине и их состояния (Windows, Chrome, NVIDIA, RAM, диск, модель) | S0 | 0.4.1.0: состояние модели — через `models.health` (endpoint отвечает **и** перечисляет модель); `diagnose.ps1 -ModelName`, HttpWebRequest без прокси |
| `ui` | панель, props-only views | S0 | 0.4.1.0: блок Keruu — поле «Yrityksen verkkosivu», «Käynnistä» (активна при модели + Chrome, без STOP), «Pysäytä», строка состояния, «Löydetty: N», живая таблица Nimi · Titteli · Puhelin · Sähköposti · Lähde (двойной клик открывает источник); Resurssit перечитываются после обхода |
| `contract_server/` | эталонный сервер OpenAPI, только для испытаний | S1 | нет |
| `test_site/` | сайт-фикстура (§12.2) | S0 | 0.4.1.0: `fixture_oy` — главная (+ JSON-LD), контакты (3 человека), `team.html` (2 человека за кнопкой «Näytä yhteystiedot», ссылка «Seuraava sivu»), `team-2.html` (обфускованный email в тексте, ссылки, LinkedIn-ссылка, которую обход не открывает); gold 7 человек |
| `collector/tests/fake_model_server.py` | подмена OpenAI-совместимого endpoint, только для тестов | — | 0.4.1.0: `GET /models`, `POST /chat/completions`, usage-токены; в панель не попадает |
