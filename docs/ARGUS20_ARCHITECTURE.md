# ARGUS 2.0 — Архитектура

**Дата:** 03.10.2026 · **Правка:** 03. Согласовано с ТЗ блока 0 v1.3 (стек, порты, правила модулей, версия, деплой) и ТЗ Selain v3.0.

Изменения 03: второй рантайм — сборщик Selain на Windows (§2, §3, §4, §6, §7); серверный модуль `collector` и его таблицы; `fetcher` снимка получает значения `collector_*`. Принцип «один конвейер» для прогона не меняется: сборщик — внешний исполнитель шага «контакты», подключённый через один контракт.

## 1. Принципы
- Один конвейер, линейный, с чекпоинтами. Это не граф состояний. Параллельность живёт внутри шага (fetch-пул), а не между шагами.
- Ядро читаемо целиком одним человеком за вечер: ≤ 3 000 строк логики. Файл ≤ 200 строк, функция ≤ 40.
- Детерминированный код используется везде, где можно. Модель только читает загруженный текст.
- Интерфейс — надстройка над API-контрактом (OpenAPI → сгенерированный клиент). Бизнес-логики во фронте нет.
- Всё, что видно на экране, — реальное состояние базы.
- Внешний исполнитель (сборщик Selain) — второй рантайм с одной дверью: контракт `ARGUS20_COLLECTOR_OPENAPI.json`; никакого прямого доступа к БД и снимкам.

## 2. Стек
- **Frontend:** Next.js App Router + TypeScript + Tailwind + shadcn/ui + next-intl (fi).
- **Backend:** FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic.
- **БД:** PostgreSQL 16.
- **Fetch:**
  - httpx — основной;
  - Playwright (Chromium, headless) — fallback-fetcher для JS-страниц. Живёт в модуле `channels`, внутри `argus20-worker`, с блока 3. Включается, когда httpx вернул страницу без целевого контента.
- **Compose:** `argus20-db`, `argus20-api`, `argus20-web`; с блока 3 добавляется `argus20-worker` (asyncio, один процесс, включает Playwright).
- **Сборщик Selain (с блока 6, вне compose):** Windows MAIN-PC владельца, RTX 4090 24 ГБ; Python 3.12 + asyncio, httpx, lxml, Playwright + установленный Chrome (постоянный рабочий профиль, видимое окно, CDP только loopback), Pydantic, SQLite (WAL), панель tkinter; модель — сменный адаптер, локальный инференс на loopback (M2). Репозиторий `gridex-argus-collector`. Исходящее HTTPS к ARGUS; входящих портов нет.
- **Прокси:** Caddy на хосте. Порты на loopback: web 4020, api 9020.

Нет: Redis, Celery, LangGraph, SearXNG, GPU на сервере, MinIO, Crawl4AI, Hermes, расширений Chrome, Windows Service.

Снимки хранятся на диске: `/mnt/argus-data/argus20/snapshots/<sha256[:2]>/<sha256>`. Доказательства сборщика загружаются через API и ложатся туда же через `evidence.contract`.

## 3. Модули (появляются по блокам)
```
api/app/modules/
  system/      health, version                                  блок 0
  projects/    project                                          блок 0–1
  passport/    event_passport, scout                            блок 2
  adapters/    expoplatform, messukeskus, eventos, paviljonki, wayback  блок 3
  channels/    каскад K0→K4, fetcher (httpx + Playwright fallback), channel_yield  блок 3–4
  evidence/    snapshot, claim                                  блок 3
  companies/   company, participation, ER, тиры, стоп-листы     блок 3–5
  contacts/    person, contact_point, contact_observation, лестница И7, статусы K3  блок 6
  collector/   контракт /api/collector: worker, batch, job, run, source, event, entity_map, gap, route, freshness  блок 6
  runs/        run, чекпоинты, терминальные статусы, STOP       блок 3
  cost/        model_call, потолки                              блок 2
  export/      CSV/XLSX                                         блок 7
```
Каждый модуль содержит:
- `README.md`;
- `contract.py` — единственный вход;
- `routes.py`, `service.py`;
- `repository.py` — единственное место доступа к своим таблицам;
- `models.py`, `tests/`.

Границы проверяет import-linter. Другие модули получают страницы только через `channels.contract`, Playwright напрямую не импортируют. `collector` пишет персон, каналы и снимки только через `contacts.contract` и `evidence.contract`; расход модели — через `cost.contract`.

Модули сборщика (репо `gridex-argus-collector`): `api_client` (сгенерирован), `scheduler`, `storage`, `delivery`, `discovery`, `http_fetch`, `browser`, `extraction`, `documents` (M2), `normalization`, `evidence`, `models` (M2), `ui`; те же правила папки/README/contract/границ.

## 4. Данные (к блоку 7)
| Таблица | Хозяин | Ключевые поля |
|---|---|---|
| project | projects | id, name, name_normalized UNIQUE, status, is_dryrun, created_at |
| event_passport | passport | project_id, поле → {state: searching/found/not_found, value, source_url, snapshot_id, checked[]}, exhibitors_by_year, platform |
| run | runs | project_id, status (queued/running/completed/failed/aborted/stale), heartbeat_at, checkpoint, cost_ceiling_eur |
| snapshot | evidence | sha256, url, fetched_at, mime, http_status, fetcher (httpx/playwright/collector_http/collector_browser/collector_document), path |
| claim | evidence | subject_type/id, predicate, value, snapshot_id, span_start/end, source_class, confidence, status |
| company | companies | canonical_name, domain, business_id, country, aliases[], legacy_ref |
| participation | companies | company_id, project_id, year, status, claim_id, booth |
| person | contacts | company_id, name, title, role_category, freshness |
| contact_point | contacts | person_id/company_id, channel, value, status (K3), claim_id, last_seen_at |
| contact_observation | contacts | contact_point_id, raw_value, normalized_value, extraction_status, binding, claim_id, change_kind, supersedes_id, observed_at |
| model_call | cost | run_id, provider, model, tokens_in/out, cost_eur, purpose, created_at |
| collector_worker, collector_batch, collector_job, collector_run, collector_source, collector_event, collector_entity_map, collector_gap, collector_route, collector_freshness | collector | см. `ARGUS20_TZ_SELAIN.md` §10.1 |

Ничего не удаляется: меняется только status. Колонок «на будущее» нет.

## 5. Конвейер прогона
```
паспорт → scout → годы → [K0 → K1 → K2 → K3 → K4] по годам → ER + тиры → контакты → отчёт
```
Каждый шаг идемпотентен, пишет чекпоинт, проверяет `STOP` и потолок. Шаг не начинается, если предыдущий не дал чекпоинт. Прогон завершается сам.

Шаг «контакты» с блока 6: по подтверждённым компаниям в порядке 3× → 2× → 1× создаются пакеты Selain (K9); пока сборщик не подключён — серверная лестница И7; результаты обоих путей идут в одни таблицы `contacts` с одними статусами K3. Прогон не ждёт сборщика: он завершается терминальным статусом, задания Selain живут своей кампанией (`collector_job`) и показываются на Soittolista.

## 6. Каналы
| # | Канал | Что даёт | Стоимость | Включается |
|---|---|---|---|---|
| K0 | Адаптер платформы организатора | Полный список года с URL на компанию | ~0 | Всегда первым |
| K1 | Wayback CDX по хосту события/площадки | Списки прошлых лет, PDF | ~0 | Год без K0 |
| K2 | PDF организатора (план зала, каталог) | Список с booth | CPU (Docling) | Покрытие < 70 % |
| K3 | Serper dork-матрица (≤ 6 запросов/год) | Косвенные подтверждения | ~€0.002/запрос | < 85 % |
| K4 | Сайт компании упоминает событие | candidate → confirmed | 1 fetch/компания | Для кандидатов без K0/K1 |
| K4-ext | Внешний провайдер (pull-модель) | Контакты с URL источника | По договору | Блок 6, отдельно |
| Selain | Локальный сборщик: HTTP + действия в Chrome по сайту компании | Люди, каналы, общие контакты с доказательствами, FieldAudit, маршруты, актуальность | Локальная модель 0 €; облако — только по `campaign_cloud_budget_eur` | Блок 6, по K9, только для confirmed/strong_historical |

Yield каждого канала пишется в базу. До блока 7 он виден в Lokit, с блока 7 — во вкладке Kulut. Для Selain yield = добавочные люди/каналы относительно серверной И7 и HTTP-only.

## 7. Модели
| Работа | Исполнитель |
|---|---|
| URL, sitemap, fetch, regex, hash, JSON-LD, ER по домену, экспорт | Код |
| Классификация страницы, релевантность, поля паспорта, toimiala | gemini-2.5-flash-lite (OpenRouter), строгий JSON |
| Большие и неоднозначные списки из HTML/PDF (пагинация) | Kimi K2 (OpenRouter) |
| Scout (где лежит список, сколько экспонентов) | 4 модели параллельно, 1 раз на проект: ChatGPT Responses, Perplexity Sonar, Gemini grounding, Claude web search |
| Selain: выбор разделов, разбор нестандартных карточек, план действия, vision сложного интерфейса (M2) | Локальная модель на RTX 4090 через адаптер; выбор по испытаниям; текст модели — не доказательство |
| Fable | Не в рантайме до блока 8 |

**Учёт.** Каждый вызов в рантайме пишется в `model_call` и входит в потолок прогона. Это касается и Scout, и локальной модели Selain (`cost_eur = 0`, токены считаются).

**Ключ Anthropic.** Claude web search в Scout ходит по отдельному рантайм-ключу, не по ключу разработки. Потолок €150 относится только к разработке (WAYS §9).

**Целевой расход:** €1–3 на выставку (3 года, ~200 компаний, контакты); с Selain на локальной модели расход на контакты ≈ 0.

## 8. Интерфейс
- Рабочие экраны: Kortti, Yritykset, Soittolista, Projektit.
- Kulut: с блока 7. До этого счётчик расхода виден на Kortti в блоке Scout.
- Soittolista с блока 6: строка состояния Selain, этап и причина неполноты по компании, история наблюдений в карточке контакта.
- Светлая тема, FI. Версия и дата сборки всегда внизу слева. Панель сборщика — отдельное окно на Windows, те же правила (FI, версия внизу слева).
- Подробнее — `ARGUS20_SCREENS.md`.

## 9. Деплой
`deploy/deploy.sh` — единственный путь деплоя. Порядок:
1. текущая ветка `main`;
2. гейты;
3. чистое дерево;
4. VERSION (`0.N.M.K`) больше прода;
5. build с build args;
6. alembic;
7. up;
8. сверка /api/health;
9. tag `v0.N.M` при K = 0.

Мерж в `main` делается только fast-forward и только основной сессией. Ветки step удаляются после мержа.

Бэкапы: ночной pg_dump, хранение 14 дней.

Caddy:
- `/argusold*` → старая система;
- `/api/*` → 9020 (включая `/api/collector/*`, basic-auth на `/api/collector/*` снят: авторизация — Bearer-токен сборщика; принято решение — поправь, если не так);
- остальное → 4020.

Сборщик: установка на MAIN-PC скриптом `install.ps1` из `main` репо `gridex-argus-collector`; обновление с резервной копией SQLite и откатом; автозапуск через Task Scheduler в интерактивной сессии.
