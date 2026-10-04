# ARGUS20_TZ_TANDEM — сборщик Selain работает вместе с ARGUS

**Версия:** 1.0 · **Дата:** 03.10.2026 · **Правка:** 01 · **Владелец:** Игорь
**Основание:** решение владельца 03.10.2026 — связать сборщик с системой сейчас, не дожидаясь блока 5. Это ТЗ — дорожка B из `ARGUS20_TZ_SELAIN.md` §2.1 и §2.4 (там она называлась «ТЗ блока 6») плюс клиентская часть сборщика (S1–S3 в объёме связки).
**Исполнители:**
- **Исполнитель ARGUS** — основная сессия, `/opt/argus20`, прод https://argus.gridex.fi. Делает шаги **B1–B5**.
- **Исполнитель-2** — сессия на Windows MAIN-PC, репозиторий `gridex-argus-collector`. Делает шаги **A1–A5**.

**Опирается на:** `ARGUS20_TZ_SELAIN.md` v3.0 (контракт §9, статусы §9.4, данные §10, поведение §8) и `ARGUS20_COLLECTOR_OPENAPI.json` 3.0.0 (wire schema 1.1). Эти два документа не меняются. Где это ТЗ упрощает их для первого рабочего варианта, сказано явно (§4).

## 1. Что получает продавец
Сейчас «Etsi yhteyshenkilöt» обходит сайты с сервера по словарю путей. По отчёту блока Kontaktit это даёт людей у 62 % компаний и gold P 0.57 · R 0.47. Потери — там, где сервер не может:
- контакты в /media и пресс-релизах (ABB, Ensto, Onninen);
- JS-каталоги, «näytä lisää», карточки по клику;
- редирект на другой хост (abb.fi → new.abb.com).

Сборщик на MAIN-PC уже умеет обходить сайт сам: модель qwen2.5:14b на RTX 4090 ведёт видимый Chrome, каждое значение подтверждено цитатой со страницы (сборщик 0.4.1.3, отчёт `ARGUS20_COLLECTOR_STAGE4_REPORT.md`). Связка делает так:
1. В Soittolista продавец отмечает компании и жмёт «Lähetä Selaimeen».
2. Сборщик на MAIN-PC сам забирает пакет и обходит сайты.
3. Найденные люди и каналы появляются в той же Soittolista во время обхода, с источником и снимком, как контакты сервера.

## 2. Неподвижное
1. **Одна дверь.** Связь только через `/api/collector` по OpenAPI 3.0.0. Сборщик не видит БД, снимков и других модулей. ARGUS не управляет браузером сборщика.
2. **Факт = снимок + цитата + URL** (E1/E2). Сервер сам проверяет цитату по загруженному снимку. Не нашёл — событие отклонено (`evidence_missing` / `evidence_hash_mismatch`), в Soittolista ничего не попадает.
3. **Статус канала K3 выводит только сервер** по таблице `TZ_SELAIN` §9.4. Сборщик передаёт `extraction_status` и `binding`, статус не задаёт.
4. **Хозяева таблиц.** `collector_*` — модуль `collector`. `person`, `contact_point`, `contact_observation` — `contacts`. `snapshot` — `evidence`. `model_call` — `cost`. `collector` пишет в чужие таблицы только через их `contract.py`.
5. **Один экран — один источник** (E6). Контакты от сборщика и от сервера лежат в одних таблицах, а Soittolista, счётчики и Gold считаются одним запросом, как сейчас.
6. **Контакт не удаляется.** Сборщик может только подтвердить, изменить или отметить «не найден в проверенном объёме».
7. Цикл шага, «ок», версии, живая проверка — по `CLAUDE.md` своего репозитория. ARGUS проверяется в браузере на проде, сборщик — на MAIN-PC.

## 3. Шаги
Шаги идут парами: Bn на сервере и An на сборщике делаются параллельно, сдаются одной общей тест-картой. «Ок» владельца — на пару. Следующая пара — после «ок».

**Нумерация.** Шаг получает версию при старте ветки: прод + 1 по третьему числу (правило от 02.10). Ожидаемые версии:

| Пара | ARGUS (ожид.) | Сборщик (ожид.) | Что видно |
|---|---|---|---|
| 1 Связь | 0.4.11.0 | 0.4.2.0 | В Soittolista строка `Selain: yhdistetty · keskeytetty`; в панели сборщика `Yhdistetty`, worker_id, heartbeat |
| 2 Пакет и контакты | 0.4.12.0 | 0.4.3.0 | «Lähetä Selaimeen» → компании в Jono сборщика → Chrome обходит → люди и каналы появляются в Soittolista во время обхода с меткой «Selain» |
| 3 Надёжность и управление | 0.4.13.0 | 0.4.4.0 | Сеть пропала и вернулась, панель закрыта и открыта — всё доставлено без дублей; «Pysäytä» / «Jatka» / «Peruuta» из ARGUS; записи в Lokit |
| 4 История и полнота | 0.4.14.0 | 0.4.5.0 | Повторный обход: «Nähty viimeksi», «muuttunut» / «vahvistettu», «ei löytynyt tarkistetusta laajuudesta»; причина неполноты у компании |
| 5 Пилот | 0.4.15.0 | 0.4.6.0 | 8 компаний из gold Sähkö, где сервер не нашёл людей; строка Gold до и после |

Если линию сдвинет другой шаг, берётся следующий свободный номер.

## 4. Упрощения первого варианта (M1)
Это ТЗ сознательно не делает до пилота (пара 5):
- **Маршруты** (`route.recorded` / `route.verified`, `TZ_SELAIN` §8.7) — после пилота. Методы и таблица `collector_route` создаются, сборщик их не шлёт. В `ClaimedJob.routes` сервер отдаёт пустой массив.
- **Автопродолжение** (`policy.auto_continue`, §8.6) — выключено. `partial` — до «Jatka» владельца.
- **Слияние персон** (`contact.merge_proposed`) — сервер принимает и хранит, ничего не сливает автоматически.
- **Документы, OCR, капча** — как в сборщике сейчас: Gap с причиной, без обработки.
- **Один worker** (MAIN-PC). Задание закреплено за ним (`TZ_SELAIN` §8.14, M1).

## 5. Пара 1 — Связь

### B1 (ARGUS)
1. **Модуль `api/app/modules/collector/`** (README, contract, routes, service, repository, models, schemas, tests). `schemas.py` генерируется из OpenAPI и руками не правится.
2. **Миграция** — все таблицы `TZ_SELAIN` §10.1 одной миграцией, плюс `contact_observation` у `contacts` (§10.1, вторая часть).
3. **Токен.** Команда `docker compose exec argus20-api python -m app.cli collector-token --label MAIN-PC` создаёт `collector_worker` и один раз печатает токен. В базе хранится только хэш. `--revoke <worker_id>` отзывает токен. Значение токена владелец вносит в панель сборщика; исполнитель его не видит и не хранит.
4. **Caddy.** Basic-auth закрывает весь `argus.gridex.fi`, а у сборщика свой Bearer: два `Authorization` в одном запросе не помещаются. Поэтому worker-методы выводятся из-под basic-auth отдельным matcher'ом:
   - `POST /api/collector/workers/heartbeat`;
   - `POST /api/collector/jobs/claim`;
   - `POST /api/collector/jobs/*/evidence`, `/events`, `/reconcile`.

   API проверяет их по `WorkerBearer`. System-методы (`POST /batches`, `/control`, все `GET`) остаются за basic-auth: их вызывает только веб ARGUS. Правка Caddyfile — через `scripts/render_caddy.py` с бэкапом, `caddy validate`, `systemctl reload caddy`; блок `argus.gridex.fi` меняется только этим matcher'ом. `restart`/`stop` Caddy запрещены (инцидент 20–21.09).
5. **`POST /workers/heartbeat` и `GET /workers/{id}/status`** — по OpenAPI. На этом шаге в ответе heartbeat пустые `leases[]` и `commands[]`.
6. **Soittolista, шапка** — строка Selain (`TZ_SELAIN` §5.2). Источник — `GET /workers/{id}/status`, обновление раз в 10 с. Сборщик не присылал heartbeat дольше 90 с → `Selain: ei yhteyttä`.

### A1 (сборщик)
1. **`api_client`** генерируется из OpenAPI (`scripts/gen_api_client.ps1`); гейт — `git diff` после генерации пуст.
2. **Блок «Yhteys» в панели**: адрес ARGUS (по умолчанию `https://argus.gridex.fi`), токен (хранится через DPAPI, в логах и на экране — только последние 4 знака), кнопка «Testaa yhteys», worker_id, время последнего heartbeat. Состояния: `Ei yhteyttä` / `Yhdistetty` / `Tunnus hylätty` (red).
3. **Heartbeat** раз в 30 с, пока панель открыта: версия, capabilities, `collecting=false`, свободные слоты, состояние браузера и модели.
4. **Сеть.** На MAIN-PC в Windows настроен системный прокси; на `127.0.0.1` он отвечает 502. Внешние запросы к ARGUS идут по системным настройкам, локальные — всегда напрямую. Настройка `network.proxy: system | direct` в `config.yaml`, по умолчанию `system`. Ошибка сети показывается словами (`Ei verkkoa`), не трассой.
5. **Ручной режим** «Yrityksen verkkosivu» остаётся, но с подписью `Paikallinen testi — ei lähetetä ARGUSiin`. Его результаты в ARGUS не уходят: события без задания контракт не принимает.

### Тест-карта пары 1 (5 мин)
| # | Где | Что сделать | Что должно быть |
|---|---|---|---|
| 1 | ARGUS | Открыть Soittolista любого проекта | Внизу слева новая версия; в шапке `Selain: ei yhteyttä` |
| 2 | Сборщик | Ввести токен → «Testaa yhteys» | `Yhdistetty`, worker_id, heartbeat ≤ 30 с назад |
| 3 | ARGUS | Обновить Soittolista | ≤ 10 с — `Selain: yhdistetty · keskeytetty` |
| 4 | Сборщик | Закрыть панель, подождать 2 мин | В ARGUS — `Selain: ei yhteyttä` |
| 5 | Сборщик | Ввести неверный токен → «Testaa yhteys» | `Tunnus hylätty` красным; ARGUS не изменился |

## 6. Пара 2 — Пакет и контакты

### B2 (ARGUS)
1. **«Lähetä Selaimeen»** в Soittolista. Флажок в каждой строке, кнопка над таблицей: `Lähetä Selaimeen (N)`, N ≤ 8.
   - Активна только для компаний с участием `confirmed` и найденным доменом (R8 в редакции 02: `strong_historical` появится с блоком 5).
   - Неактивная строка показывает причину подсказкой: `Osallistumista ei ole vahvistettu` / `Verkkotunnusta ei löytynyt`.
   - Компания, у которой уже есть активное задание, повторно не отправляется (`Selain käsittelee`).
2. **`POST /batches`** вызывает сервис `collector` изнутри API. `approved_hosts` — домен из `company_domain` с основанием `seed`. Основание `redirect_from_seed` действует только после «ок» K7 редакции 03 (§11 п.1). `policy` — значения R8 §3.3 по умолчанию.
3. **Ядро.** Пакет создаёт `run` через `runs.contract` (kind `collector`), чтобы `model_call.run_id` ссылался на существующий прогон. Его статус повторяет состояние пакета.
4. **`POST /jobs/claim`**, lease 180 с, продление в heartbeat, истечение → `queued`.
5. **`POST /jobs/{id}/evidence`.** Файл ложится через `evidence.contract.store_fetched` с `fetcher` по `TZ_SELAIN` §9.5 (`collector_http` / `collector_browser`). Проверяются sha256 и размер (§8.12); HTML отдаётся инертно, как все снимки.
6. **`POST /jobs/{id}/events`** — `job.started`, `source.*`, `contact.observed`, `contact.enriched`, `model.called`, `job.progress`, `job.finished`. Порядок `seq`, идемпотентность и коды — §9.3.
7. **Запись контакта** через новую функцию `contacts.contract.record_collector_observation`:
   - **Цитата.** Сервер ищет `quote` в тексте снимка, извлечённом своим `html_text.extract`, и пишет **свой** span. Span сборщика — только подсказка: тексты сборщика и сервера разные, и позиции символов не совпадают.
   - **Статус** — по §9.4.
   - **Хост вне `approved_hosts`** → `host_not_approved`, ничего не пишется.
   - **Человек** — по UNIQUE (company, name_normalized), как в 0.4.8.0. Новый — создаётся с цитатой, снимком и URL. Существующий — получает наблюдение; должность меняется, только если новая подтверждена цитатой.
   - **Канал** — по UNIQUE (company, channel, value). Каждое наблюдение — строка `contact_observation`. Статус канала — сильнейший из его наблюдений (`published_direct` > `published_general` > `inferred`). `stale` считается по дате (K5). Сборщик не понижает статус, найденный сервером, и наоборот.
   - `last_seen_at` — дата последнего наблюдения.
8. **Soittolista.**
   - Строка компании показывает vaihe (`TZ_SELAIN` §5.2): `Odottaa käsittelyä` → `Selain käsittelee` → `Valmis` / `Osittain valmis` / `Epäonnistui`, и счётчики henkilöt · kanavat · lähteet.
   - Пока у проекта есть активное задание, таблица обновляется раз в 5 с.
   - У контакта, найденного сборщиком, рядом с «Avaa lähde» — чип `Selain` (по `snapshot.fetcher`). «Avaa lähde» открывает снимок с подсветкой цитаты, как сейчас.
9. **Модель.** `model.called` → `cost.contract`, `provider=local`, `cost_eur=0`, purpose `collector_model`, `run_id` из п.3. Строка расхода Soittolista эти вызовы учитывает: €0, но число вызовов видно.

### A2 (сборщик)
1. **Кнопка «Käynnistä»** в блоке «Keruu» включает сбор (`collecting=true`): `claim` с `max_jobs` = свободные слоты. Компании пакета — в таблице «Jono» (`TZ_SELAIN` §5.1).
2. **Seed.** Обход каждой компании — существующим walk, стартовый URL — `seed_urls` задания. Разрешённые хосты — только `approved_hosts`. Отличие от ручного режима: всё найденное уходит в ARGUS.
3. **Доставка.** На каждую новую страницу-источник — `POST /evidence` (байты снимка + metadata). На каждого найденного человека и канал — `contact.observed` с:
   - `evidence_id`, locator `text_span` и `quote`;
   - `entity_type`, `binding`, `extraction_status`;
   - `field_audit` по источнику.

   Наблюдение не уходит раньше своего снимка.
4. **Outbox.** Событие и запись в outbox — одна транзакция SQLite. Отдельный цикл доставки: микропакет ≤ 50 событий или 2 с. Счётчики «Lähetys»: `Odottaa lähetystä: N` · `Lähetysvirhe: N`.
5. **`job.finished`** с `run_result_status`, `completion_reason`, `coverage` (`TZ_SELAIN` §8.10). Пока охват не проверен по каталогу, `confirmation=unverified`; это нормально и так и показывается.
6. **`model.called`** на каждый вызов модели: токены, мс, `cost_eur=0`.
7. **Ошибка сервера** (`rejected` + код) видна в строке компании в Jono словами, не исчезает молча.

### Тест-карта пары 2 (10 мин)
| # | Где | Что сделать | Что должно быть |
|---|---|---|---|
| 1 | ARGUS | Sähkö-Electricity 2027 → отметить 3 компании с доменом, где сервер не нашёл людей или потерял часть (Naficon Liitin, Onninen, Cablex) → «Lähetä Selaimeen (3)» | У трёх строк `Odottaa käsittelyä`; компания без подтверждённого участия не отмечается, причина в подсказке |
| 2 | Сборщик | «Käynnistä» | 3 строки в Jono; Chrome открывает первый сайт |
| 3 | ARGUS | Смотреть Soittolista во время обхода | `Selain käsittelee`; люди и каналы появляются до конца обхода, с чипом `Selain` |
| 4 | ARGUS | «Avaa lähde» у человека от сборщика | Снимок страницы, цитата подсвечена, URL — хост компании |
| 5 | ARGUS | Дождаться конца | `Valmis` или `Osittain valmis` с причиной; счётчики Nimetty henkilö / Soitettavia выросли так же, как число новых строк |
| 6 | ARGUS | Строка расхода | Добавились вызовы `collector_model` на €0 |

## 7. Пара 3 — Надёжность и управление

### B3 (ARGUS)
1. **`POST /jobs/{id}/reconcile`** — режимы `resume` / `drain_only` (§8.14). Поздние события старого прогона принимаются как наблюдения без права менять состояние.
2. **`POST /jobs/{id}/control`** — `pause` / `resume` / `cancel` / `continue` с `expected_state_revision`. Кнопки в строке компании: «Pysäytä» (pause), «Jatka» (resume / continue), «Peruuta» (cancel, с подтверждением). Команды уходят сборщику в ответе heartbeat.
3. **Lokit** — записи сборщика с префиксами `http` / `browser` / `extraction` / `delivery` / `model`, без значений контактов и секретов (§5.2).
4. **Строка Selain** — состояния `kerää · N yritystä jonossa` и `tulosten lähetys epäonnistui` (red).

### A3 (сборщик)
1. **Восстановление.** Перезапуск панели, обрыв сети, истечение lease → reconcile → продолжение без дублей (§8.14). `seq` не сбрасывается.
2. **Команды из heartbeat** исполняются и подтверждаются (`command_id` в acks).
3. **Kill switch.** «Pysäytä» в панели и файл `STOP` останавливают и обход, и claim; outbox при этом продолжает отправку.
4. **Журнал** — те же префиксы, что видит Lokit; без PII.

### Тест-карта пары 3 (10 мин)
| # | Где | Что сделать | Что должно быть |
|---|---|---|---|
| 1 | Сборщик | Посреди обхода выключить Wi-Fi на 2 мин | Панель `Ei verkkoa`, обход идёт; после включения — `Lähetetään` → `Lähetetty`; в ARGUS число людей не задвоилось |
| 2 | Сборщик | Закрыть панель посреди обхода, открыть, «Käynnistä» | Компания продолжается; дублей нет |
| 3 | ARGUS | «Pysäytä» у компании | ≤ 30 с — `Keskeytetty`, Chrome по ней не ходит |
| 4 | ARGUS | «Jatka» | Обход продолжается с того места |
| 5 | ARGUS | «Peruuta» у другой компании | `Peruttu`; найденное до отмены осталось |
| 6 | ARGUS | Lokit | Строки `browser` / `delivery` по ходу обхода, без телефонов и почт |

## 8. Пара 4 — История и полнота

### B4 (ARGUS)
1. **`known_contacts[]` в claim** — контакты компании из `contact_point` (сервер и сборщик) для проверки актуальности.
2. **`contact.freshness`** → `collector_freshness`; у канала:
   - `Nähty viimeksi <дата>`;
   - история наблюдений в раскрытии строки: дата, значение, `vahvistettu` / `muuttunut`;
   - `Ei löytynyt tarkistetusta laajuudesta` — серым. Контакт не удаляется и в Soitettavia остаётся, пока не `stale`.
3. **У компании** — причина неполноты из `completion_reason` словами и Gap-список (раскрытие): адрес и причина (`access_denied`, `consent_unresolved`, `unsupported_widget`, …).

### A4 (сборщик)
1. Повторный пакет той же компании (`rerun_reason`) → `contact.freshness` для каждого `known_contact`: `reconfirmed` / `changed` / `not_seen_in_checked_scope` / `not_checked` с описанием проверенного объёма.
2. `change_kind` и `supersedes_observation_id` в наблюдениях.
3. Gap с причиной на каждую непройденную ветвь; `coverage` с `basis`, `expected_count`, `found_count`.

### Тест-карта пары 4 (7 мин)
| # | Где | Что сделать | Что должно быть |
|---|---|---|---|
| 1 | ARGUS | Повторно отправить компанию из пары 2 | Тот же человек — `vahvistettu`, `Nähty viimeksi` сегодня; строк не прибавилось |
| 2 | Сборщик (тестовый сайт) | Убрать человека из фикстуры, повторить пакет | В ARGUS у него `Ei löytynyt tarkistetusta laajuudesta`, строка на месте |
| 3 | ARGUS | Компания `Osittain valmis` | Причина словами и Gap-список с адресами |

## 9. Пара 5 — Пилот
1. **Пакет.** 8 компаний Sähkö-Electricity 2027 из gold, где сервер нашёл 0 людей или потерял часть: ABB, Ensto, Onninen, Cablex, Naficon Liitin, Schneider*, Prysmian*, Phoenix Contact*.

   \* У отмеченных нет найденного домена (отчёт Kontaktit, приложение A). Для них домен вносит владелец (`owner_known_url`) — это действие владельца, не исполнителя. Не внесён — компания заменяется следующей из gold без домена-проблемы.
2. **Метрики** — до и после, на экране Soittolista и в отчёте пары:
   - строка Gold P · R;
   - Nimetty henkilö;
   - Soitettavia;
   - доля `published_direct` среди найденного сборщиком.
3. **Проверка.** 10 случайных телефонов от сборщика — со страниц хостов из `approved_hosts`; цитата совпадает со снимком.
4. **Порог** (блок 6, BLOCKS): ≥ 50 % компаний пакета — человек с каналом не `inferred` / `stale`.
5. **Отчёт** `docs/ARGUS20_TANDEM_REPORT.md` в ARGUS и `ARGUS20_COLLECTOR_STAGE6_REPORT.md` в сборщике: время на компанию, страниц и действий, вызовов модели, сравнение с серверной лестницей по тем же компаниям.

## 10. Общие контрактные тесты
- **Набор примеров.** Запросы и ответы на каждый метод и каждый код ошибки §9.3 — в `docs/collector_contract/` (JSON). Кладёт Исполнитель ARGUS в паре 1; в репозиторий сборщика копию переносит владелец.
- **Обе стороны прогоняют один набор.** Сборщик — против своего тестового контракт-сервера и против прода (только чтение: heartbeat). ARGUS — pytest модуля `collector` на тех же JSON.
- **Расхождение** схемы или примера — красный гейт на обеих сторонах.
- **Изменение контракта** — только перевыпуском `TZ_SELAIN` + OpenAPI владельцем (`TZ_SELAIN` §3.1 п.2).

## 11. Требует «ок» владельца
1. **K7 редакции 03** (`redirect_from_seed`, `linked_from_contact_section`, `business_id_match`). Без «ок» abb.fi → new.abb.com остаётся недоступным и для сборщика.
2. **Caddy.** Worker-методы `/api/collector` выводятся из-под basic-auth, их защищает Bearer-токен (§5 B1 п.4).
3. **Порядок блоков.** Связка идёт раньше блока 5. `strong_historical` и тиры появятся позже; до того пакет — только `confirmed`.
4. **Версии.** Линия ARGUS остаётся 0.4.N (правило 02.10), линия сборщика продолжается от 0.4.1.3.
5. **Код сборщика на GitHub** — пустой репозиторий `GridexOy/gridex-argus-collector` создаёт владелец. До этого код живёт только на MAIN-PC.

## 12. Что дальше (не делать)
- Маршруты и автопродолжение (§4) — после пилота.
- Несколько сборщиков, передача задания между ними — M2.
- Провайдер K4-ext — отдельный канал, объединение по `normalization`.
