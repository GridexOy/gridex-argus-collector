# ARGUS20_TZ_SELAIN — локальный сборщик контактов (Selain) на Windows

**Версия:** 3.0 · **Дата:** 03.10.2026 · **Правка:** 03 · **Владелец:** Игорь
**Заменяет:** ARGUS20_TZ_SELAIN v2.0 (03.10.2026) и ARGUS20_COLLECTOR_OPENAPI 2.1.0. Единый перевыпуск: этот документ и `ARGUS20_COLLECTOR_OPENAPI.json` 3.0.0 (wire schema 1.1) выпускаются вместе и не расходятся.
**Исполнитель-2 (сборщик):** одна сессия Claude Code (Sonnet) на Windows MAIN-PC (RTX 4090, 24 ГБ), репозиторий `gridex-argus-collector`, каталог `C:\dev\gridex-argus-collector`.
**Исполнитель (ARGUS):** основная сессия в `/opt/argus20`, серверный модуль `collector` — блок 6, по ТЗ `ARGUS20_TZ_BLOCK6.md` (пишется после «ок» блока 5).
**Основание:** решение владельца 03.10.2026 (чат 03): отдельный исполнитель на Windows с RTX 4090 — новое решение; NON_GOALS и ARCHITECTURE актуализированы (правка 03). Порядок «ок» по этапам сохраняется.

Изменения 3.0 относительно 2.0:
- две работы разделены: дорожка A — сборщик (самостоятельный, с тестовым контракт-сервером), дорожка B — интеграция в блок 6 ARGUS (§2);
- учтены статусы K3, `model_call`, i18n, хозяева таблиц, формат ошибок, маршруты API (§9–§10);
- условия запуска, лимит страниц и правило источников телефонов — конкретные формулировки, вынесенные на «ок» (§3.3);
- добавлены: автопродолжение с общим бюджетом кампании (§8.6), история изменений и актуальность контактов (§8.8), маршруты и их повторная проверка (§8.7), сверка всех контактных полей (§8.9), раздельные статусы завершения обхода и подтверждённости охвата (§8.10), рабочий минимум M1 и развитие M2 (§4);
- версия MD и OpenAPI согласованы: один документ — одна версия; OpenAPI 3.0.0 сопровождает ТЗ 3.0.

---

## 1. Контекст

ARGUS 2.0 собирает для продавца компании-экспоненты и людей с каналами связи. Контакты (блок 6) берутся с того, что компания сама опубликовала: сайт, henkilöstö, пресс-релизы, PDF (VISION п.5, RULES K1). Серверный fetcher (httpx + Playwright-fallback в `argus20-worker`) читает страницы без действий.

Selain — второй исполнитель: локальный сборщик на Windows-компьютере владельца. Он получает от ARGUS пакет компаний (по умолчанию 8), проходит сайты кодом, затем локальным Chrome закрывает недоступное и неполное (переходы, клики, поиск, фильтры, раскрытие карточек, прокрутка, пагинация), сохраняет все обнаруженные контактные сведения с доказательствами и непрерывно отправляет их в ARGUS по API. Это реализация лестницы И7 (RULES K1) с действиями в браузере; серверный fetcher остаётся резервом, когда сборщик не подключён.

Что не меняется ни одним положением этого ТЗ: модель ничего не ищет и не генерирует списков (RULES R2/R3); факт = снимок + span + URL (E1/E2); контакт без источника не принимается; `inferred` никогда не показывается как проверенный (K3); соцсети своим кодом — никогда (K8); широкий кроул — никогда (R7).

Старой системы для обоих исполнителей не существует (CLAUDE.md п.6). Факты о внешних сервисах — только из `docs/ARGUS20_ASSETS.md`.

## 2. Подход и шаги с версиями

### 2.1. Две дорожки

| Дорожка | Кто | Где | Когда | Проверка владельца |
|---|---|---|---|---|
| A — сборщик | Исполнитель-2 | `gridex-argus-collector`, Windows | Начинается сразу, независимо от блоков 0–5 | Панель сборщика + тестовый контракт-сервер + тестовый сайт |
| B — интеграция | Исполнитель (ARGUS) | `/opt/argus20`, модуль `collector` | Блок 6, после «ок» блока 5 | Soittolista, Lokit, строка Selain |

Дорожка A до блока 6 работает против **тестового контракт-сервера** — эталонной реализации `ARGUS20_COLLECTOR_OPENAPI.json` внутри репо сборщика (FastAPI, SQLite, in-process). Он нужен только для испытаний сборщика, на прод не деплоится и в `/opt/argus20` не копируется. Боевой модуль `collector` пишет исполнитель ARGUS в блоке 6 по тому же OpenAPI и проходит тот же набор контрактных тестов (§12.4), которые живут в репо сборщика и подключаются в CI ARGUS как внешний пакет. Принято решение — поправь, если не так.

### 2.2. Цикл

Правила цикла WAYS §2 и TZ_BLOCK0 §2.1 действуют для обеих дорожек. Для дорожки A с поправками на отсутствие прода:
- ветка `stage-<S>/step-<M>-<slug>` от `main`; мерж только `--ff-only`; ветка удаляется после мержа;
- «деплой» = установка сборщика на MAIN-PC скриптом `scripts/install.ps1` из `main` с чистым деревом; версия и дата видны в панели сборщика;
- **«ок» владельца — по этапу S0–S6**, а не по каждому шагу внутри этапа (решение владельца 03.10.2026). Шаги внутри этапа коммитятся и устанавливаются по циклу, сдаются одной тест-картой этапа; следующий этап не начинается без «ок»;
- версия сборщика: файл `VERSION`, формат `0.<этап>.<шаг>.<правка>`, тег `cv0.<этап>.<шаг>` при `.0`; тег `stage-<S>-start` перед этапом;
- правка по замечаниям — тот же цикл, последняя цифра +1, коммит `stage-S step-M fix-K: …`.

### 2.3. Этапы и версии дорожки A

| Этап | Версия | Что видно (панель сборщика / тестовый сервер / тестовый сайт) |
|---|---|---|
| S0 | 0.0.1.0 | Диагностика: Windows, Chrome, драйвер NVIDIA, RAM/диск/GPU; тестовый сайт поднимается локально; smoke-test Playwright открывает тестовый сайт в постоянном профиле. Панель: версия, дата, «API: ei yhteyttä» |
| S1 | 0.1.1.0 – 0.1.3.0 | Контракт-сервер; панель подключается по токену; claim пакета; одно контрольное наблюдение с доказательством появляется в контракт-сервере; перезапуск и повтор не создают дубля; lease/heartbeat/reconcile |
| S2 | 0.2.1.0 – 0.2.3.0 | HTTP-проход по 8 компаниям тестового сайта; находки идут потоком; FieldAudit; маршруты записываются |
| S3 | 0.3.1.0 – 0.3.4.0 | Браузерный проход: кнопки, фильтры, поиск, пагинация, scroll; checkpoints; автопродолжение с бюджетом кампании; актуальность контактов при повторе |
| S4 | 0.4.1.0 – 0.4.3.0 | Адаптер модели (локальная, RTX 4090): выбор разделов, разбор карточек, план действия; документы PDF/DOCX/XLSX/CSV, OCR; нормализация и объединение; `model.called` в журнале |
| S5 | 0.5.1.0 – 0.5.3.0 | Панель полностью; восстановление после сна/обрыва/перезапуска; лимиты ресурсов; установочный пакет, обновление, откат |
| S6 | 0.6.1.0 | Живой пилот 8 компаний против боевого ARGUS (после блока 6) или против контракт-сервера, если блок 6 ещё не принят; отчёт с метриками §13.3 |

**Рабочий минимум M1 = S0–S3 + S5.** M2 = S4 и всё из §4.2. Пилот S6 проходится на M1; S4 — после «ок» S3, параллельно с S5 допустимо (разные модули).

### 2.4. Шаги дорожки B (блок 6, для понимания; ТЗ блока 6 — отдельно)

| Шаг | Версия | Что видно в ARGUS |
|---|---|---|
| 6.1 | 0.6.1.0 | Soittolista: таблица людей/каналов из серверной лестницы И7 (без Selain) |
| 6.2 | 0.6.2.0 | Строка состояния Selain в шапке Soittolista; выдача токена сборщика через `.env`; пакет создаётся кнопкой «Lähetä Selaimeen» по компаниям с подтверждённым участием |
| 6.3 | 0.6.3.0 | Контакты от Selain появляются в Soittolista во время обхода (polling ≤ 5 с); источник и исходное значение в карточке; статусы K3 |
| 6.4 | 0.6.4.0 | У компании: этап, число людей/каналов/источников, причина неполноты, Gap; «Jatka» (continue) и «Peruuta» (cancel); Lokit с разделением http/browser/extraction/delivery |

## 3. Неподвижные правила

Правила №1–№4 TZ_BLOCK0 §3 действуют для обоих репозиториев целиком. Дополнительно для сборщика:

### 3.1. Сборщик = второй рантайм с одной дверью
1. Единственная связь сборщика с ARGUS — контракт `ARGUS20_COLLECTOR_OPENAPI.json`. Прямого доступа к БД, снимкам, другим модулям нет.
2. Контракт меняется только перевыпуском этого ТЗ и OpenAPI одной правкой; клиентские типы сборщика генерируются из OpenAPI, руками не пишутся; серверный модуль валидирует запросы той же схемой.
3. У серверных таблиц `collector_*` один хозяин — модуль `collector` (§8.1). Контакты, персоны и снимки принадлежат `contacts` и `evidence`; `collector` пишет туда только через их `contract.py`.

### 3.2. Данные и модель
4. Текст модели — не доказательство. Модель выбирает разделы, разбирает карточки, планирует следующее действие; каждое поле записывается только с `evidence_id` + locator + quote, которые сервер проверяет по снимку.
5. Каждый вызов модели (локальной — тоже) пишется в `model_call` сервера через событие `model.called`: provider, model, tokens, `cost_eur` (для локальной — 0), purpose. Это требование RULES E3, не опция.
6. Статусы качества извлечения (`extraction_status`) и статусы канала (K3) — разные множества. Соответствие фиксировано в §9.4; сервер выводит статус канала сам, сборщик его не задаёт.
7. Ничего не удаляется: наблюдения только добавляются, конфликт — два наблюдения с флагом, увольнение не выводится из отсутствия на странице.

### 3.3. Формулировки, вынесенные на «ок» владельца
Эти три формулировки меняют RULES R8 и K7 и добавляют условия запуска. До «ок» действуют R8 и K7 правки 02; сборщик до S3 проектируется под эти формулировки, в код условий запуска они входят в S2.

**R8 (03.10.2026, новая редакция).** Обход сайта компании выполняется только для компании с участием `confirmed` или `strong_historical` в проекте, из которого создан пакет. Пакет без проекта (`project_id = null`) создаётся только системным вызовом с `override_reason`, и он виден в Lokit. Лимиты одной компании: 200 HTTP-страниц и 300 состояний (страница + значимые параметры/фильтры/cursor) на один прогон; 400 браузерных действий на прогон; кампания (все прогоны одной job) — 600 страниц / 900 состояний / 1 200 действий / 3 часа активного времени. Превышение — `partial` с сохранённым frontier, не ошибка. Причина: прежний предел 200 страниц не учитывал состояния браузера; обход без подтверждённого участия возвращает широкий кроул.

**K7 (03.10.2026, новая редакция).** Телефон и email привязываются к компании или её сотруднику только со страницы хоста из `approved_hosts` задания. Хост попадает в `approved_hosts` одним из оснований, каждое — с доказательством: `seed` (URL из паспорта/карточки компании), `redirect_from_seed` (редирект с seed, цепочка в снимке), `linked_from_contact_section` (ссылка из контактного раздела seed-хоста, снимок страницы со ссылкой), `business_id_match` (тот же Y-tunnus на странице нового хоста), `owner_known_url`. Внешний SaaS-каталог/CDN допускается только как `linked_from_contact_section` и только по подтверждённому tenant/path. Наблюдение канала с хоста вне `approved_hosts` сервер отклоняет кодом `host_not_approved`; сборщик сохраняет его локально как `domain_ownership_unresolved` и продолжает другие ветви. Причина: Sandvik получил номер Katsa; суффиксное сравнение строк недопустимо.

**Условия запуска Selain (новое, K9, 03.10.2026).** Пакет создаётся из Soittolista владельцем (кнопка) или прогоном блока 6 автоматически после шага «ER + тиры», в порядке приоритета 3× → 2× → 1×, по 8 компаний. Компания попадает в пакет один раз на проект; повторный запуск — только командой `continue` или новым пакетом с `rerun_reason`. Пока сборщик не подключён (`Selain: ei yhteyttä`), прогон использует серверную лестницу И7 и помечает компании `selain_pending`; при подключении сборщик забирает очередь. Причина: два источника контактов на одну компанию без порядка дадут дубли и спор счётчиков (E6).

## 4. Границы

### 4.1. Входит — M1 (обязательный рабочий минимум)
- Windows-сборщик: claim пакета ≤ 8, HTTP-проход, браузерный проход детерминированными правилами (без модели), извлечение `mailto`/`tel`/vCard/JSON-LD/microdata/RDFa/встроенного JSON/XHR-ответов каталога, карточки и таблицы по структуре.
- Доказательства: снимок, sha256, canonical text, locator, quote; скриншот релевантного участка при визуальном извлечении.
- Надёжная доставка: SQLite + outbox, at-least-once, идемпотентность, seq, reconcile, lease/heartbeat.
- Автопродолжение с бюджетом кампании; checkpoints; маршруты и их повторная проверка; история и актуальность; FieldAudit; раздельные статусы охвата.
- Панель сборщика (tray/окно), установка, обновление, откат, диагностика.
- Контракт-сервер и контрактные тесты; тестовый сайт-фикстура.
- Серверный модуль `collector` и экраны блока 6 (дорожка B).

### 4.2. Входит — M2 (после «ок» M1, отдельными этапами)
- Адаптер модели: локальная модель на RTX 4090 (структурированный ответ, инструменты/схема действий, vision для моделей с ней, таймаут/отмена/учёт). Выбор модели — по испытаниям на одинаковых источниках и бюджете.
- Документы: PDF/DOCX/XLSX/CSV, OCR изображений с контактами; без исполнения макросов и встроенных программ.
- Адаптер действий по скриншоту/координатам, когда клик через locator не работает (только видимый браузер).
- Облачный fallback модели — отдельная настройка, по умолчанию выключена, лимит в EUR; включение — только «ок» владельца (платный сервис).
- Несколько сборщиков и автоматическая передача задания другому (M1: один worker, задание закреплено).

### 4.3. Не входит и не появляется на экране
- Поиск сайта компании по названию (вход без `seed_urls` → `invalid_input`).
- Отправка писем, заявок, заказов, создание аккаунтов, изменение данных на сайтах.
- Автоматическое решение капч, подбор учётных данных, смена идентичностей/маршрутов при блокировке.
- Обход соцсетей и LinkedIn (K8); внешние профили сохраняются только как ссылки.
- Hermes и любые агентные фреймворки (NON_GOALS); Celery/Redis/очереди; Windows Service (Session 0).
- Запись видео/всех скриншотов сессии; отправка cookies, заголовков авторизации, истории, других вкладок.
- Монитор пополнения, периодические ре-снапшоты по расписанию (NON_GOALS; повторная проверка маршрутов идёт только внутри задания).
- Отдельный веб-продукт панели сборщика; «охват 100 %» без известного total.

## 5. Спецификация интерфейса

### 5.1. Панель сборщика (Windows)
Одно окно + значок в tray. Язык — финский, строки в `collector/messages/fi.json`, тот же гейт `check_i18n` (принято решение — поправь, если нужен английский). Светлая тема. Внизу слева — версия и дата сборки: `cv0.3.2.1 (3.10.2026 klo 14.32)` + короткий хэш, из файла `VERSION`, вшитого при сборке.

| Блок | Элементы | Состояния |
|---|---|---|
| Yhteys | адрес ARGUS, «Testaa yhteys», worker_id, последний heartbeat | `Ei yhteyttä` / `Yhdistetty` / `Tunnus hylätty` (red) |
| Keruu | «Käynnistä» / «Keskeytä» / «Pysäytä»; две независимые настройки с подписями: `Käynnistä Windowsin kirjautuessa`, `Aloita keruu automaattisesti` | collecting on/off; обе настройки по умолчанию выключены |
| Jono | таблица компаний пакета: nimi · vaihe (`Odottaa` / `Haetaan sivuja` / `Selain käsittelee` / `Asiakirjat` / `Viimeistellään`) · henkilöt · kanavat · lähteet · tila | 4 состояния списка: `Ladataan…` / `Jonon lataus epäonnistui` / `Ei tehtäviä` / таблица |
| Lähetys | `Odottaa lähetystä: N` · `Lähetysvirhe: N` · p95 с последней минуты | `synced` / `syncing` / `offline` / `delivery_error` (red) |
| Resurssit | Chrome: `Käytettävissä`/`Ei käytettävissä`; Malli: `Paikallinen (GPU)` / `Paikallinen (CPU)` / `Ei ladattu` / `Pilvi` ; levy, muisti, GPU-muisti | предупреждение при > 85 % диска |
| Huomio | текущая причина `Tarvitsee huomiota` + «Avaa työselain» + «Jatka käsin tehdyn toimen jälkeen» | показывается только когда есть job в `needs_attention` |

Всё, что показано, — из локальной SQLite и последнего ответа сервера; никаких вычисленных «прогрессов». Кнопка есть — работает.

### 5.2. ARGUS (блок 6, экраны по SCREENS правка 03)
**Шапка Soittolista** — строка состояния сборщика, один источник (`GET /api/collector/workers/{id}/status`):

| Состояние | Текст |
|---|---|
| не подключён | `Selain: ei yhteyttä` |
| подключён, сбор выключен | `Selain: yhdistetty · keskeytetty` |
| подключён, собирает | `Selain: kerää · N yritystä jonossa` |
| ошибка доставки на стороне сборщика | `Selain: tulosten lähetys epäonnistui` (red) |

**Строка компании в Soittolista** добавляет: vaihe (`Odottaa käsittelyä` / `Haetaan sivuja` / `Selain käsittelee` / `Tarvitsee huomiota` / `Valmis` / `Osittain valmis` / `Keskeytetty` / `Epäonnistui`), henkilöt, kanavat, lähteet, причина неполноты (из `completion_reason`), «Jatka», «Peruuta». Кнопка «Lähetä Selaimeen» — на выбранных компаниях с участием `confirmed`/`strong_historical`.

**Карточка контакта**: канал · статус K3 · исходное значение · источник (ссылка + иконка снимка) · дата наблюдения · `Nähty viimeksi` · история (список наблюдений с датами, `muuttunut`/`vahvistettu`).

**Lokit**: записи сборщика с префиксом канала `http` / `browser` / `extraction` / `delivery` / `model`; без значений контактов и секретов.

Наличие HTML не даёт зелёного статуса. `inferred` не показывается как проверенный и не считается в G6.

## 6. i18n-ключи

### 6.1. Сборщик — `collector/messages/fi.json`
```
app.name = ARGUS Selain
connection.title = Yhteys
connection.test = Testaa yhteys
connection.state.disconnected = Ei yhteyttä
connection.state.connected = Yhdistetty
connection.state.rejected = Tunnus hylätty
collecting.title = Keruu
collecting.start = Käynnistä
collecting.pause = Keskeytä
collecting.stop = Pysäytä
collecting.autostartWindows = Käynnistä Windowsin kirjautuessa
collecting.autoCollect = Aloita keruu automaattisesti
queue.title = Jono
queue.loading = Ladataan…
queue.loadError = Jonon lataus epäonnistui
queue.empty = Ei tehtäviä
queue.col.company = Yritys
queue.col.stage = Vaihe
queue.col.persons = Henkilöt
queue.col.channels = Kanavat
queue.col.sources = Lähteet
queue.col.state = Tila
stage.queued = Odottaa
stage.http = Haetaan sivuja
stage.browser = Selain käsittelee
stage.documents = Asiakirjat
stage.finalizing = Viimeistellään
job.state.completed = Valmis
job.state.partial = Osittain valmis
job.state.failed = Epäonnistui
job.state.cancelled = Keskeytetty
job.state.paused = Tauolla
job.state.needs_attention = Tarvitsee huomiota
delivery.title = Lähetys
delivery.pending = Odottaa lähetystä: {n}
delivery.error = Lähetysvirhe: {n}
delivery.state.synced = Lähetetty
delivery.state.syncing = Lähetetään
delivery.state.offline = Ei verkkoa
delivery.state.delivery_error = Lähetys epäonnistui
resources.title = Resurssit
resources.chrome.ok = Chrome: käytettävissä
resources.chrome.missing = Chrome: ei käytettävissä
resources.model.gpu = Malli: paikallinen (GPU)
resources.model.cpu = Malli: paikallinen (CPU)
resources.model.none = Malli: ei ladattu
resources.model.cloud = Malli: pilvi
resources.diskWarning = Levytila alle 15 %
attention.title = Huomio
attention.openBrowser = Avaa työselain
attention.resume = Jatka käsin tehdyn toimen jälkeen
version.builtAt = {date}
```

### 6.2. ARGUS — добавляются в `web/messages/fi.json` в блоке 6
```
selain.state.disconnected = Selain: ei yhteyttä
selain.state.paused = Selain: yhdistetty · keskeytetty
selain.state.collecting = Selain: kerää · {n} yritystä jonossa
selain.state.deliveryError = Selain: tulosten lähetys epäonnistui
selain.send = Lähetä Selaimeen
selain.continue = Jatka
selain.cancel = Peruuta
selain.stage.queued = Odottaa käsittelyä
selain.stage.http = Haetaan sivuja
selain.stage.browser = Selain käsittelee
selain.stage.attention = Tarvitsee huomiota
selain.result.completed = Valmis
selain.result.partial = Osittain valmis
selain.result.cancelled = Keskeytetty
selain.result.failed = Epäonnistui
contact.lastSeen = Nähty viimeksi: {date}
contact.history.changed = muuttunut
contact.history.reconfirmed = vahvistettu
contact.history.notSeen = ei nähty tarkistetussa laajuudessa
```
Коды `completion_reason` и `gap.reason` на экран не попадают напрямую: каждый получает ключ `selain.reason.<code>` в ТЗ блока 6.

## 7. Стек

**Сборщик (Windows):** Python 3.12 (закреплён lock-файлом), asyncio, httpx, lxml, Playwright Python + установленный Chrome (постоянный рабочий профиль; CDP только loopback), Pydantic v2 + сгенерированные модели из OpenAPI, SQLite (WAL), pywebview или tkinter для панели (принято решение — tkinter, без веб-сервера; поправь, если не так), Task Scheduler для автозапуска в интерактивной сессии. Документы (M2): pypdf/pdfplumber, python-docx, openpyxl, Tesseract OCR — без исполнения макросов. Модель (M2): сменный адаптер; локальный инференс через HTTP-endpoint на loopback (llama.cpp/vLLM — выбирается на S4 по измерениям); DPAPI для токена.

**Chrome:** отдельный `user-data-dir` в `%LOCALAPPDATA%\Gridex\ArgusCollector\browser-profile`; видимое окно; владелец может работать в нём руками; драйвер управляет только своими вкладками, не читает остальные, пароли не копирует. Личный Chrome не трогается (ограничения remote debugging стандартного профиля с Chrome 136).

**Сервер (блок 6):** стек ARCHITECTURE §2 без добавлений; модуль `collector` в `argus20-api`; хранение доказательств — через `evidence.contract` в `/mnt/argus-data/argus20/snapshots/`, `fetcher=collector_http|collector_browser`.

**Нет:** Hermes, LangGraph, Redis, Celery, Windows Service, расширение Chrome MV3, глобальное управление мышью как базовая зависимость.

## 8. Поведение сборщика

### 8.1. Приём и планирование
1. Проверка версии контракта (`schema_version` 1.1) и локального хранилища.
2. `POST /jobs/claim` с `max_jobs` = свободные слоты (≤ 8), атомарно; задания и lease — в SQLite одной транзакцией.
3. Проверка `seed_urls`, `approved_hosts`, отсутствия дублирующего активного задания той же компании.
4. Frontier по всем компаниям; отдельный цикл доставки outbox, не зависящий от HTTP и браузера.
5. Новый пакет не берётся при переполненной очереди; `free_job_slots` уходит в heartbeat.

### 8.2. Первый проход кодом (HTTP)
Для каждого сайта: входные страницы с редиректами; навигация, footer, контактные блоки, ссылки; sitemap как источник URL, не как доказательство полноты; приоритет contacts/team/staff/people/management/sales/support/offices/locations/yhteystiedot/henkilöstö/myynti/johto и языковых вариантов; все контактные записи на обработанных страницах, включая общие каналы; `mailto`, `tel`, vCard, JSON-LD, microdata, RDFa, контактные `data-*`, JSON состояния страницы; ссылки на контактные документы; браузерные задачи по признакам динамических карточек, скрытых полей, поиска, фильтров, неполной выдачи.

Запрещено: угадывать административные адреса, перебирать произвольные параметры/ID, собирать все сетевые ответы без разбора (аналитика, реклама, платежи — не источники). XHR/JSON каталога сохраняется и извлекается целиком, пагинация/cursor — по обнаруженным параметрам в том же контексте. Встроенный JSON с записями сверх первого экрана — `source_kind=embedded_data`. Архивные документы — с признаком исторического источника (§8.8).

### 8.3. Условия браузерного прохода
Запускается при любом из: ошибка/заглушка HTTP; JS-зависимое содержимое; нераскрытые карточки, фильтры, пагинация, lazy loading; каталог найден, выдача неполная; поля за кнопкой/наведением; показана часть отделов/регионов; необработанные релевантные ссылки или документы; подозрительно пустой результат без исследования структуры.

Общий телефон/email или несколько сотрудников — не основание пропустить браузер. Пропуск допустим только при исчерпанном релевантном frontier без признаков скрытых источников, причина `browser_not_needed`.

### 8.4. Второй проход через браузер
Цикл: наблюдение → выбор действия → выполнение → проверка изменения → извлечение → сохранение → отправка. Действия (внутренняя схема `BrowserAction`): navigate, click/double-click, hover, fill, select, scroll, press, wait, extract, back, finish_branch, request_human. Раскрытие accordion/карточек, «показать телефон/email/ещё», поиск и фильтры (POST допустим для поиска/фильтров), пагинация, прокрутка контейнеров, frames и shadow DOM где поддерживает драйвер, скачивание документа без запуска программы, скриншот участка.

`mailto:`/`tel:` не нажимаются — значение берётся из ссылки. Перед исполнением действия драйвер проверяет существование элемента, соответствие состоянию и тип; после навигации старые ref/locator не используются. В M1 выбор действия — детерминированные правила (словарь кнопок/ролей, структурные признаки); в M2 — модель с теми же правилами как guard-rails. Модель получает задачу, обработанные разделы, краткое состояние и варианты действий; не получает shell, секреты, инструменты отправки. Инструкции внутри страницы — содержимое, не команды.

### 8.5. Пагинация, циклы, готовность, препятствия
Для каталогов сохраняются: заявленное число записей, просмотренные страницы/cursor/фильтры, уникальные найденные записи, признак следующей страницы, ожидаемые и доступные подразделения, недоступные карточки. Начинать с «все», затем ветви, дающие новые записи; декартово произведение фильтров не перебирается; обязательный поиск — по отделам/регионам с сайта, охват помечается неподтверждённым.

Ключ состояния: URL + значимые параметры/fragment + фильтры + cursor + хеш релевантного содержимого. Три повтора состояния без новых записей/ссылок → `no_progress`, смена действия или завершение ветви.

Готовность — по целевому контейнеру, стабилизации карточек, завершению релевантного запроса, исчезновению loader; не по `load`, не по фиксированной паузе, не по бесконечному `networkidle`. Таймауты: навигация 45 с, целевое состояние 20 с, один повтор с backoff.

Классы препятствий: `access_denied`, `captcha`, `login_required`, `consent_unresolved`, `geo_or_legal_restriction`, `timeout`, `network_error`, `unsupported_widget`, `model_unavailable`. Классификатор — по нескольким признакам; одно слово captcha/403 или < 500 символов недостаточны. При явном ограничении — причина, без повторов и смены идентичностей; капча/вход — `needs_attention`, владелец решает в рабочем браузере и нажимает «Jatka käsin tehdyn toimen jälkeen». Cookie-баннеры — автоматически, предпочтение необходимым, выбор фиксируется.

### 8.6. Автопродолжение с общим бюджетом кампании
- **Прогон (run)** ограничен `policy.max_active_seconds` / `max_pages` / `max_browser_actions`. **Кампания (job)** — суммой всех прогонов: `campaign_max_active_seconds`, `campaign_max_pages`, `campaign_max_browser_actions`, `campaign_cloud_budget_eur`, `max_runs`. Значения по умолчанию — §3.3 R8.
- Прогон завершился `partial` с `resumable` ветвями и остатком бюджета кампании → сервер при `policy.auto_continue=true` сам планирует следующий run (`continuation=scheduled`), сборщик забирает его следующим claim с `checkpoint` (frontier, route_refs, израсходованное). Ожидания владельца нет.
- Остаток бюджета исчерпан → `continuation=budget_exhausted`, job = `partial`; «Jatka» в ARGUS с `policy_patch` поднимает потолок кампании — это команда владельца, не автоматика.
- `needs_attention` → `continuation=waiting_attention`; сборщик не подключён → `waiting_worker`.
- Сон Windows, пауза и ожидание пользователя не расходуют активное время.

### 8.7. Маршруты: сохранение и повторная проверка
- Успешная последовательность, давшая новые записи (стартовый URL → действия → контейнер), сохраняется как `Route`: host, purpose (`contact_index` / `person_card` / `catalog_page` / `document`), шаги с текстовыми описателями целей (role/text/selector), сигнатура результата (хеш ключевого контейнера, число записей), счётчики успехов/неудач, `last_verified_at`, статус `active` / `failing` / `retired`.
- Событие `route.recorded` → сервер хранит в `collector_route`; при следующем claim по тому же хосту сервер отдаёт известные маршруты в `ClaimedJob.routes`.
- Повторная проверка: при новом прогоне по хосту сборщик сначала воспроизводит маршруты (дёшево), сравнивает сигнатуру; совпало — `route.verified` с `verified`, записи переизвлекаются; не совпало — `changed`, маршрут `failing`, ветвь идёт в обычное исследование; три неудачи подряд — `retired`. Маршрут — ускорение, не доказательство полноты: coverage по нему не повышается.

### 8.8. История изменений и актуальность контактов
- Наблюдение несёт `change_kind`: `new` / `reconfirmed` / `changed` и `supersedes_observation_id`. Сервер ведёт у каждого поля контакта историю наблюдений с датами; `last_seen_at` = дата последнего `new`/`reconfirmed`.
- В конце прогона по компании для каждого ранее известного контакта (из `ClaimedJob.known_contacts`) сборщик отправляет `contact.freshness`: `reconfirmed` / `changed` / `not_seen_in_checked_scope` / `not_checked`, с описанием проверенного охвата и evidence. `not_seen` — не увольнение: контакт остаётся, получает отметку; `stale` по K5 (18 мес) считает сервер по датам.
- Исторические документы (дата документа старше 18 мес или архивный раздел) — `extraction_status=historical`; сервер даёт каналу статус `stale` сразу.
- Конфликт значений — оба наблюдения с `conflict`, без выбора «правильного» сборщиком.

### 8.9. Сверка всех обнаруженных контактных полей (FieldAudit)
Каждое `contact.observed`/`contact.enriched` содержит `field_audit` по источнику: для каждого обнаруженного в источнике контактного поля — `mapped` (есть наблюдение), `extra` (ушло в `extra_fields` с названием и исходным значением), `unresolved` (не удалось привязать — отдельное наблюдение `ambiguous`), `empty_technical` (пустой технический атрибут). Поле `dropped_contact_fields` = 0 обязательно: сборщик не имеет права «потерять» контактное поле молча. Сервер отклоняет событие без аудита кодом `field_audit_missing`.

### 8.10. Раздельные статусы завершения обхода и подтверждённости охвата
Два независимых измерения, оба в `job.finished` и в `GET /jobs/{id}`:
- **Завершение обхода** — `run_result_status` ∈ completed/partial/failed/cancelled и `completion_reason` ∈ `frontier_exhausted` / `no_contacts_in_checked_scope` / `budget_reached` / `unresolved_access` / `unsupported_source` / `manual_cancel` / `technical_failure`.
- **Подтверждённость охвата** — `coverage.frontier_status` ∈ `exhausted` / `partial` / `not_started` и `coverage.confirmation` ∈ `verified_against_catalog_total` (сайт заявил total, найдено ≥ total) / `verified_against_manual_reference` (пилот) / `unverified`; плюс `basis`, `expected_count`, `found_count`, `gap_count`, `evidence_ids`.
`completed` + `unverified` — нормальная комбинация и показывается именно так: «обход закончен, полнота не подтверждена». «Охват 100 %» публикуется только при `verified_*`.

### 8.11. Что сохраняется
Сущности: `person`, `department`, `office`, `organization_channel`, `unassigned_channel`; `relationship` ∈ employee/company/partner/distributor/agent/unknown — партнёр не превращается в сотрудника. Поля — имя (full/given/family, исходное написание), работа (должность на языке источника, отдел, функции, зона), связь (email[], phone[], mobile[], fax[], другие), организация, география, дополнительное (языки, часы, ссылки профилей, фото URL, описание), происхождение, качество, `extra_fields[]`. Минимум схемы — имя, фамилия, телефон, email, должность; наличие всех не требуется; только имя + должность — сохраняется; неоднозначное деление имени — `full_name`, части `null`.

Нормализация: исходные значения обязательны; телефон в E.164 только при уверенном контексте страны, иначе `normalized=null`; добавочные отдельно; email — синтаксис, домен в нижнем регистре, оригинал сохранён; `email_pattern` — отдельное поле, никогда не адрес. Привязка — по карточке, строке таблицы, объекту JSON или явной подписи (`binding`); близость текста без структуры → `ambiguous`; общий номер footer не приписывается всем людям.

Дубли: стабильные ID источника, персональный email в контексте записи, имя + подразделение, подтверждённые ссылки; общий телефон/имя/общий email — недостаточно; `contact.merge_proposed` с доказательствами, сервер решает; `possible_duplicate` без принудительного слияния.

### 8.12. Доказательства
Источники: HTTP body, DOM после взаимодействия, публичный JSON, документ, скриншот/OCR. Состав: `evidence_id`, `company_id`, `job_id`, `run_id`, начальный/конечный URL (цепочка), `source_kind`, MIME, `fetched_at` UTC, sha256 байтов, canonical text + его sha256, версия извлекателя, `document_date`. Locator: `text_span` (code points, `[start,end)`, хеш текста), `json_pointer`, `document` (page/table/row/cell), `bbox`, `dom` (дополнительно, не вместо снимка). Сервер проверяет quote по снимку; несовпадение — `evidence_hash_mismatch`.

Не отправляются: cookies, Authorization, хранилища браузера, пароли, история, чужие вкладки. Технические секреты в HTML/URL вырезаются, `redacted=true`, доказательство привязано к очищенной версии. HTML-снимки в ARGUS — инертно (без скриптов и удалённых ресурсов). Лимиты: 25 МиБ HTML/DOM/JSON, 50 МиБ документ/checkpoint, 10 МиБ изображение, и к распакованному; превышение — `source_too_large`, допустим фрагмент с `capture_truncated=true`.

### 8.13. Планировщик и ресурсы (пилотные значения)
Компаний в пакете 8; активных HTTP-компаний до 8; одновременных HTTP-запросов 8, на host — 1, интервал ≥ 1 с; браузерных страниц одновременно 1; запросов к модели 1; lease 180 с; heartbeat 30 с; окно отправки ≤ 5 с (микропакет ≤ 50 событий или 2 с). 429 — `Retry-After`; временные ошибки — backoff с jitter; блокировки не разгоняют поток. Диск/память/GPU контролируются; нехватка — снижение параллельности/контекста или остановка этапа с сохранением результата; диск > 85 % — стоп новых загрузок, outbox продолжает.

### 8.14. Состояния и восстановление
Job: `queued → leased → running → completed | partial | failed | cancelled`, плюс `paused`, `needs_attention`; `stage` отдельно (`http` / `browser` / `documents` / `finalizing`). Транспорт отдельно: `online` / `offline` / `syncing` / `synced` / `delivery_error`. Страницы/ветви: `discovered`, `queued_http`, `fetched_http`, `queued_browser`, `in_browser`, `extracted`, `blocked`, `unsupported`, `skipped`, `failed`.

Lease: атомарная выдача, непрозрачный `execution_token`, срок, монотонное `lease_generation`; heartbeat продлевает только текущую аренду. Истёк lease → новые действия прекращаются, полученное и outbox сохраняются → `reconcile` → `resume` (новая аренда тому же worker; M1: задание закреплено за worker) или `drain_only` (только слив буфера, без права обхода). Поздние события старого run — наблюдения без права менять состояние; поздний `finished` не завершает новый run. После перезапуска восстанавливаются задания, frontier, бюджет, entity_map, outbox; вкладки/scroll — нет, ветвь открывается заново, наблюдения дедуплицируются.

## 9. API-контракт `/api/collector`

### 9.1. Общие правила
- Префикс `/api/collector` (без `/v1`: версия — `schema_version` в теле; как у остальных модулей ARGUS). Принято решение — поправь, если не так.
- HTTPS, JSON UTF-8, ISO 8601 UTC. Ошибка: `{"code","detail","retryable","request_id"}` — надмножество формата TZ_BLOCK0 §9 (`code`, `detail` обязательны там же; `retryable`, `request_id` — расширение, фиксируется в ТЗ блока 6).
- Два класса авторизации: `WorkerBearer` (токен сборщика, привязан к `worker_id`, правам и сроку; отзыв и ротация; выдаётся командой `argus20 collector-token`, значение вносит владелец в панель сборщика; в логах нет) и `SystemBearer` (внутренний вызов ARGUS/владелец для создания пакетов и control). Worker не получает административных методов, зная URL.
- `schema_version = "1.1"` во всех конвертах.

### 9.2. Методы
| Метод и путь | Кто | Назначение | Ответ |
|---|---|---|---|
| `POST /batches` | System | `client_request_id`, `companies[]` ≤ 8 с `participation_status`, `approved_hosts[]` с основаниями, scope, policy | 201 `batch_id`, `jobs[]`; повтор ключа → 200 тот же; другой payload → 409 `idempotency_conflict`; участие не `confirmed`/`strong_historical` без `override_reason` → 422 `participation_not_confirmed` |
| `POST /workers/heartbeat` | Worker | версия, capabilities, collecting, active leases, outbox, слоты, браузер/модель, acks команд | 200 server_time, продлённые аренды (только валидные), команды с `command_id` |
| `POST /jobs/claim` | Worker | `{worker_id, max_jobs ≤ 8, capabilities}` | 200 `jobs[]` с lease, `checkpoint`, `routes[]`, `known_contacts[]`; пустой массив допустим |
| `POST /jobs/{job_id}/evidence` | Worker | multipart: metadata + файл; lease/recovery token; проверка владения, хеша, размера | 201 / 200 duplicate; `evidence_id`, `snapshot_id` |
| `POST /jobs/{job_id}/events` | Worker | ≤ 50 событий одного run по возрастанию seq | 200 результат по каждому `event_id` (`accepted`/`duplicate`/`rejected`+code, `canonical_contact_id`, `channel_status`, `server_revision`), `last_contiguous_seq`, `job_state`, `next_run_scheduled` |
| `POST /jobs/{job_id}/reconcile` | Worker | run_id, last_acknowledged_seq, pending IDs | 200 `mode` resume/drain_only, lease, принятые/недостающие IDs |
| `POST /jobs/{job_id}/control` | System | pause/resume/cancel/continue, `expected_state_revision`, `policy_patch` | 200 новая версия состояния |
| `GET /jobs/{job_id}` | System | состояние, stage, counts, coverage, budget, continuation, gaps, транспорт | 200 |
| `GET /batches/{batch_id}` | System | сводка по компаниям | 200 |
| `GET /workers/{worker_id}/status` | System | состояние сборщика для строки Selain | 200 |

### 9.3. События
`job.started` · `source.discovered` · `source.processed` · `source.blocked` · `contact.observed` · `contact.enriched` · `contact.merge_proposed` · `contact.freshness` · `route.recorded` · `route.verified` · `model.called` · `job.progress` · `job.needs_attention` · `job.finished`.

Конверт: `event_id` (глобально уникален), `job_id`, `run_id`, `seq` (монотонен в `(job_id, run_id)`, не сбрасывается после перезапуска), `occurred_at`, `type`, `schema_version`, `payload`. Доставка at-least-once; повтор принятого — `duplicate`; тот же ID с другим payload после принятия — 409 `idempotency_conflict`; пропуск seq — `sequence_gap` для всего хвоста; событие без загруженного доказательства — `evidence_missing`, повтор после загрузки разрешён. `job.finished` принимается, когда приняты все предыдущие seq и их доказательства; повтор идемпотентен.

Коды ошибок: `unauthorized`, `worker_revoked`, `schema_unsupported`, `lease_expired`, `lease_mismatch`, `job_cancelled`, `sequence_gap`, `evidence_missing`, `evidence_hash_mismatch`, `idempotency_conflict`, `host_not_approved`, `field_audit_missing`, `participation_not_confirmed`, `budget_exceeded`, `continuation_limit_reached`, `payload_too_large`, `rate_limited`, `storage_unavailable`, `invalid_input`.

### 9.4. Соответствие статусов: качество извлечения → статус канала K3
Сборщик передаёт `extraction_status` и `binding`; сервер (модуль `contacts`) выводит статус `contact_point.status` по таблице. Таблица — единственный источник; сборщик статус канала не задаёт.

| `entity_type` | `binding` | `extraction_status` | → статус канала K3 |
|---|---|---|---|
| person | card / table_row / json_object / caption | confirmed | `published_direct` |
| person | proximity_only / none | любое | `inferred` |
| person | любое | ambiguous | `inferred` |
| person | любое | ocr_unverified | `inferred` до ручного подтверждения |
| organization_channel, office, department | любое, кроме none | confirmed | `published_general` |
| unassigned_channel | — | любое | `inferred` |
| любое | любое | historical | `stale` |
| поле `email_pattern` | — | любое | не канал; хранится у компании, статус не назначается |
| контакт из каталога организатора (блок 6, не Selain) | — | — | `catalog_published` |
| контакт от провайдера K4-ext | — | — | `provider_verified` |

Дополнительно: канал с хоста вне `approved_hosts` — отклонён (`host_not_approved`), статус не назначается. Должность старше 18 мес (K5) — `stale` по дате наблюдения, считает сервер. `inferred` и `stale` не входят в G6.

### 9.5. Соответствие `source_kind` → `snapshot.fetcher`
`http_html`, `json_response`, `embedded_data` → `collector_http`; `browser_dom`, `screenshot`, `ocr` → `collector_browser`; `document` → `collector_document`; `checkpoint` — не снимок, хранится в `collector_run`.

## 10. Данные

### 10.1. Сервер — хозяин модуль `collector` (блок 6, одна миграция Alembic)
| Таблица | Ключевые поля |
|---|---|
| collector_worker | id, label, token_hash, capabilities (jsonb), worker_version, last_seen_at, revoked_at |
| collector_batch | id, client_request_id UNIQUE(caller, key), created_by, override_reason, created_at |
| collector_job | id, batch_id, company_id, project_id NULL, participation_claim_id, scope, policy, state, state_revision, stage, continuation, lease_* , budget_consumed (jsonb), created_at |
| collector_run | id, job_id, generation, worker_id, last_contiguous_seq, result_status, completion_reason, coverage (jsonb), checkpoint_snapshot_id, started_at, finished_at |
| collector_source | id, run_id, url, state_key, parent_id, method, status, attempts, snapshot_id; UNIQUE(run_id, state_key) |
| collector_event | event_id UNIQUE, run_id, seq, type, payload_sha256, result, applied_at; UNIQUE(run_id, seq) |
| collector_entity_map | run_id, entity_id, canonical_person_id / canonical_contact_point_id |
| collector_gap | id, job_id, source_url, state_key, reason, detail, attempts, resumable |
| collector_route | id, host, purpose, start_url, steps (jsonb), signature, status, success_count, failure_count, last_verified_at |
| collector_freshness | id, run_id, contact_point_id, status, scope_description, checked_at |

Контакты: `person`, `contact_point` — хозяин `contacts` (ARCHITECTURE §4); `contact_point` получает `last_seen_at` и таблицу `contact_observation` (хозяин `contacts`: contact_point_id, raw_value, normalized_value, extraction_status, binding, claim_id, change_kind, supersedes_id, observed_at). Снимки — `evidence`. Расход модели — `model_call` (хозяин `cost`): `run_id` = `collector_run.id`, provider `local`/`openrouter`/…, `cost_eur` 0 для локальной. Ничего не удаляется; колонок «на будущее» нет.

### 10.2. Сборщик — SQLite `%LOCALAPPDATA%\Gridex\ArgusCollector\state\collector.db`
`jobs`, `runs`, `frontier`, `observations`, `entity_map`, `outbox`, `evidence_manifest`, `routes`, `checkpoints`, `commands`, `model_calls`. Байты доказательств — на диске по sha256 (`evidence/<sha256[:2]>/<sha256>`), запись во временный файл + атомарное переименование до фиксации manifest. Наблюдение и запись outbox — одна транзакция. Неотправленное не удаляется автоматически; подтверждённые источники — 30 дней; логи без PII — 14 дней; очистка не трогает активные задания и ссылки.

## 11. Структура репозитория сборщика и модули

```
gridex-argus-collector/
  VERSION                      # 0.<stage>.<step>.<fix>
  CLAUDE.md                    # copy of ARGUS CLAUDE.md rules adapted to this repo
  collector/
    src/argus_collector/
      api_client/              # generated from OpenAPI — never edited by hand
      scheduler/               # batches, leases, budgets, continuation
      storage/                 # SQLite, migrations
      delivery/                # outbox, retries, reconcile
      discovery/               # frontier, link/section ranking, state keys
      http_fetch/              # httpx pass
      browser/                 # Playwright driver, actions, readiness, obstacles, routes
      extraction/              # structured extractors, binding, field audit
      documents/               # M2: pdf/docx/xlsx/csv/ocr
      normalization/           # phones, emails, names; dedup rules (one place)
      evidence/                # hashing, canonical text, locators, redaction
      models/                  # M2: model adapter, local endpoint, usage log
      ui/                      # tray/window, props-only views, data hooks
    messages/fi.json
    tests/{unit,contract,fixtures,recovery}/
  contract_server/             # reference server for OpenAPI; test-only, never deployed
  test_site/                   # reproducible fixture site (§12.2)
  scripts/ install.ps1, start.ps1, diagnose.ps1, update.ps1, rollback.ps1,
           gen_api_client.ps1, check_i18n.mjs, check_no_cyrillic.ps1,
           check_docs.ps1, check_size.ps1, check_version.ps1, check_legacy.ps1
  docs/ ARGUS20_TZ_SELAIN.md, ARGUS20_COLLECTOR_OPENAPI.json, ARGUS20_COLLECTOR_MODULES.md,
        ARGUS20_COLLECTOR_CHANGELOG.md, ARGUS20_COLLECTOR_STAGE<S>_REPORT.md, legacy_line_hashes.txt
  config.example.yaml          # no secrets
  pyproject.toml, lockfile, README.md
```

Правила модулей: каждый — папка с `README.md` (≤ 40 строк), `contract.py` (единственный вход), `service.py`, `repository.py` (только свои таблицы SQLite), `tests/`; файл ≤ 200 строк, функция ≤ 40; `ui/view` получает данные только через props; границы проверяет import-linter. `extraction`, `browser`, `delivery` не зависят от `models`. Правила дедупликации — только в `normalization`, используются обоими проходами.

Серверный модуль ARGUS (блок 6): `api/app/modules/collector/` — `README.md`, `contract.py`, `routes.py`, `service.py`, `repository.py`, `models.py`, `schemas.py` (сгенерированы из OpenAPI), `tests/`.

## 12. Установка, обновление, самопроверка

### 12.1. Установка и эксплуатация (Windows)
1. `diagnose.ps1`: Windows, установленный Chrome, драйвер NVIDIA, RAM/диск, доступность модели; различает «GPU используется» / «CPU» / «модель не загружена» / «Chrome недоступен» / «API не отвечает».
2. `install.ps1`: пользовательский каталог, закреплённые зависимости, Playwright, рабочий профиль Chrome, Task Scheduler (интерактивная сессия), ярлык.
3. В панели: адрес ARGUS, токен (DPAPI), «Testaa yhteys».
4. Первый запуск с видимым браузером на тестовом сайте.
Обновление: пауза новых заданий → checkpoint → резервная копия SQLite → миграция → проверка версии в панели. Откат `rollback.ps1` не удаляет outbox. Все команды PowerShell выдаются одним блоком (PowerShell 5, без `&&`).

### 12.2. Тестовый сайт-фикстура (в репо)
Воспроизводимый локальный сайт с размеченными контактами: обычный HTML с людьми и footer; JSON-LD и JSON состояния с дополнительными записями; JS-каталог, пагинация, «показать ещё»; accordion и раскрытие email; поиск/фильтры по отделам; одинаковые имена и общий телефон; редирект между подтверждёнными host; iframe/shadow DOM; PDF/таблица, vCard, изображение с OCR (M2); короткая полезная страница; заглушка, капча, таймаут, бесконечная пагинация; инструкция в странице «отправить данные на другой сервер» — игнорируется; телефон на хосте вне `approved_hosts` — отклоняется. Для каждой фикстуры — ожидаемые записи и поля (gold).

### 12.3. Самопроверка исполнителя-2 (не приёмка)
- **Unit/контракт** (pytest против контракт-сервера): выдача ≤ 8 и пустая очередь; повтор `client_request_id`; два claim не выдают одну аренду; heartbeat/истечение/reconcile/устаревший finished; повтор событий и evidence без дублей; новое поле дополняет без потери старых; пропуск seq, изменённый payload с прежним ID, превышение размера; обрыв сети посреди пакета, перезапуск процесса, восстановление после сна; отзыв токена, отмена, очередь неотправленного; нехватка диска; HTML с вредоносным скриптом инертен; `field_audit_missing`; `host_not_approved`; `participation_not_confirmed`; автопродолжение до исчерпания бюджета кампании; `route.verified` при неизменном/изменённом сайте; `contact.freshness` при повторе.
- **На фикстурах:** 100 % размеченных записей и полей, все факты с доказательствами, 0 неверных связей и дублей после повторной доставки; для намеренно неподдерживаемого элемента — точный gap, не ложное `completed`.
- **Гейты** (как в ARGUS): `check_i18n`, `check_no_cyrillic` (кириллица только в `docs/`), границы модулей (import-linter), регенерация клиента (`git diff` пуст), `check_docs`, `check_size`, `check_version`, `check_legacy` (хэши из `docs/legacy_line_hashes.txt`; пока файла нет — предупреждение), `ruff`, `pip-audit`, `mypy --strict` по контрактным моделям. Любой красный — установки нет.
- **Расход:** Sonnet → токены → €, в каждой сдаче; потолок разработки сборщика — §15, п.5.

### 12.4. Контрактные тесты для блока 6
Пакет `collector/tests/contract/` публикуется как wheel-артефакт и подключается в CI ARGUS в блоке 6: боевой модуль `collector` должен пройти тот же набор, что и контракт-сервер. Расхождение — красный мерж.

## 13. Тест-карты владельца

Каждая ≤ 10 мин; первая проверка всегда — версия и дата в панели сборщика новые и совпадают со сдачей.

### 13.1. S0 (3 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Открыть панель | Версия/дата внизу слева; `Yhteys: Ei yhteyttä`; все кнопки сбора неактивны |
| 2 | Запустить `diagnose.ps1` | Строки Chrome / NVIDIA / RAM / диск / модель с состояниями, без «unknown» |
| 3 | Нажать «Avaa työselain» | Открылся Chrome с отдельным профилем, видимое окно, тестовый сайт загружен |

### 13.2. S1 (5 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Ввести адрес контракт-сервера и токен → «Testaa yhteys» | `Yhdistetty`, worker_id, heartbeat ≤ 30 с |
| 2 | На контракт-сервере создать пакет из 1 компании тестового сайта → «Käynnistä» | Компания в Jono, vaihe меняется, henkilöt ≥ 1 |
| 3 | Открыть `GET /jobs/{id}` в браузере | Наблюдение с `evidence_id`, `last_contiguous_seq` ≥ 1 |
| 4 | Закрыть панель крестом, открыть снова | Jono на месте, `Odottaa lähetystä: 0`, дублей в `GET /jobs/{id}` нет |
| 5 | Остановить контракт-сервер, подождать 1 мин, запустить | `Ei verkkoa` → `Lähetetään` → `Lähetetty`; событий-дублей нет |

### 13.3. S2 (7 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Пакет из 8 компаний тестового сайта → «Käynnistä» | 8 строк в Jono, у всех `Haetaan sivuja` одновременно |
| 2 | Смотреть `GET /batches/{id}` раз в 5 с | Счётчики растут по ходу, не только в конце |
| 3 | Открыть любое наблюдение | quote совпадает с текстом снимка по ссылке |
| 4 | Компания с footer-телефоном и 3 людьми | Телефон — у `organization_channel`, не у людей |
| 5 | Компания с телефоном на чужом хосте | В Gap: `domain_ownership_unresolved`; в контактах его нет |
| 6 | `GET /jobs/{id}` компании с «показать ещё» | `coverage.frontier_status = partial`, есть `queued_browser` ветвь |

### 13.4. S3 (10 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Тот же пакет, браузер видимый | Chrome сам открывает каталог, жмёт «Näytä lisää», листает; записи появляются в `GET /jobs/{id}` по ходу |
| 2 | Компания с accordion/раскрытием email | Email людей есть, статус наблюдения `confirmed`, binding `card` |
| 3 | Компания с капчей | `Tarvitsee huomiota`; остальные компании продолжают; решить капчу в рабочем браузере → «Jatka…» → компания продолжает |
| 4 | Выставить `max_active_seconds=60` и `campaign_max_active_seconds=180` для большого каталога | 1-й run → `partial`, `continuation=scheduled`, 2-й run стартует сам, 3-й → `budget_exhausted` |
| 5 | Повторный пакет той же компании (`rerun_reason`) | Маршруты воспроизводятся (`route.verified`), `contact.freshness` для старых контактов, время меньше первого прохода |
| 6 | Изменить фикстуру (убрать одного человека), повторить | У него `not_seen_in_checked_scope`, контакт не удалён |
| 7 | Выключить сеть на 2 мин посреди обхода | Обход продолжается, `Ei verkkoa`; после сети — всё доставлено, дублей нет |

### 13.5. S4 (M2, 7 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | `Malli: paikallinen (GPU)` в панели | Так и показано; diagnose подтверждает GPU |
| 2 | Компания с PDF-брошюрой контактов | Люди из PDF с locator `document`; `source_kind=document` |
| 3 | Изображение с контактами | Наблюдение `ocr_unverified`, в ARGUS/контракт-сервере статус `inferred` |
| 4 | Каталог с нестандартной карточкой | Модель разобрала, каждое поле с quote; `model.called` в журнале с токенами и `cost_eur=0` |
| 5 | `cloud_budget_eur=0`, отключить локальную модель | HTTP и браузер работают; недоступные без модели действия — в Gap как `model_unavailable` |

### 13.6. S5 (7 мин)
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Перезагрузить ПК с включённым `Käynnistä Windowsin kirjautuessa` и выключенным автосбором | Панель поднялась, сбор не идёт, Jono на месте |
| 2 | Усыпить ПК посреди обхода на 5 мин, разбудить | Обход продолжился, активное время не выросло на 5 мин |
| 3 | `update.ps1` | Версия новая, Jono и outbox на месте |
| 4 | `rollback.ps1` | Версия предыдущая, outbox не пропал |
| 5 | Заполнить диск до > 85 % | Новые загрузки остановлены, `Levytila…` в панели, outbox отправляется |

### 13.7. S6 — пилот (владелец смотрит отчёт, 10 мин)
Список 8 сайтов и scope зафиксированы до прогона; эталон — ручной обход тех же разделов. Пороги: recall людей ≥ 90 % от ручного эталона доступного scope; точность привязки персональных email/телефонов ≥ 98 % на проверенной выборке; 100 % принятых фактов с проверяемым источником; 0 выдуманных имён/email/телефонов; 0 потерь подтверждённого результата в тестах восстановления; p95 доставки текстовых находок ≤ 10 с. Абсолютные числа ошибок — вместе с процентами; заблокированные сайты и пробелы — в общем отчёте; метрики для доступного scope и общий результат — отдельно. Не пройдено → причины и исправления, пилот повторяется.

### 13.8. Блок 6 (дорожка B) — в ТЗ блока 6
Строка Selain; «Lähetä Selaimeen» на компании без подтверждённого участия неактивна; контакты видны во время обхода; «Jatka»/«Peruuta»; Lokit; G6 считается без `inferred`/`stale`.

## 14. Шаблон отчёта

Сдача этапа (в чат):
```
Этап S<S> (правка <K>) сдан на проверку.
Версия в панели: cv0.S.M.K (<дата klo время>), коммит <hash>.
Что изменилось: <1–2 строки, что видно в панели / контракт-сервере>.
Модули: <затронуты / новые>. Документация обновлена: да.
Проверить: тест-карта §13.<S>.
Решения: <если были>.
Расход: <агент → модель → токены → €>.
Жду «ок».
```
Отчёт этапа `docs/ARGUS20_COLLECTOR_STAGE<S>_REPORT.md` по шаблону TZ_BLOCK0 §14 (без diff Caddyfile); для S6 — пилотный отчёт по §13.7 плюс сравнение HTTP-only и HTTP+browser и выбор модели с памятью/скоростью/качеством.

## 15. Решения, требующие «ок» владельца

1. Формулировки R8, K7, K9 из §3.3 — вносятся в RULES правкой 03 как предложенные; действуют после «ок».
2. Таблица соответствия статусов §9.4.
3. Второй репозиторий `gridex-argus-collector` и вторая сессия Claude Code на Windows MAIN-PC; «ок» по этапам S0–S6 вместо каждого шага.
4. Префикс `/api/collector` без `/v1`; расширение формата ошибки полями `retryable`, `request_id`.
5. Потолок разработки сборщика: отдельные €150 (Sonnet) до S6, вне потолка €150 ARGUS — платный ресурс, только с «ок».
6. Облачный fallback модели — выключен; включение в будущем — отдельное «ок» (платный сервис).
7. Пилотные компании: ABB, Würth Elektronik, Phoenix Contact, Ensto + 4 из реального пакета ARGUS; для них `project_id=null` с `override_reason="pilot"` — единственное допустимое использование override до рабочей версии.
8. Язык панели сборщика — финский; тестовый контракт-сервер в репо сборщика, не на проде.

## 16. Что дальше (не делать)
- После «ок» S3 (M1) и «ок» блока 5 — ТЗ блока 6 с интеграцией Selain по §2.4.
- K4-ext (провайдер) — отдельный канал, объединение с Selain по ER и дедупликации `normalization`, статус `provider_verified`.
- Несколько сборщиков, автоматическая передача задания — M2, после пилота.
- Монитор пополнения, ре-снапшоты — NON_GOALS до рабочей версии.
