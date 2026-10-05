# ARGUS20_COLLECTOR_CHANGELOG

## 0.4.6.0 — 2026-10-05

**Шаг `stage-5/step-5-a5-pilot`: пара 5 TZ_TANDEM «Пилот» (A5) — подготовка сборщика.** Сам пилот (8 компаний Sähkö-Electricity 2027 против прода ARGUS на MAIN-PC, `owner_known_url` для Schneider / Prysmian / Phoenix Contact) — действие владельца и сессии ARGUS (B2–B4 на проде); в контейнере не проводился.

**Что видно.**
- Cookie-баннеры отвечаются автоматически (TZ_SELAIN §8.5): «только необходимые» (`Vain välttämättömät`, `Only necessary`, `Nur notwendige`, …), иначе «отклонить» (`Hylkää`, `Reject all`, …), «принять» — только если другого нет; ответ — один раз на хост, до чтения страницы (текст баннера в снимок не попадает). Строка состояния `Evästeilmoitus: valittiin «Nur notwendige»`, журнал `browser: cookie banner on <host>: necessary (…)`, в `coverage.scope_description` — `cookie banners answered (<host>: necessary)`.
- Отчёт пилота со стороны сборщика: `scripts\pilot_report.ps1 [-Batch <id>]` (или `python -m argus_collector.pilot`) пишет `%LOCALAPPDATA%\Gridex\ArgusCollector\reports\pilot-*.md`: по компании — результат и причина, активное и полное время, страницы, действия, вызовы модели (число, токены, секунды), люди, каналы, `published_direct` среди событий, оценённых ARGUS; порог ≥ 50 % компаний с человеком, чей канал не `inferred`/`stale`; 10 случайных телефонов — хост снимка в `approved_hosts`, цитата на своём месте в снимке.

**Модули.** Новый: `pilot` (README, contract, service, repository, render, `__main__`, tests). Изменены: `browser` (`page_tools.py` — кандидаты, проверка «не бот», ответ на cookie-баннер; `scripts.py` — `CONSENT_JS`; `service.consent_choice`), `walk` (`checkpoint.consents`, шаг `consent`), `scheduler` (`job_facts`, scope с cookie-ответами), `delivery` (`run_results`, `local_evidence_id`), `ui` (строка шага), `messages/fi.json`; `test_site/sites/vogel/index.html` — баннер в духе Cookiebot (`Alle akzeptieren` / `Nur notwendige` / `Einstellungen`); `pyproject.toml` — слой `ui | pilot`, новые внутренние файлы шагов 3–5 закрыты import-linter'ом.

**Решения (поправь, если не так).**
1. При баннере только с «принять» сборщик принимает (TZ: «автоматически, предпочтение необходимым») и фиксирует это в журнале и в scope; баннер без понятных кнопок не трогается (если перекрывает клик — gap как раньше).
2. Метрики ARGUS (Gold P · R, Nimetty henkilö, Soitettavia, сравнение с серверной лестницей) отчёт сборщика не считает — это экран Soittolista и отчёт ARGUS; сборщик даёт свои таблицы для `ARGUS20_COLLECTOR_STAGE6_REPORT.md`.
3. `ARGUS20_COLLECTOR_STAGE6_REPORT.md` пишется после пилота (сейчас данных нет, демо-цифры не ставлю); порядок пилота — в `ARGUS20_COLLECTOR_STAGE5_REPORT.md`, раздел пары 5.

## 0.4.5.0 — 2026-10-05

**Шаг `stage-5/step-4-a4-history`: пара 4 TZ_TANDEM «История и полнота» (A4) и сокращение паузы по решению владельца 05.10.2026.**

**Что видно (в ARGUS / контракт-сервере; в панели — те же Jono / Lähetys).**
- Повторный пакет той же компании (`rerun_reason`): тот же человек приходит как `reconfirmed` — строк в ARGUS не прибавляется, `last_seen_at` — сегодня; изменённое поле — `changed` со ссылкой на прежнее наблюдение (`supersedes_observation_id`); человек, которого на сайте больше нет, — `contact.freshness` `not_seen_in_checked_scope` («Ei löytynyt tarkistetusta laajuudesta»), контакт остаётся.
- `job.finished`: `freshness_summary` = счёт проверок; `coverage.basis` / `expected_count` / `found_count` (каталог с заявленным размером — `catalog_total`, найдены все — `verified_against_catalog_total`); `scope_description` — страницы, состояния, хосты, открытые вкладки/разделы, заявленный размер, остаток frontier и число gaps.
- Gap на каждую непройденную ветвь: кончился бюджет — каждая оставшаяся релевантная ссылка `budget_reached` (возобновляемо); три сбоя подряд — `no_progress`; релевантная ссылка на хост того же бренда вне `approved_hosts` (`ledvance.fi` рядом с `ledvance.com`) — `domain_ownership_unresolved` (не возобновляемо, владелец может внести `owner_known_url`).
- «Pysäytä» из ARGUS исполняется после текущей страницы: состояние `paused` приходит в ответе на каждый пакет событий (обход шлёт их после каждой страницы), heartbeat для этого больше не нужен; команда по-прежнему подтверждается в heartbeat (`applied`).

**Как работает.** `scheduler.history`: известные контакты из claim (форма `fields` в контракте открыта — читаются строка, список, объект с `value`/`observation_id` и список объектов); человек сопоставляется по нормализованному имени, офис/общий канал — по телефону или почте; значение = известному → `reconfirmed`, другое значение известного поля → `changed` + `supersedes`, иначе `new`. `scheduler.freshness`: в конце прогона — по проверке на каждое поле каждого известного контакта, из наблюдений задания (checkpoint), с evidence наблюдения; события по ≤ 50 проверок перед `job.finished`. `walk.coverage`: заявленный размер каталога, gaps внешних ссылок бренда; `walk.state.gap_unwalked`; `walk.actions` — выполнение действий вынесено из `runner.py`.

**Модули.** Новые файлы: `scheduler/history.py`, `scheduler/freshness.py`, `walk/coverage.py`, `walk/actions.py`. Изменены: `scheduler` (events, sink, runner, finish, hooks, repository), `walk` (state, decide, page, runner, sink). Тесты: `scheduler/tests/test_history.py`, `test_collector_history.py` (повтор → reconfirmed без новых строк; вариант фикстуры без Pekka Salo → not_seen, контакт на месте), `test_collector_control.py::test_pause_takes_effect_after_the_current_page_without_a_heartbeat`, `walk/tests/test_coverage.py`.

**Решения (поправь, если не так).**
1. Формат `KnownContact.fields` контракт не фиксирует; сборщик читает все разумные формы, контракт-сервер отдаёт `{поле: [{value, raw_value, observation_id, observed_at}]}` — вопрос Архивариусу: какой формат отдаёт B4.
2. `not_seen_in_checked_scope` — только при исчерпанном frontier (`coverage.frontier_status=exhausted`); прогон, закончившийся бюджетом, отменой или сбоями, даёт `not_checked`.
3. `changed` для поля с несколькими значениями (телефоны) — когда ни одно известное значение на странице не встретилось; новое значение рядом с подтверждённым — `new`.
4. Gap на «непройденную ветвь» — только для релевантных ссылок (`discovery.strong_link`: контакты, команда, версия страны); слабые ссылки (продукты, новости) gap не дают, но входят в `scope_description` числом.
5. Заявленный размер каталога берётся только со страницы, где найдены люди, и только если он не меньше найденного там.

## 0.4.4.0 — 2026-10-05

**Шаг `stage-5/step-3-a2-country`: дополнение владельца к A2 от 05.10.2026, пп. 1–5 (страна выставки, вкладки отделов, проверка «не бот»).** S5 (cv0.4.3.1) принят владельцем 05.10.2026; тег `v0.4.3` поставлен локально на `b700d40` (отправить его не даёт git-прокси сессии — см. отчёт).

**Что видно.**
- Keruu: на международной странице контактов со списком стран (аккордеон, вкладки, выпадающий список, ссылки ≥ 3 стран) открывается только страна выставки; строка состояния — `Napsautetaan: Finland`. Обход идёт по ссылке на местную версию (`/fi-fi`, `/fi`, `fi.` домен), остальные страны не обходятся.
- Проверка «не бот» без клика (JS-заглушка Cloudflare / WAF): обход ждёт до 20 с; не прошла — строка `Selaintarkistus ei päästänyt läpi: <url> — katso Huomio`, в Jono `Tarvitsee huomiota` (не `Epäonnistui`).
- Новый блок **Huomio** (TZ_SELAIN §5.1, виден только при задании в `needs_attention`): `Tarvitsee huomiota: <компания> — selaintarkistus ei päästänyt läpi 20 sekunnissa: <url>`, кнопки «Avaa työselain» (рабочий браузер на этой странице; неактивна, пока идёт обход) и «Jatka käsin tehdyn toimen jälkeen» (задание идёт дальше с того же места). Пока рабочий браузер открыт, сборщик не начинает обход (один профиль).
- Страница людей с вкладками отделов: открываются все вкладки, продажи и маркетинг первыми, люди из каждой; у человека — отдел (заголовок группы или вкладка: Joakim Flakholm → `Johto`).
- Seed — уже версия страны выставки (`.fi`, `/fi/`, `fi.`): сначала она, затем версии других стран (malux.se); у людей оттуда — страна (`SE`) из `<html lang>`.

**Как работает.** `discovery.countries` (таблицы `country_names.py`): страна подписи (`Finland`, `Suomi`, `FI`), страна версии URL, «местный» seed, список стран (≥ 3), порядок отделов; `strong_link` — ссылки, мимо которых модель не может закончить обход (контакты, местная версия; при местном seed — переключатель на версию другой страны, «после»). `walk.structure` — правила до модели (TZ_SELAIN §8.4, guard-rails): страна выставки в списке стран (клик / выбор в списке / переход), все вкладки и свёрнутые разделы отделов на странице с контактами; каждое действие — один раз на URL и подпись (`checkpoint.acted`); другие страны списка модели не показываются и в frontier не попадают. `browser`: вкладки, заголовки аккордеона, выпадающие списки — кандидаты (`role`, `state`, `options`), действие `select`; кнопка без формы больше не считается «submit»; ожидание проверки «не бот» до 20 с (нужны два признака из трёх: заголовок, текст, элемент проверки; короткая страница). `extraction.sections`: разделы стран в тексте страницы (только при ≥ 3 странах), телефон в разделе — в формате его страны (`09-7422 3300` под Finland → `+358974223300`), строка с `Fax` / `Faksi` / `Telefax` — не телефон; строки названия и адреса офиса. `walk.offices`: офис раздела — одна сущность `office` (`country`, `office_name`, `address`, `phone`, `email`, binding `card` → `published_general`). `walk.context`: `department` (заголовок группы / вкладка карточки, цитата — текст заголовка перед именем) и `country` (заголовок раздела или регион `<html lang>`, locator `dom html[lang]`) у людей. `scheduler`: состояние `needs_attention` — событие `job.needs_attention` (gap `captcha` + counts), аренда продлевается, прогон не закрывается; «Jatka…» или `resume` из ARGUS → `queued`, обход продолжает с URL проверки, первым событием идёт `job.progress`.

**Найдено живой проверкой шага и исправлено до сдачи.**
1. `mailto:`/`tel:` из закрытых вкладок и разделов брались из HTML сразу: у Ledvance уходили почты 10 других стран (в шапку компании ARGUS как общие каналы), у Malux — почты людей скрытых вкладок как `unassigned_channel` (дубли людей). Теперь ссылки, которые браузер сейчас не показывает, не читаются; они берутся, когда вкладка или раздел открыты.
2. Общие каналы компании получают `country` (раздел страны или `<html lang>`), иначе шведский `Växel` Malux в ARGUS не отличить от финского `Vaihde`.
3. Пройденная владельцем проверка «не бот» оставалась в gaps `job.finished` — теперь gap снимается, когда страница открылась.
4. Панель выше экрана (с блоком Huomio — ~1250 px, кнопки Huomio за нижним краем): тело панели прокручивается, окно не выше экрана, строка версии всегда видна, при появлении Huomio панель прокручивается к нему.

**Модули.** Новые файлы: `discovery/countries.py`, `discovery/country_names.py`, `browser/scripts.py`, `extraction/sections.py`, `walk/structure.py`, `walk/entities.py`, `walk/offices.py`, `walk/context.py`, `ui/attention_lines.py`, `ui/view_attention.py`, `ui/app_browser.py`, `ui/view_scroll.py`. Изменены: `discovery`, `browser`, `extraction`, `walk`, `scheduler`, `ui`, `messages/fi.json`; `test_site/` (ledvance, malux, malux-se, варианты, проверка «не бот», `__PORT__`), `contract_server/` (история контактов компании, known_contacts, freshness, needs_attention — под пару 4).

**Решения (поправь, если не так).**
1. Факс по решению 05.10 не отправляется вовсе. FieldAudit требует учесть каждое контактное поле; факс распознаётся по подписи и контактным полем источника не считается (в аудит не попадает). Если нужен аудит `extra` с `extra_label=Fax` — поправь.
2. Страна у человека отправляется только с доказательством: заголовок раздела страны (text_span) или регион в `<html lang>` (`sv-SE`, locator `dom html[lang]`, цитата — значение атрибута). Язык без региона (`fi`) и домен страну не дают — ARGUS видит страну ещё по E.164.
3. Отдел — только из структуры страницы (заголовок группы перед карточкой, иначе вкладка); общие заголовки (`Yhteystiedot`, `Contact`), страны и названия компаний отделом не считаются. Отдел из должности не выводится.
4. «Не обходить другие страны» — для списков стран (≥ 3 стран на странице). Переключатель версий (`FI | SE`) — по фокусу: при местном seed другие версии идут после, иначе — как в 0.4.3.0 (третий язык вниз).
5. Свёрнутые разделы (не страны) раскрываются только на странице, где уже есть люди или каналы, не больше 12 на страницу.
6. Причина «не бот» — `captcha` (класс препятствия TZ_SELAIN §8.5; отдельного класса для JS-проверки в контракте нет).

## 0.4.3.1 — 2026-10-04

**Правка 1 шага `stage-5/step-2-a2-a3` — расхождения, найденные живой проверкой по тест-карте TZ_TANDEM §7 и TZ_SELAIN §13.5 стр. 5 (указание владельца: «расхождения исправь, не подгоняй»).**

**Чек-лист правки.**
1. Строка состояния Keruu после обхода задания оставалась на последней странице (`Ladataan sivua http://katsa-oy.localhost:8765/`) — теперь, как у локального теста, `Keruu valmis: N sivua, M yhteystietoa` по каждому заданию — **сделано**.
2. Причина `unresolved_access` в Jono была частным случаем (`sivustolle ei päästy (verkkotunnusta ei hyväksytty)`), а код покрывает любой неразрешённый доступ — теперь `pääsy sivustolle jäi ratkaisematta` — **сделано**.
3. ARGUS остановлен, а отправлять нечего: Lähetys показывал `Lähetetty`, хотя тест-карта §13.5 стр. 5 ждёт `Ei verkkoa`. Теперь heartbeat без ответа (HTTP 0) переводит Lähetys в `Ei verkkoa` и при пустом outbox; первый ответ после обрыва сразу отправляет ожидающее, не дожидаясь backoff (`Ei verkkoa` → `Lähetetään` → `Lähetetty`) — **сделано**.
4. Yhteys после неудачного heartbeat писал `Ei vielä heartbeatia`, хотя heartbeat были: теперь строка `Viimeksi: <время>` последнего ответа сохраняется, пока проверяется тот же worker — **сделано**.

**Модули.** `ui` (`app_collect`, `app_connection`, `app`), `delivery` (новый файл `results.py` — разбор ответа на пакет событий вынесен из `loop.py`, иначе файл > 200 строк), `scheduler` (`collector`), `walk` (`contract` экспортирует виды событий). Новые тесты: `delivery/tests/test_link.py`, `ui/tests/test_queue_lines.py`, `ui/tests/test_ui_connection.py::test_argus_down_keeps_the_last_heartbeat_and_shows_ei_verkkoa`; `test_ui_collect` проверяет строку `Keruu valmis`.

**Решения (поправь, если не так).**
1. `Ei verkkoa` в Lähetys — только когда ARGUS не ответил вовсе (HTTP 0, как у самой доставки); ответ с кодом (401, 5xx) — это связь есть, его класс показывает доставка.
2. Слова Jono для команд ARGUS — по таблице i18n TZ_SELAIN §5: pause → `Tauolla`, cancel → `Keskeytetty`. В тест-карте TZ_TANDEM §7 стр. 3/5 (сторона ARGUS) — `Keskeytetty` для «Pysäytä» и `Peruttu` для «Peruuta»; это слова ARGUS, не панели сборщика — вопрос Архивариусу в отчёте.

## 0.4.3.0 — 2026-10-04

**Пары 2 и 3 из `docs/ARGUS20_TZ_TANDEM.md` 1.1 — шаги A2 «Пакет и контакты» и A3 «Надёжность и управление» одним шагом `stage-5/step-2-a2-a3` (указание владельца 04.10.2026), плюс дополнение владельца по стране выставки.** Прод `/api/collector` (B2/B3) ещё не принят; сборщик проверен против своего `contract_server/`, который теперь реализует весь контракт и проверяет каждый запрос по OpenAPI.

**Что видно в панели (только блоки TZ_SELAIN §5.1).**
- Keruu: «Käynnistä» включает сбор заданий ARGUS (`collecting=true`): claim с `max_jobs` = свободные слоты (≤ 8), обход по одному заданию, Chrome сам открывает сайт компании. Активна при модели, Chrome, рабочей связи (Yhteys) и без STOP; подсказка говорит, чего не хватает (`Keruu vaatii yhteyden ARGUSiin (Testaa yhteys)`). «Pysäytä» останавливает обход и claim, outbox продолжает отправку. Ручной режим остался: поле «Yrityksen verkkosivu» + кнопка «Testaa paikallisesti» (или Enter), подпись «Paikallinen testi — ei lähetetä ARGUSiin».
- Jono: `Ladataan…` / `Jonon lataus epäonnistui` / `Ei tehtäviä` / таблица Yritys · Vaihe (`Odottaa` / `Selain käsittelee` / `Viimeistellään`) · Henkilöt · Kanavat · Lähteet · Tila (`Valmis` / `Osittain valmis` + причина словами / `Epäonnistui` / `Keskeytetty` / `Tauolla` / `Pysäytetty` / `Odottaa yhteyttä ARGUSiin`); отказ ARGUS — словами в строке компании: `Hylätty N: verkkotunnusta ei ole hyväksytty`.
- Lähetys: `Odottaa lähetystä: N · Lähetysvirhe: N · p95 (1 min): X s` и `Lähetetty` / `Lähetetään` / `Ei verkkoa` / `Lähetys epäonnistui` (красным). Jono и Lähetys перечитывают локальную SQLite раз в секунду.

**A2 — как работает.** Задание из claim хранится локально целиком (`jobs`). `walk` в режиме задания: стартовый URL — `seed_urls`, хосты — только `approved_hosts` задания (K7 ред. 02: основание `seed`; seed, ушедший редиректом на другой хост, — gap `domain_ownership_unresolved`, с того хоста ничего не отправляется), бюджет прогона = политика минус израсходованное кампанией. На каждую новую страницу — снимок в `evidence_uploads` (`POST /evidence`: точные байты, sha256, canonical text) и `source.processed`; на каждого человека и общий канал — `contact.observed` (новые поля того же человека — `contact.enriched`) с `evidence_id`, locator `text_span` (или `json_pointer`/`dom` для JSON-LD и ссылок без видимого текста), `quote`, `entity_type`, `binding`, `extraction_status` и `field_audit` страницы (каждое найденное поле → `mapped` с id наблюдения, `dropped_contact_fields=0`). Привязка — по DOM: имя и значение в одной небольшой карточке без других людей → `card`/`table_row` + `confirmed` (сервер даёт `published_direct`), только близость → `proximity_only` + `ambiguous` (`inferred`). Канал без человека: общий ящик, строка «Vaihde/Tel.», JSON-LD → `organization_channel` (`published_general`); строка с «office/toimisto» → `office`; прочее → `unassigned_channel` (`inferred`). Событие и запись outbox — одна транзакция SQLite с локальной строкой `observations`. Поток доставки: сначала снимки, потом события run'а по seq, ≤ 50 событий или 2 с, наблюдение не уходит раньше своего снимка. `job.finished`: `run_result_status`, `completion_reason`, `coverage` (`confirmation=unverified`, `basis`, `scope_description`, `found_count`, `gap_count`), gaps, checkpoint с frontier, budget, модели по назначению. `model.called` — на каждый вызов: токены, мс, `cost_eur=0`, `local=true`.

**Страна выставки (дополнение владельца).** `scope.priority_countries`/`priority_languages` → фокус обхода: ссылки на версию сайта для страны/языка (`Suomi`, `/fi/`, `?lang=fi`) и на местный офис (`Finland office`, `Suomen toimisto`, города) поднимаются в ранжировании; у компании без офиса в стране — родной язык сайта и английский, вверх идут export / Nordic / Scandinavia / international sales и marketing; третий язык — вниз. Модель получает то же правило в запросе действия (`FOCUS: …`); пока непосещена сильная ссылка (контакты/команда/страна, вес ≥ 10), модель не может закончить обход. Регион телефона — по странице (ccTLD, `lang` с регионом, путь `/fi/`, язык страницы), иначе страна выставки: немецкий `0711 123 4500` → `+497111234500`.

**A3 — надёжность и управление.** Перезапуск панели: задания, run, seq, checkpoint (посещённое, frontier, люди, id наблюдений), outbox и команды — в SQLite; прерванный обход продолжается с последней страницы, дублей нет (стабильные id). Обрыв сети: обход идёт, доставка `Ei verkkoa` с backoff, после связи — всё по порядку. Истечение аренды (локально по `lease_expires_at` или `expired`/`mismatch` в heartbeat, или 409 `lease_*` на отправке): новые действия прекращаются, `reconcile` → `resume` (тот же run и seq) или `drain_only` (только слив). Команды из ответа heartbeat: pause / resume / cancel / continue исполняются (cancel → `job.finished` `cancelled`/`manual_cancel`, если run начат) и подтверждаются в следующем heartbeat (`command_id` в acks; повтор — `already_applied`). «Pysäytä» и файл `STOP` останавливают обход и claim; outbox продолжает. Журнал `<данные>/logs/collector-YYYY-MM-DD.log` с префиксами Lokit `http` / `browser` / `extraction` / `delivery` / `model`, без значений контактов и токенов, 14 дней.

**Модули.** Новые: `scheduler`, `delivery`, `collector/tests/contract/`. Изменены: `api_client` (весь рабочий набор операций, генератор), `walk`, `browser`, `discovery`, `extraction`, `normalization`, `evidence`, `storage` (миграция 2), `models`, `runtime`, `ui`, `contract_server/` (весь контракт), `test_site/` (nordtec, vogel, katsa), гейты `check_i18n`, `check_codegen`.

**Найдено и исправлено попутно.** `evidence` писал снимки через `write_text`: на Windows `\n` превращался в `\r\n`, и байты файла переставали совпадать со своим sha256 — теперь точные utf-8 байты. Гейт `check_i18n` принимал значения провода (`job.finished` в сгенерированном клиенте) за ключи панели — сгенерированный `api_client` исключён из проверки.

**Решения (поправь, если не так).**
1. A2 и A3 — один шаг ветки `stage-5/step-2-a2-a3` (название ветки — указание владельца), одна версия `0.4.3.0`: линия 0.4.x по TZ_TANDEM §11 п.4, «следующий свободный номер» (§3); ожидавшиеся 0.4.3.0/0.4.4.0 для A2/A3 сведены в одну, A4 получит следующий свободный номер. Правило CLAUDE.md №3 (версия = этап.шаг) здесь расходится с TZ_TANDEM §11 п.4 — принято TZ_TANDEM. Тег не ставлю (как и раньше — при согласии владельца, TZ_TANDEM §11 п.4: `v0.4.M`).
2. «Käynnistä» по TZ_TANDEM A2.1 — сбор ARGUS; ручной обход получил свою кнопку «Testaa paikallisesti» в своей строке (A1.5 оставляет ручной режим). «Keskeytä» по-прежнему неактивна (S5).
3. Человек отправляется и без канала (имя + должность, TZ_SELAIN §8.11; FieldAudit не позволяет молча терять поле): только имя — `ambiguous`; канал, раскрытый позже на той же странице, приходит как `contact.enriched`. Таблица панели по-прежнему показывает только людей с каналом (0.4.1.1).
4. Привязка — только по структуре DOM, не по группировке модели; без браузерной привязки поле — `ambiguous`.
5. Фокус страны меняет порядок обхода, а не фильтрует людей: все люди на пройденных страницах отправляются.
6. «finish» модели = релевантный frontier исчерпан (`frontier_status=exhausted`), но не раньше, чем пройдены сильные ссылки (guard ≥ 10); `confirmation` всегда `unverified`, пока нет total каталога.
7. Неудачное действие (таймаут, перекрытый элемент) — gap (`timeout`/`network_error`/`unsupported_widget`), обход продолжается; три подряд — конец (`partial`/`technical_failure`). Это меняет 0.4.1.2, где первый неудачный клик завершал обход.
8. `job.progress` — не чаще раза в 15 с; `source.blocked` — на каждый gap.
9. Jono показывает активные задания и изменённые за последние 24 ч.
10. Регион телефона без контекста страницы — страна выставки задания (не FI по умолчанию); у ручного обхода — FI, как раньше.
11. Контракт-сервер — stdlib, состояние в JSON (`--state`), не SQLite/FastAPI из TZ_SELAIN §2.1: стенду нужна только сохранность между перезапусками. Решения стенда, которых нет в ТЗ: токен завершённого run'а остаётся токеном слива (повтор `job.finished` — `duplicate`); `email_pattern` не канал и не проверяется по K7; случаи вне таблицы §9.4 → `inferred`.
12. Reconcile из потока доставки делается, только если токен, получивший 409, всё ещё текущий (иначе аренду уже обновил другой поток).

**Не проверено живьём на MAIN-PC.** Windows, настоящий Chrome, qwen2.5:14b на RTX 4090 и боевой `https://argus.gridex.fi/api/collector` (B2/B3 ещё не на проде). Проверено в Linux-контейнере: 387+ тестов (настоящая панель под Xvfb, Chromium, контракт-сервер, тестовый сайт, подмена модели), живой прогон панели — в отчёте `ARGUS20_COLLECTOR_STAGE5_REPORT.md`.

## 0.4.2.0 — 2026-10-04

**Пара 1 «Связь» из `docs/ARGUS20_TZ_TANDEM.md` (решение владельца 03.10.2026 — связать сборщик с ARGUS сейчас, не дожидаясь блока 5). Шаг A1, владелец дал «ок» 04.10.2026.** Прод `/api/collector` ещё не существует (параллельно его строит сессия ARGUS, шаг B1); до «ок» на пару 2 сборщик проверен против своего `contract_server/` на loopback — живая проверка против `https://argus.gridex.fi` будет сделана по факту готовности B1, токен внесёт владелец.

**Что видно.** Блок Yhteys — больше не заглушка: поля «ARGUS-osoite» (по умолчанию `https://argus.gridex.fi`), «Worker-tunnus», «Tunnus (token)» (поле только для ввода, никогда не показывает сохранённое значение целиком), кнопка «Testaa yhteys» → один heartbeat; состояния `Ei yhteyttä` / `Tarkistetaan…` / `Yhdistetty` / `Tunnus hylätty` (красным) / `Ei verkkoa: <деталь>` (красным); строка «Viimeksi: <время>» / «Ei vielä heartbeatia». Успешная проверка сохраняет адрес+worker_id (`worker_auth`, не секрет) и токен (DPAPI) и дальше шлёт heartbeat каждые 30 с, пока панель открыта — без повторного ввода при следующем запуске. Поле «Yrityksen verkkosivu» получило подпись «Paikallinen testi — ei lähetetä ARGUSiin»: ручной обход по-прежнему ничего не отправляет в ARGUS (контракт не примет наблюдения без задания — пары 2+).

**Новые модули.**
- `api_client` — генерируется из `docs/ARGUS20_COLLECTOR_OPENAPI.json` (`scripts/gen_api_client.ps1` → `scripts/gen_api_client.py`, логика в `scripts/codegen/`), не пишется руками (правило №14). Манифест операций — пока только `heartbeat` (`scripts/codegen/manifest.py`); остальные операции контракта (claim, evidence, events, reconcile, control, batches, статусы) относятся к парам 2+ и появятся там же, где понадобятся — расширением манифеста и перегенерацией, без переписывания вручную. Гейт `check_codegen` проверяет, что регенерация — no-op (`git diff` пуст).
- `worker_auth` — локальное хранение: `worker_connection.json` (адрес + worker_id, не секрет) и `worker_token.bin` (токен через DPAPI, `CryptProtectData`/`CryptUnprotectData`; вне Windows — запасной XOR только для тестов). `mask_token` показывает исключительно последние 4 знака (TZ_TANDEM A1.2), остального токена нигде нет — ни в логах, ни на экране.
- `contract_server/` — опорный тестовый сервер (стенд, не прод) с единственным эндпоинтом `POST /api/collector/workers/heartbeat`: реестр токенов в памяти (`test-token-abc` → `worker-main-pc` по умолчанию, `--token TOKEN:WORKER_ID` добавляет свои), проверка `schema_versions` (ожидает `1.1`), 401 `unauthorized` / 400 `invalid_input` / `schema_unsupported`, пустые `leases`/`commands` (заданий ещё нет). `python -m contract_server.server --port N` поднимает его отдельно от панели.

**Сетевой слой.** `network.proxy: system | direct` в `config.yaml` (по умолчанию `system`) решает, идут ли запросы к ARGUS через системный прокси Windows; loopback (127.0.0.1/localhost, т.е. `contract_server/` на этапе разработки) всегда напрямую независимо от настройки — иначе прокси отвечает 502 на локальный адрес (тот же случай, что и у локальной модели, коммит `6b6467b`).

**Живьём на MAIN-PC проверено:** `pytest` гоняет реальную панель (`tk.Tk()`, не заглушка) против реально поднятого `contract_server/` — «Testaa yhteys» с верным токеном даёт `Yhdistetty` и сохраняет связку, с неверным — `Tunnus hylätty` без сохранения токена (`collector/src/argus_collector/ui/tests/test_ui_connection.py`); отдельно руками через `install.ps1` → `scripts\start.ps1` → реальный `contract_server.server` на другом порту.

**По ходу работы найдены и исправлены три бага, не связанные с A1 напрямую, но вскрытые при его сборке:**
1. Гейт `import_linter` был тихим no-op: `python -m importlinter.cli lint_imports` молча импортирует модуль и ничего не проверяет (у `importlinter` нет `__main__.py`); настоящий вызов — `importlinter.cli.lint_imports_command()`. После починки гейт впервые реально заработал и сразу нашёл 3 предсуществующих нарушения слоёв в тестах (`walk` → `browser.session` напрямую, `ui.tests.test_ui` → `diagnostics.tests`/`runtime.service` напрямую) — все три исправлены (импорт `PageState` через `browser.contract`; `runtime.version_status` и `diagnostics`-фикстура `sample_document` стали доступны/локальны без захода во внутренности чужого модуля).
2. `subprocess.run(..., text=True)` без `encoding="utf-8"` в `scripts/gates/check_tools.py` и `check_codegen.py` падал с `UnicodeDecodeError` на этой (русской) кодовой странице Windows, если инструмент печатал что-то вне cp1251 (тот же класс ошибки, что и у `diagnose.ps1` в 0.4.1.1) — добавлен явный `encoding="utf-8", errors="replace"`.
3. `contract_server`: клиент, отправивший тело запроса без токена, иногда получал `ConnectionAbortedError` вместо ответа 401 — Windows рвёт TCP-соединение, если сервер закрывает его, не вычитав присланные байты. Обработчик теперь всегда вычитывает тело прежде, чем отклонить запрос.

**Решения (поправь, если не так).**
1. `worker_id` вводится владельцем в панели отдельным полем (третье поле рядом с адресом и токеном), а не только получается из токена: `HeartbeatRequest.worker_id` обязателен на проводе, а B1 ещё не описал формат самого токена настолько, чтобы полагаться на его внутреннюю структуру.
2. `api_client` генерируется только для операций из явного манифеста (сейчас — только `heartbeat`), а не для всего OpenAPI сразу: остальные операции относятся к парам 2–5 и будут не нужны до соответствующего шага — генерация «на будущее» без явной надобности противоречит правилу «не больше, чем требует задача».
3. `argus.base_url` в `config.example.yaml` теперь по умолчанию `https://argus.gridex.fi` (раньше — пустая строка): это и есть значение по умолчанию поля адреса в блоке Yhteys per TZ_TANDEM A1.2.
4. Токен, введённый в поле и провалившийся при проверке (`Tunnus hylätty` или сетевая ошибка), не сохраняется — остаётся прежний сохранённый токен (если был), чтобы одна опечатка не затёрла рабочую связку.

**Не проверено живьём:** реальный `https://argus.gridex.fi/api/collector` (сервер B1 ещё не существует) — тест-карта TZ_TANDEM §5 пп.1 и 3–4 (сторона ARGUS, Soittolista) требует сессии ARGUS и будет пройдена по факту готовности B1.

## 0.4.1.3 — 2026-10-03

**Падающий гейт `install.ps1` примерно в половине запусков.** `scripts\run_gates.py`/`pytest` внутри `install.ps1` несколько раз подряд падали на `test_panel_drives_a_real_walk_with_the_fake_model` с `_tkinter.TclError` (`invalid command name "tcl_findLibrary"` либо `couldn't read ... tk.tcl`) прямо на `tk.Tk()`, хотя тест зелёный в одиночку. Похоже на гонку Windows/Tcl при повторном создании `Tk()` в одном процессе вскоре после `destroy()` предыдущего окна (`test_ui.py` создаёт и уничтожает окно прямо перед этим тестом). Правка не трогает рантайм панели (`ui/contract.py` создаёт ровно один `Tk()` за процесс — там это не воспроизводится): новый `ui/tests/conftest.py::make_tk_root()` оборачивает `tk.Tk()` в короткий повтор (до 3 попыток, пауза 0.3 с) и используется в обоих местах, где тесты открывают настоящее окно (`test_ui.py`, `test_ui_walk.py`). Три подряд живых прогона `pytest -q` на MAIN-PC после правки — зелёные.

## 0.4.1.2 — 2026-10-03

**Живая проверка, продолжение.** Два дальнейших находа:

1. Три реальных сайта (ensto.com, abb.fi, phoenixcontact.fi) показали, что крупные корпоративные сайты почти всегда ставят cookie-баннер; модель иногда успевает пройти несколько страниц до него, но рано или поздно клик по перекрытому баннером элементу зависает до таймаута (10 с) — и это роняло весь обход в `Keruuvirhe`, даже если до того уже было найдено несколько контактов. Баннеры по-прежнему вне этого шага (решение №8 к 0.4.1.0, S3), но единичный неудачный клик не должен стирать то, что уже нашли. Исправление: `walk/runner.py::_walk` ловит `browser.ActionError` (новый реэкспорт `playwright.sync_api.Error` из `browser/contract.py`) вокруг `_perform` и завершает обход как обычный «Keruu valmis» с тем, что успели найти, вместо красной ошибки. Новый тест `test_walk_resilience.py::test_a_failed_click_ends_the_walk_cleanly_with_what_was_found` подменяет `_perform`, чтобы падать на втором шаге, и проверяет чистое завершение.
2. Тест `test_ui.py::test_window_renders_keruu_block_and_live_rows` был жёстко завязан на `"cv0.4.1.0 ("` — ломался при каждом поднятии VERSION. Исправлено на сравнение с реальным `runtime.current_version_status().file_version`.

Заодно: `walk/tests/test_walk.py` разросся сверх 200 строк (гейт `size`) — общие фикстуры (`site`, `gold`, `_settings`) вынесены в новый `walk/tests/conftest.py`, резистентный тест — в `walk/tests/test_walk_resilience.py`.

Живьём на MAIN-PC после этой правки проверено: обход тестового сайта — ровно 7 контактов (не 9), у всех оба канала, панель показывает `Malli: paikallinen (GPU)` и читаемую кириллицу в «Resurssit». Обход настоящих сайтов компаний подробно — в сдаче этапа, не здесь.

## 0.4.1.1 — 2026-10-03

**Живая проверка на MAIN-PC (первая)** нашла две ошибки, не видные в контейнере без Windows/GPU; обе исправлены этой правкой.

1. **Панель показывала карточки без канала связи.** `walk/runner.py::_parse_cards` записывал и показывал в таблице контакт сразу, как только модель находила имя — даже если на странице ещё не было ни телефона, ни почты (например, карточка на `team.html` до нажатия «Näytä yhteystiedot», или борд-страница вовсе без личных контактов). После раскрытия той же карточки на странице с другим текстом она разбиралась заново и добавлялась второй строкой — первая, пустая, оставалась в таблице. На `ensto.com/.../owners-board-management/` это дало 10 строк без единого телефона или почты. Исправление: `_parse_cards` пропускает запись и событие `contact`, если у карточки нет ни телефона, ни почты; при появлении канала на той же странице позже карточка разбирается заново как обычно (ключ состояния — URL + хеш текста — не меняется). Тест `test_walk_finds_every_gold_person_with_evidence` ужесточён: ровно 7 контактов (не 9), и у каждого обязателен хотя бы один канал.
2. **Строка ОС в «Resurssit» — нечитаемая кракозябра.** `diagnostics/repository.py::run_powershell_diagnose` запускает `diagnose.ps1 -Json` через `subprocess.run(..., text=True)` без `encoding`; на этой машине (русская локаль) Python декодировал корректный UTF-8 вывод PowerShell кодовой страницей `cp1251` ANSI по умолчанию. Байты от PowerShell были верными (проверено посимвольно); исправление — `encoding="utf-8"` явно в `subprocess.run`. Затронуло только отображение `resources.os` (Windows 11 с русской локализацией Caption); остальные поля ASCII и не пострадали.

Обе найдены и исправлены в одном цикле живой проверки (без отдельной сдачи владельцу между ними): правка `fix-1` к шагу stage-4/step-1.

## 0.4.1.0 — 2026-10-03

**Решение владельца 03.10.2026 (меняет порядок этапов ТЗ).** «Нейросеть на моей RTX 4090, которая по-настоящему ходит по сайту компании в моём обычном Chrome» — строится сейчас, до S1/S2. Содержание этого шага — S4 (локальная модель) и S3 (браузерные действия) вместе, поэтому `VERSION` = `0.4.1.0`; HTTP-проход (S2), claim/outbox/контракт-сервер (S1) остаются следующими этапами. Ветка та же, `stage-0/step-1-diagnostics` (git ведёт основная сессия).

**Что видно.** Блок Keruu: поле «Yrityksen verkkosivu», «Käynnistä» (активна, когда `Malli` не `ei ladattu`, Chrome доступен и нет STOP; иначе подсказка почему), «Pysäytä» (активна во время обхода); строка состояния (`Sivu n/15: URL`, шаги «Ladataan sivua», «Poimitaan yhteystietoja», «Malli lukee henkilökortteja», «Malli valitsee seuraavan toimen», «Siirrytään: URL», «Napsautetaan: текст», «Mallivirhe: …», итог «Keruu valmis: N sivua, M yhteystietoa» / «Keruu pysäytetty» / «Keruuvirhe: …» красным); «Löydetty: N yhteystietoa»; таблица Nimi · Titteli · Puhelin · Sähköposti · Lähde, строки появляются по ходу обхода, двойной клик по строке открывает источник в браузере. Chrome открывается видимым окном с профилем `browser-profile` и сам ходит по сайту. В Resurssit у строки `Malli` появилась строка `Malli <имя> @ <endpoint>: <деталь>`; после каждого обхода Resurssit перечитываются (Ollama грузит модель в VRAM при первом вызове, поэтому `paikallinen (GPU)` появляется после первого обхода).

**Как работает обход (`walk`).** Загрузка страницы → снимок (HTML + видимый текст, sha256, `%LOCALAPPDATA%\Gridex\ArgusCollector\evidence\<sha[:2]>\<sha>.html|.txt`, строка `evidence_manifest`) → детерминированные каналы (`tel:`, `mailto:`, JSON-LD, `data-cfemail`, `(at)`/`[dot]` в тексте) → если на странице есть признаки контактов, модель разбирает карточки людей; каждое поле проходит verbatim-проверку: имя и должность должны быть найдены в каноническом тексте снимка, телефон/email — либо quote найден в тексте и нормализуется в значение, либо нормализованное значение совпадает с каналом из HTML (тогда quote и locator канала); остальное отбрасывается → модель выбирает действие из ограниченного списка (`navigate <index>` по ссылке, `click <index>` по кнопке, `scroll`, `finish`); неверный ответ или ошибка модели → детерминированный fallback (лучшая ссылка по рангу или finish). Только approved hosts (seed + redirect, точное совпадение), соцсети не открываются, документы не открываются, submit не нажимается, `mailto:`/`tel:` не нажимаются. Бюджет страниц — `walk.page_budget` (15). Файл STOP и «Pysäytä» проверяются между шагами. Каждый вызов модели — строка `model_calls` (provider `local`, модель, purpose `walk.cards`/`walk.action`, токены, мс, `cost_eur=0`, ошибки тоже).

**Модель.** `scripts/install_model.ps1` (PS 5.1, ASCII): `nvidia-smi` → Ollama (установлен? иначе `curl.exe` скачивает `OllamaSetup.exe`, при неудаче печатает URL и путь `%TEMP%\OllamaSetup.exe` для ручной загрузки, затем перезапуск скрипта) → `OLLAMA_CONTEXT_LENGTH=16384` в пользовательское окружение (Ollama по умолчанию 4k, обход шлёт до ~6k токенов) → перезапуск сервера при изменении → `ollama pull qwen2.5:14b-instruct` (при неудаче — GGUF-файл в `%LOCALAPPDATA%\Gridex\ArgusCollector\models\` и `ollama create`, URL печатается) → тестовый вызов и `ollama ps` (ожидается `100% GPU`). Все loopback-вызовы в PowerShell — `HttpWebRequest` с `Proxy = $null`; в Python — `urllib` с `ProxyHandler({})`.

**Тесты и стенды.** `test_site`: `team.html` (контакты двух людей появляются только после кнопки «Näytä yhteystiedot», ссылка «Seuraava sivu»), `team-2.html` (email в виде `jukka.laine (at) fixture.example`, телефон текстом, ссылка на LinkedIn, которую обход не открывает), JSON-LD на главной; gold — 7 человек с признаком `how` (`link`/`button`/`text`). `collector/tests/fake_model_server.py` + `walk/tests/fake_policy.py` — подмена OpenAI-совместимого endpoint (только тесты; возвращает людей из gold, которых видит в тексте, плюс выдуманного «Ghost Person», которого verbatim-проверка обязана отбросить). Интеграционный тест обходит сайт headless-Chromium и проверяет всех 7 людей с evidence (quote совпадает с текстом снимка по span), отсутствие «призрака», клик по кнопке, пагинацию, строки `model_calls` с нулевой стоимостью, остановку по callback и по STOP. Тест панели под Xvfb запускает настоящий обход кнопкой и видит строки в таблице.

**Гейты.** `check_no_cyrillic` дополнительно требует чистый ASCII в `*.ps1` (PS 5.1 читает файл без BOM как ANSI). Слои import-linter: `ui → walk → browser|extraction|diagnostics → discovery|models|evidence → normalization|storage → runtime`. `mypy --strict` проходит и с `--platform win32`.

**Модули.** Новые: `storage`, `normalization`, `evidence`, `models`, `extraction`, `discovery`, `walk`. Изменены: `browser` (`session.py`), `diagnostics`, `runtime` (`model.name`, `walk.page_budget`), `ui`, `test_site`, `scripts/diagnose.ps1`, `scripts/install.ps1`, новый `scripts/install_model.ps1`, `config.example.yaml`.

**Решения (поправь, если не так).**
1. Модель — `qwen2.5:14b-instruct` через Ollama (Q4_K_M ≈ 9 ГБ VRAM + 16k контекст — свободно в 24 ГБ; у 14B заметно лучше JSON-дисциплина и финский, чем у 7–9B; `llama3.1:8b` — запасной вариант в `config.yaml`). Выбор «по испытаниям» (ТЗ §4.2) остаётся: модель меняется одной строкой `model.name`.
2. Endpoint — OpenAI-совместимый `/v1` (Ollama по умолчанию, llama.cpp server без изменений кода). `diagnose.ps1` и панель проверяют `GET <endpoint>/models` и требуют, чтобы модель была в списке; `/health` больше не используется.
3. Новый модуль `walk` (нет в списке §11): оркестратор одного обхода. `scheduler` остаётся для пакетов/аренды S1; `walk` станет тем, что `scheduler` запускает на каждую компанию.
4. Обход ведётся с панели по одному URL без задания ARGUS: approved hosts = seed + его redirect; основания `linked_from_contact_section`/`business_id_match` придут с заданиями S2.
5. Два вызова модели на страницу (карточки — только при признаках контактов; действие — всегда), а не один: отдельные purpose в `model_calls`, лучшая точность разбора.
6. Verbatim-правило строже ТЗ: значение, которого нет ни в тексте снимка, ни среди каналов HTML, не записывается вообще (а не помечается `inferred`).
7. Обход и «Avaa työselain» делят один профиль Chrome, поэтому запуск обхода при открытом рабочем браузере даёт ошибку «Sulje työselain ennen keruuta», а кнопка «Avaa työselain» неактивна во время обхода.
8. Cookie-баннеры, формы (включая поиск по сайту), документы, iframe/shadow DOM, препятствия (captcha/login) — не в этом шаге; они в S3-правках. Submit-кнопки не нажимаются.
9. Normalised email целиком в нижнем регистре (quote хранит исходное написание).
10. `install.ps1` заменяет `config.yaml` от 0.0.1.0 (без `model.name`, старый endpoint `:8080`) на новый пример с копией `config.yaml.bak` — секретов в файле нет.
11. `OLLAMA_CONTEXT_LENGTH=16384` ставится в пользовательское окружение, а не в Modelfile: так работает и `ollama pull`-модель, и трей-приложение Ollama после перезагрузки.
12. Готовность страницы: DOMContentLoaded + `load` (≤ 10 с) + 0,8 с; навигация 45 с (§8.5). Повторный ключ состояния (URL + хеш текста) не разбирается заново.
13. `models` стоит ниже `diagnostics` в слоях, чтобы диагностика использовала тот же `health()`; `extraction`, `browser` не зависят от `models` (§11).

**Не проверено живьём.** Windows, настоящий Chrome (`channel="chrome"`), Ollama на RTX 4090, `install_model.ps1` (curl.exe, тихая установка `/VERYSILENT`, `ollama ps`), `diagnose.ps1` с `HttpWebRequest`, `install.ps1` с заменой config — всё писалось в Linux-контейнере без PowerShell и GPU. Точность настоящей модели на реальных сайтах не измерена; подмена модели в тестах проверяет только контракт и защиту от выдумок.

## 0.0.1.0 — 2026-10-03

Этап S0, шаг 1 «диагностика» (TZ_SELAIN §2.3, тест-карта §13.1). Ветка `stage-0/step-1-diagnostics`.

**Что видно.** Панель `ARGUS Selain` (tkinter, одно окно, светлая тема, финский из `collector/messages/fi.json`): внизу слева `cv0.0.1.0 (<дата> klo <время>) <hash>` из `VERSION` + `build.json`, без установки — `cv0.0.1.0 (ei asennustietoa)`; блок Yhteys — `Yhteys: Ei yhteyttä`; блок Keruu — «Käynnistä» / «Keskeytä» / «Pysäytä» и обе настройки автозапуска есть и неактивны; блок Resurssit — строки ОС, Chrome, модель, диск, память, NVIDIA из `diagnostics` (ошибка проверки — красной строкой); кнопка «Avaa työselain» открывает видимый Chrome с профилем `%LOCALAPPDATA%\Gridex\ArgusCollector\browser-profile` на тестовом сайте `http://127.0.0.1:8765/`, строка состояния: открывается / открыт / закрыт / ошибка с текстом. Файл `STOP` (корень репо или каталог данных) — красный баннер с путями.

**Скрипты.** `scripts/diagnose.ps1` (PS 5.1): Windows, Chrome, NVIDIA (nvidia-smi, иначе Win32_VideoController), RAM, диск, модель — состояния словами из `fi.json`, без «unknown»; `-Json` — документ `argus-collector-diagnose/1`, который панель разбирает и сверяет с теми же правилами в Python. `scripts/install.ps1`: только `main` с чистым деревом, Python 3.12 с tkinter, venv с закреплёнными зависимостями (`requirements*.txt`), гейты и pytest до копирования, копия дерева в `%LOCALAPPDATA%\Gridex\ArgusCollector\app`, `build.json` (версия, коммит, дата), `config.yaml` из примера, ярлык «ARGUS Selain» на рабочем столе; любой красный гейт — установки нет. `scripts/start.ps1` (`-Console` для вывода ошибок). Гейты: `scripts/run_gates.py` / `run_gates.ps1` — `version`, `no_cyrillic`, `size`, `docs`, `i18n`, `legacy`, `ruff`, `mypy --strict`, `import-linter`, `pip-audit`; обёртки `check_*.ps1`.

**Тестовый сайт.** `test_site/server.py` (stdlib), фикстура `fixture_oy`: главная, контакты (3 человека с должностью, email, телефоном), footer; gold `test_site/gold/fixture_oy.json`; тест сверяет gold с HTML.

**Модули.** Новые: `runtime`, `diagnostics`, `browser` (S0-часть), `ui`, `test_site/`. Реестр — `ARGUS20_COLLECTOR_MODULES.md`.

**Решения (поправь, если не так).**
1. Панель — tkinter без веб-сервера, как записано в TZ_SELAIN §7; проверяется headless под Xvfb (в CI) и живьём на MAIN-PC.
2. «Avaa työselain» в S0 стоит в блоке Resurssit (под строками ресурсов), потому что блок Huomio показывается только при задании `needs_attention`, а тест-карта S0 требует кнопку без заданий. С S3 кнопка появляется и в Huomio.
3. Подпись состояния — `Yhteys: Ei yhteyttä` (по §5.1 и тест-карте, не «API: ei yhteyttä» из §2.3).
4. Профиль Chrome — `browser-profile` (TZ §7), не `chrome-profile`.
5. `playwright install` не выполняется: на Windows используется установленный Chrome (`channel="chrome"`); встроенный Chromium — только вне Windows (CI).
6. Состояние модели: `Malli: ei ladattu`, если `<endpoint>/health` не отвечает; `paikallinen (GPU)`, если отвечает, GPU — NVIDIA и занято ≥ 1024 МБ видеопамяти; иначе `paikallinen (CPU)`. Endpoint — `model.endpoint` в `config.yaml` (по умолчанию `http://127.0.0.1:8080`).
7. Диск: `low` при > 85 % занято (WAYS §9), в панели — `Levytila alle 15 %`.
8. `fi.json` в S0 содержит только ключи, которые панель и `diagnose.ps1` используют сейчас (гейт `check_i18n` требует точного совпадения); остальные ключи §6.1 добавляются этапом, который их использует. Добавлены ключи `resources.os`, `resources.gpu.*`, `resources.gpuMemory`, `resources.memory`, `resources.disk`, `resources.checking`, `resources.error`, `browser.*`, `stop.active`, `version.notInstalled`, `version.error`.
9. Блок Yhteys в S0 — только заголовок и состояние: адрес ARGUS, «Testaa yhteys», worker_id и heartbeat появляются в S1 вместе с контракт-сервером (кнопка без работы не показывается).
10. `check_i18n` — на Python (`scripts/gates/check_i18n.py`), не `.mjs`: Node на MAIN-PC не нужен. `check_legacy`: одно совпадение — предупреждение, три подряд — красный.
11. Task Scheduler (автозапуск) — не в S0; настройка `Käynnistä Windowsin kirjautuessa` показана неактивной, реализуется в S5.
12. Установленная копия живёт в `%LOCALAPPDATA%\Gridex\ArgusCollector\app` (robocopy /MIR без `.git`, `.venv`, `STOP`, `config.yaml`), чтобы панель не зависела от рабочего дерева разработчика.
13. Содержимое тестового сайта в S0 — на английском (код только на английском); финские подписи («Yhteystiedot», «puh.») добавляются в фикстуры S2 вместе с извлечением.
14. STOP блокирует сбор (кнопки сбора неактивны и так) и показывается баннером; «Avaa työselain» при STOP остаётся доступной — это ручной инструмент, не сбор.

**Не проверено живьём.** Тест-карта §13.1 на MAIN-PC (Windows, NVIDIA, настоящий Chrome) не пройдена: разработка шла в Linux-контейнере без PowerShell. См. `ARGUS20_COLLECTOR_STAGE0_REPORT.md`.

## 0.0.0.0 — 2026-10-03

Стартовый `main` репозитория сборщика по решению владельца 03.10.2026: отдельный репозиторий `gridex-argus-collector` и отдельная сессия на Windows MAIN-PC (TZ_SELAIN §15 п.3). Кода и панели нет; первый шаг — этап S0 (`0.0.1.0`, TZ_SELAIN §2.3, тест-карта §13.1).

**Положено.** `START_HERE.md`; `CLAUDE.md` и `AGENTS.md` (одинаковые правила ARGUS, адаптированные под сборщик); `VERSION`, `README.md`, `.gitignore` (`STOP`, `config.yaml`, `.env` не коммитятся), `.gitattributes` (LF, CRLF для `*.ps1`/`*.bat`/`*.cmd`). Документы из `gridex-argus20@196d2ba` — в `docs/` под исходными именами; опись и контрольные суммы — `docs/KIT_MANIFEST.md`.

**Решения (поправь, если не так).**
1. Стартовая версия `main` — `0.0.0.0`; первая сдача S0 поднимает её до `0.0.1.0`.
2. Документы ARGUS лежат копиями в `docs/` под исходными именами, чтобы ссылки ТЗ (`docs/ARGUS20_ASSETS.md`, `docs/legacy_line_hashes.txt`) совпадали буквально. Подмодуль не используется: у сборщика нет доступа к репозиторию ARGUS. Синхронизирует владелец коммитом `docs: sync from gridex-argus20@<hash>`.
3. В шаблон сдачи добавлены строки «Живая проверка» и «Чек-лист правки» — по образцу CLAUDE.md ARGUS п.2а, 2б.
4. Кириллица разрешена в `docs/` и в корневых `CLAUDE.md`, `AGENTS.md`, `START_HERE.md`; гейт проверяет каталоги кода — как `check_no_cyrillic.sh` в ARGUS.
5. Открыты и ждут «ок» владельца: TZ_SELAIN §15 пп.1, 2, 4–8, в том числе потолок €150 на разработку (п.5).
