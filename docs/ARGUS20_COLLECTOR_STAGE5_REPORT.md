# ARGUS20_COLLECTOR_STAGE5_REPORT — этап S5 (`ARGUS20_TZ_TANDEM.md` 1.1, пакет T1), версии 0.4.3.0 и 0.4.3.1

**Дата:** 04.10.2026 · **Ветка:** `stage-5/step-2-a2-a3` (название — указание владельца), ff-мерж в `main` после самопроверки · **Шаблон:** TZ_BLOCK0 §14 (без diff Caddyfile) · **Тест-карта:** сторона сборщика тест-карт TZ_TANDEM §6 (пара 2) и §7 (пара 3).

Пакет T1 = пары 1–3 (TZ_TANDEM §3). Сдача пары 1 (A1, 0.4.2.0) — `ARGUS20_COLLECTOR_STAGE4_REPORT.md` §9; здесь — пары 2 и 3 (A2 «Пакет и контакты», A3 «Надёжность и управление») и правка 1 по итогам живой проверки.

## 1. Сделано

1. «Käynnistä» забирает задания ARGUS (claim ≤ 8 по свободным слотам); компании пакета — в таблице Jono, обход по одной, Chrome сам открывает `seed_urls`, ходит только по `approved_hosts`, в бюджете политики.
2. Каждая новая страница — снимок (`POST /evidence`, точные байты + sha256 + canonical text) и `source.processed`; каждый человек и общий канал — `contact.observed`/`contact.enriched` с `evidence_id`, locator, `quote`, `entity_type`, `binding` (по DOM), `extraction_status` и `field_audit` страницы. Наблюдение не уходит раньше своего снимка.
3. Outbox: событие и запись — одна транзакция SQLite; поток доставки ≤ 50 событий / 2 с; счётчики Lähetys. `job.finished` с `run_result_status`, `completion_reason`, `coverage` (`confirmation=unverified`), gaps; `model.called` на каждый вызов (`cost_eur=0`).
4. Страна выставки: версия сайта страны и местный офис вверх; у компании без офиса — родной язык и английский, export / Nordic / international sales и marketing; регион телефона — по странице.
5. A3: перезапуск панели, обрыв сети, истечение аренды → reconcile (`resume` / `drain_only`) без дублей, `seq` не сбрасывается; pause / resume / cancel / continue из heartbeat исполняются и подтверждаются; «Pysäytä» и `STOP` останавливают обход и claim, outbox продолжает; журнал с префиксами Lokit без PII.
6. `contract_server/` реализует весь контракт `/api/collector` и проверяет каждый запрос по OpenAPI; тестовый сайт — три новые компании (nordtec, vogel, katsa) с gold.
7. Правка 1 (0.4.3.1): строка `Keruu valmis` после каждого задания; общая формулировка `unresolved_access`; Lähetys `Ei verkkoa`, когда ARGUS не отвечает и отправлять нечего; Yhteys сохраняет «Viimeksi: …» после неудачного heartbeat.

## 2. Принятые решения (поправь, если не так)

`ARGUS20_COLLECTOR_CHANGELOG.md`: 0.4.3.0 — «Решения» пп. 1–12, 0.4.3.1 — пп. 1–2. Главное: A2+A3 — одна версия линии 0.4.x (TZ_TANDEM §11 п.4 против правила №3 CLAUDE.md — принято TANDEM), правка — последняя цифра (0.4.3.1); «Käynnistä» = сбор ARGUS, ручной обход — «Testaa paikallisesti»; привязка канала к человеку — только по DOM; человек без канала отправляется; фокус страны меняет порядок обхода, а не фильтрует людей; слова Jono — по таблице i18n TZ_SELAIN §5.

## 3. Отклонения от ТЗ

1. **Живая проверка — не на MAIN-PC.** У сессии нет доступа к MAIN-PC. Проверено в Linux-контейнере: настоящая панель (tkinter под Xvfb, видимое окно), Chromium (Playwright), `contract_server/` с сохранением состояния (`--state`), тестовый сайт на виртуальных хостах `*.localhost`, подмена модели с задержкой 2.5–5 с на вызов. Windows, настоящий Chrome, `qwen2.5:14b` на RTX 4090, `install.ps1` и боевой ARGUS не проверены — **ждёт владельца** (MAIN-PC) и B2/B3 на проде.
2. **Строки тест-карт «Где: ARGUS»** (Soittolista, чипы, «Avaa lähde», строка расхода, Lokit) — сторона B; вместо них проверено, что принял контракт-сервер (`/_stand/jobs/{id}/contacts`, `/_stand/evidence/{id}`).
3. **Пауза из ARGUS — 32 с вместо «≤ 30 с»** (TZ_TANDEM §7 стр. 3): команда приходит с ответом heartbeat (27 с — окно heartbeat 30 с, TZ_SELAIN §8), затем обход дочитывает уже открытую страницу (один вызов модели, 5 с) и останавливается; Chrome дальше по компании не ходит. Интервал heartbeat не менял — он задан ТЗ; вопрос — §9.
4. Обрыв сети имитирован остановкой контракт-сервера (`kill -9`) на 71 с, не выключением Wi-Fi: в контейнере сеть не выключить, для сборщика это тот же случай (HTTP 0).
5. Версия в панели — `cv0.4.3.1 (ei asennustietoa)`: дата сборки и хэш появляются после `install.ps1` (только Windows).

## 4. Diff Caddyfile

Не относится к сборщику.

## 5. Самопроверка

- `pytest`: **394 passed**, 0 failed (было 387, +7 новых) (настоящая панель под Xvfb, Chromium, контракт-сервер, тестовый сайт, подмена модели).
- Гейты `scripts/run_gates.py`: **11 ok, 0 failed** (legacy — только одиночные совпадения типовых строк).
- Живой прогон (§7): 6 пакетов, 16 заданий, 0 отклонённых событий, 0 дублей людей, все цитаты найдены в своих снимках (75 из 75 на пакет из трёх компаний), `cost_eur=0` у всех вызовов модели.

## 6. Версия

`VERSION` = `pyproject.toml` = `0.4.3.1`. Коммиты: `a074bd7` (docs: TZ_TANDEM 1.1), `adc95c5` (`stage-5 step-2`, 0.4.3.0), правка — `stage-5 step-2 fix-1` (0.4.3.1). Теги не ставлю: TZ_TANDEM §11 п.4 — `v0.4.M` при согласии владельца.

## 7. Тест-карта и живая проверка (контейнер, 04.10.2026, время UTC)

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 0 | Версия в панели | Открыл панель после правки | `cv0.4.3.1 (ei asennustietoa)` внизу слева | 17:28 |
| 1 | §6 стр. 2 «Käynnistä» | Пакет 1: Fixture Oy, Nordtec AB, Vogel Antriebstechnik GmbH, Katsa Oy; «Testaa yhteys» → `Yhdistetty`; «Käynnistä» | 4 строки в Jono, Chromium сам открыл первый сайт; люди появляются в таблице и уходят в контракт-сервер по ходу обхода (p95 2.5 с) | 17:17:04–17:17:21 |
| 2 | §6 стр. 3–5 (на контракт-сервере) | Дождался конца, проверил `/_stand` | Fixture Oy 7 людей / 16 каналов / 5 источников `Valmis`; Nordtec 4 / 13 / 7 (финский офис: «Maajohtaja, Suomi» с `/fi/`); Vogel 5 / 14 / 7 (без офиса в FI: «Exportleiter Nordeuropa», `/en/`, `+49…`); Katsa `Osittain valmis · pääsy sivustolle jäi ratkaisematta` (seed ушёл редиректом на другой хост → gap `domain_ownership_unresolved`, ничего не отправлено). Каждая цитата есть в тексте снимка, URL — хост компании; статусы `published_direct` / `published_general` / `inferred` по §9.4 | 17:17–17:21 |
| 3 | §6 стр. 6 | `model_calls` на контракт-сервере | `model.called` на каждый вызов, `provider=local`, `cost_eur=0` | 17:21 |
| 4 | §7 стр. 1 — обрыв | Пакет 3 (Fixture, Nordtec, Vogel); посреди обхода Fixture остановил контракт-сервер на 71 с, запустил с тем же состоянием | Yhteys `Ei verkkoa: HTTP 0 …`, `Viimeksi: 17:28:47` сохранилось; Lähetys `Ei verkkoa`, `Odottaa lähetystä` рос до 80, обход шёл дальше (Fixture → Nordtec → Vogel); после запуска `Lähetetään` → `Lähetetty`, 0 в очереди; в ARGUS 7 / 4 / 5 людей, по одному run, 0 дублей | 17:28:48 стоп, 17:29:59 старт, 17:30:07 `Lähetetään`, 17:30:15 `Lähetetty` |
| 5 | §7 стр. 2 — перезапуск | Пакет 4; посреди Fixture (5 из 7 людей, 5 событий не отправлены) убил панель (`kill -9`), открыл, «Testaa yhteys», «Käynnistä» | Обход продолжился с `team-2.html` (checkpoint), тот же run (generation 1), `seq` 1…35 без пропусков, 7 людей, 0 дублей; Nordtec 4 | 17:31:37 убил, 17:31:52 открыл, 17:31:56 «Käynnistä» |
| 6 | §7 стр. 3 — пауза | Пакет 5; `stand control <Fixture> pause` при 3 найденных | Команда пришла с heartbeat в 17:35:15, обход остановился в 17:35:20 (Jono `Tauolla`), Chromium перешёл к Nordtec; ack `applied` | 17:34:48 → 17:35:20 (32 с, см. §3 п.3) |
| 7 | §7 стр. 5 — отмена | `stand control <Nordtec> cancel` во время обхода (2 человека) | 409 `job_cancelled` на отправке → reconcile `drain_only` → `job.finished` `cancelled` / `manual_cancel`, Jono `Keskeytetty`; 2 человека остались в ARGUS; поздние события приняты без смены состояния (`state_applied=false`); ack команды — `already_applied` | 17:35:49 → 17:35:53 |
| 8 | §7 стр. 4 — продолжение | `stand control <Fixture> resume` | ack `applied` с heartbeat 17:36:15; после Vogel Fixture продолжилась с оставшегося frontier (`index.html`), не с начала: `Valmis`, 7 людей, один run | 17:35:54 → 17:37:08 |
| 9 | A3.3 «Pysäytä» | Пакет 6; «Pysäytä» посреди Fixture (3 человека, 5 событий в очереди) | `Keruu pysäytetty`, Jono `Pysäytetty`, «Käynnistä» активна; outbox дослал 5 → 0; 12 с — Nordtec не взята; «Käynnistä» → Fixture продолжилась и `Valmis` (7) | 17:39:46 → 17:39:52; 17:40:04 → 17:40:50 |
| 10 | A3.3 `STOP` | Файл `STOP` в корне посреди Nordtec (2 человека, 5 в очереди); потом удалил, «Käynnistä» | `STOP-tiedosto estää keruun`, «Käynnistä» неактивна, обход остановлен, outbox дослал 5 → 0; после удаления — Nordtec `Valmis` (4) | 17:41:18 → 17:41:23; 17:41:29 → 17:42:10 |
| 11 | §7 стр. 6 — журнал | `logs/collector-2026-10-04.log` | 785 строк: `http` 54, `browser` 132, `extraction` 96, `delivery` 335, `model` 168; ни одного имени, телефона, почты, токена из gold | 17:42 |

Найдено живой проверкой и исправлено в правке 1 — CHANGELOG 0.4.3.1, чек-лист пп. 1–4 (все — сделано).

## 8. Расход

Claude Code (Исполнитель-2): основная сессия + 2 субагента `general-purpose` (генератор клиента ≈ 388 тыс. токенов, контракт-сервер ≈ 329 тыс. токенов, включая кэш). Основная сессия по журналу: ≈ 0.44 млн выходных токенов, ≈ 116 млн прочитано из кэша, ≈ 0.9 млн записано в кэш. € — в биллинге владельца (цен в `ARGUS20_ASSETS.md` нет, сам не считаю). Рантайм-модель в проверке — подмена, платных вызовов нет.

## 9. Вопросы Архивариусу

1. TZ_TANDEM §7 стр. 3: «≤ 30 с» — это смена чипа в ARGUS (сразу по `control`) или остановка Chrome у сборщика? При heartbeat 30 с (TZ_SELAIN §8) сборщик получает команду до 30 с и останавливается после текущего шага (живьём — 32 с).
2. TZ_TANDEM §7 стр. 3/5 называют состояния `Keskeytetty` (pause) и `Peruttu` (cancel), а таблица i18n TZ_SELAIN §5 — `job.state.paused = Tauolla`, `job.state.cancelled = Keskeytetty`, и `Peruttu` в таблицах нет. Панель сборщика следует TZ_SELAIN §5; нужна ли правка одного из ТЗ?

---

# Пакет T2 (пары 4–5) и дополнение к A2 от 05.10.2026 — версии 0.4.4.0, 0.4.5.0, 0.4.6.0

**Дата:** 05.10.2026 · **Основание:** «ок S5 (cv0.4.3.1)», «Начинай A4 и A5», дополнения к A2 пп. 1–5 (владелец, 05.10.2026) · **Шаги:** `stage-5/step-3-a2-country` (0.4.4.0), `stage-5/step-4-a4-history` (0.4.5.0), `stage-5/step-5-a5-pilot` (0.4.6.0), каждый — ff в `main` · **Тест-карта:** TZ_TANDEM §8 (пара 4) и тест-карты владельца из дополнений (Ledvance, Malux); пара 5 — сам пилот, ждёт владельца.

## T2.1. Сделано

1. **Страна выставки (A2 п. 1–2).** На международной странице контактов со списком стран (аккордеон, вкладки, выпадающий список, ссылки ≥ 3 стран) открывается только страна выставки; её офис — одна сущность `office` (название, адрес, vaihde, общий email, `country`), телефон — в формате страны раздела (`09-7422 3300` → `+358974223300`), факс не берётся; по ссылке на местную версию (`/fi-fi`, `/fi`, `fi.`) обход идёт за людьми; другие страны не открываются и в снимок не читаются.
2. **Проверка «не бот» (A2 п. 3).** До 20 с ожидания; не прошла — `needs_attention` (не `failed`), блок Huomio с «Avaa työselain» и «Jatka käsin tehdyn toimen jälkeen»; прогон продолжается с того же URL, решённая проверка из gaps снимается.
3. **Вкладки отделов (A2 п. 4).** Открываются все вкладки, продажи и маркетинг первыми; у человека — отдел (заголовок группы или вкладка).
4. **Местная версия первой (A2 п. 5).** Seed `.fi` / `/fi/` — сначала эта версия, затем версии других стран; у людей оттуда — страна из `<html lang>` (SE).
5. **История (A4.1–A4.2).** Повторный пакет: `reconfirmed` / `changed` + `supersedes_observation_id`; в конце прогона `contact.freshness` по каждому полю каждого известного контакта, `freshness_summary`.
6. **Полнота (A4.3).** Gap на каждую непройденную релевантную ветвь (`budget_reached`, `no_progress`, `domain_ownership_unresolved` для ссылок бренда вне approved_hosts); `coverage.basis` / `expected_count` / `found_count`, подробный `scope_description`.
7. **Пауза после текущей страницы** (решение владельца): состояние `paused` берётся из ответа на каждый пакет событий.
8. **Готовность к пилоту (A5).** Cookie-баннеры (сначала «только необходимые»); модуль `pilot` и `scripts\pilot_report.ps1` — таблицы сборщика для отчёта пилота.

## T2.2. Принятые решения (поправь, если не так)

CHANGELOG 0.4.4.0 пп. 1–6, 0.4.5.0 пп. 1–5, 0.4.6.0 пп. 1–3. Главное: факс не отправляется вовсе; страна и отдел — только с доказательством (заголовок / вкладка / `<html lang>`); «не обходить другие страны» — для списков стран, переключатель версий — по фокусу; `not_seen_in_checked_scope` — только при исчерпанном frontier, иначе `not_checked`; cookie «принять» — только если другого варианта нет.

## T2.3. Отклонения от ТЗ

1. **Живая проверка — в контейнере, не на MAIN-PC** (как и в T1): Xvfb, Chromium, контракт-сервер, тестовый сайт, подмена модели. Реальные ledvance.com и malux.com из контейнера недоступны (исходящий доступ закрыт политикой) — фикстуры построены по описанию владельца.
2. **Пилот (пара 5) не проведён:** нужны MAIN-PC, прод ARGUS с B2–B4, `owner_known_url` для трёх компаний — ждёт владельца. `ARGUS20_COLLECTOR_STAGE6_REPORT.md` не создан: данных пилота нет, демо-цифры не ставлю.
3. **Тег `v0.4.3`** создан локально на `b700d40`, но git-прокси сессии не пропускает отправку тегов (как и удаление веток) — команда для владельца в сдаче.

## T2.4. Самопроверка

`pytest`: **500 passed**, 0 failed (было 394 в T1). Гейты `scripts/run_gates.py`: **11 ok, 0 failed**. Контракт-сервер (подагент): 172 теста стенда в составе этих 500.

## T2.5. Версия

`VERSION` = `pyproject.toml` = `0.4.6.0`. Коммиты в `main`: `eeaf4c9`, `a916967` (шаг 3, 0.4.4.0), `cc67a39` (шаг 4, 0.4.5.0), шаг 5 (0.4.6.0) — в сдаче.

## T2.6. Живая проверка (контейнер, 05.10.2026, время UTC)

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Панель после каждого шага | `cv0.4.4.0`, `cv0.4.5.0`, `cv0.4.6.0` (ei asennustietoa) | 04:28, 05:17, 05:36 |
| 2 | Ledvance: Finland | Пакет ledvance+malux, «Käynnistä» | Обход: главная → международная страница → открыт только Finland → `/fi-fi/` (проверка «не бот» прошла сама за ~3 с) → Yhteystiedot. В ARGUS: офис `FI` `LEDVANCE Oy`, `Testikatu 1, 00100 Helsinki`, `+358974223300`, `asiakaspalvelu@ledvance.com` (`published_general`), факса нет, других стран нет; 6 людей с `/fi-fi/`, у всех `FI` | 04:33:23 → 04:34:00 |
| 3 | Malux: вкладки, FI → SE | Тот же пакет | 25 людей: 20 финнов (все 4 вкладки; Joakim Flakholm · Maajohtaja · Johto; Henkilöstö, Myynti, Markkinointi, Logistiikka…), затем 5 шведов с `SE`; общие каналы `FI` и `SE` раздельно; 0 отклонений | 04:34:26 |
| 4 | Проверка «не бот» не проходит | Сайт в варианте `challenge-stuck`, повтор Ledvance | Строка `Selaintarkistus ei päästänyt läpi: …/fi-fi/ — katso Huomio`, Jono `Tarvitsee huomiota`, блок Huomio; после перезапуска панели блок на месте | 04:35:45, 04:38:14 |
| 5 | Владелец проходит проверку | «Avaa työselain» в Huomio → рабочий браузер на `/fi-fi/` → проверка пройдена → окно закрыто → «Jatka käsin tehdyn toimen jälkeen» → «Käynnistä» | Тот же прогон (runs_completed 1) дошёл до `Valmis`, 6 людей без дублей, gap проверки снят | 04:39:45 → 04:41:03 |
| 6 | §8 стр. 1 — повтор | Fixture Oy второй раз (`rerun_reason`) | 7 человек — строк не прибавилось, `last_seen_at` = сегодня, 32 проверки `reconfirmed`, summary совпадает | 05:14:08 → 05:14:41 |
| 7 | §8 стр. 2 — человек ушёл | Сайт в варианте `departed` (нет Pekka Salo), повтор | Pekka Salo: 4 проверки `not_seen_in_checked_scope` с описанием объёма, `not_seen` в ARGUS, контакт на месте; Jono — 6 человек | 05:15:03 → 05:15:33 |
| 8 | §8 стр. 3 — неполнота | Katsa | `Osittain valmis · pääsy sivustolle jäi ratkaisematta`, gap `domain_ownership_unresolved` `http://katsa-oy.localhost:8765/` | 05:13:50 |
| 9 | Пауза после страницы | Nordtec, модель 4 с на вызов, `pause` из ARGUS | Остановка через 3.9 с (ответ на пакет событий), без heartbeat; `resume` → `Valmis` | 05:16:27 → 05:16:31 |
| 10 | Cookie-баннер | Vogel (баннер Cookiebot-типа) | Журнал `cookie banner on vogel.localhost: necessary (Nur notwendige)`, в scope `cookie banners answered (vogel.localhost: necessary)` | 05:36:42 |
| 11 | Отчёт пилота | `python -m argus_collector.pilot --batch …` по пакету vogel+ledvance+malux | Таблица по компаниям (время, страницы, действия, вызовы модели, люди, каналы, published_direct), порог 100 % (выполнен), 10 из 10 телефонов: хост в approved_hosts, цитата в снимке | 05:38 |

Найдено живой проверкой и исправлено до сдачи (CHANGELOG 0.4.4.0, «Найдено живой проверкой»): `mailto:` из закрытых разделов уходили в шапку компании, у общих каналов не было страны, пройденная проверка оставалась gap'ом, панель с Huomio была выше экрана.

## T2.7. Пилот (пара 5) — порядок для владельца на MAIN-PC

1. `install.ps1` из `main` (0.4.6.0), панель → «Testaa yhteys» на прод `https://argus.gridex.fi` с токеном сборщика.
2. В ARGUS: пакет из 8 компаний §9 п.1 («Lähetä Selaimeen»), `owner_known_url` для Schneider / Prysmian / Phoenix Contact.
3. «Käynnistä»; при `Tarvitsee huomiota` — Huomio → «Avaa työselain», пройти проверку, «Jatka…».
4. После пакета: `scripts\pilot_report.ps1 -Batch <batch_id>` → `%LOCALAPPDATA%\Gridex\ArgusCollector\reports\pilot-<batch_id>.md`; эти таблицы + метрики ARGUS (Gold P · R, Nimetty henkilö, Soitettavia до/после) — в `ARGUS20_COLLECTOR_STAGE6_REPORT.md`.

## T2.8. Расход

Claude Code (Исполнитель-2): основная сессия с «ок S5» — ≈ 0.29 млн выходных токенов, ≈ 135 млн прочитано из кэша, ≈ 0.74 млн записано в кэш; 2 субагента `general-purpose` (фикстуры test_site ≈ 186 тыс. токенов, контракт-сервер ≈ 217 тыс. токенов). € — в биллинге владельца. Рантайм-модель — подмена, платных вызовов нет.

## T2.9. Вопросы Архивариусу

1. Формат `KnownContact.fields` (B4) в контракте открыт: сборщик читает строку, список, объект `{value, observation_id}` и список объектов. Какой отдаёт ARGUS?
2. Новые поля наблюдений: `country` (ISO, цитата — заголовок раздела или значение `<html lang>`, locator `dom html[lang]`), `department`, `office_name`, `address`. Так ли их ждёт ARGUS для шапки, «Muut maat» и чипа страны?
3. Факс по решению 05.10 не отправляется вовсе, а FieldAudit требует учесть каждое контактное поле. Оставить так или отправлять как `extra` (`extra_label=Fax`)?

**Ответы на T2.9** — `docs/ANSWERS_S5.md` (ARGUS, 05.10.2026), исполнены в 0.4.7.0 (раздел T3).

# Шаг 6: паринг в один клик и поля `extra` — версия 0.4.7.0

**Дата:** 05.10.2026 · **Основание:** решение владельца 05.10.2026 («Шаг паринга в один клик…», «Возьми файл docs/collector_contract/ANSWERS_S5.md… Это входит в шаг паринга») · **Ветка:** `stage-5/step-6-pairing`, ff в `main` · **Контракт:** не менялся.

## T3.1. Сделано

1. **Yhteys — одно поле.** «Paritusavain» + «Yhdistä» (или Enter) вместо адреса, worker_id, токена и «Testaa yhteys». Строка `argus://pair?url=…&worker=…&token=…` разбирается, сохраняется (адрес и worker_id — открыто, токен — DPAPI), сразу heartbeat. Строка `Paritettu: <адрес> · <worker_id> · tunnus ****abcd`. Поле замаскировано и очищается сразу после нажатия.
2. **Сам при каждом запуске.** Сохранённый паринг подключается при старте панели; пока ARGUS недоступен — `Ei verkkoa`, повтор каждые 30 с; `Tunnus hylätty` — повторы стоп до нового ключа.
3. **Неверный ключ** — красная строка с причиной, ничего не сохраняется и не отправляется.
4. **Пустые значения по умолчанию.** Адреса ARGUS нет ни в `config.example.yaml`, ни в `runtime.Config`; адрес стенда в коде сборщика не зашит. Контракт-сервер печатает ключ паринга на каждый токен при старте.
5. **`extra` по ANSWERS_S5.** `country`, `department`, `office_name`, `address`, `fax` — только `field="extra"` + `extra_label`, с цитатой; строка field audit — `extra`, `reason` = ключ. Факс — `extra` `fax` (не телефон). `KnownContact.fields` читается в форме ответа §1 (ключ = имя поля, значение — строка или список строк); контракт-сервер отдаёт эту форму и отклоняет прямые `country`/…/`fax` и `extra` без метки.

## T3.2. Принятые решения (поправь, если не так)

CHANGELOG 0.4.7.0 пп. 1–6. Главное: «разобрал → сохранил → подключился» (ключ сохраняется до ответа ARGUS); http — только для этой машины; `url` с `/api/collector` и без принимается; `+` в значениях — не пробел; факс вне раздела страны — общий канал компании.

## T3.3. Отклонения

1. Живая проверка — в контейнере (Xvfb, Chromium, контракт-сервер, тестовый сайт, подмена модели), не на MAIN-PC; дата сборки в панели появится после `install.ps1`.
2. Коммита `04022ca` в `GridexOy/gridex-argus20` нет; `ANSWERS_S5.md` взят из `main` на `8c0279c` (blob `d8b6c3d`), положен как есть. Прочитан только этот файл (частичный клон, один blob) и сообщение коммита `8c0279c` (ARGUS 0.4.22.0 выдаёт ключ `argus://pair?…` в Asetukset → Selain) — кода ARGUS не открывал. Точную кодировку ключа ARGUS я не видел: парсер принимает и закодированные (`%3A%2F%2F`), и сырые значения.
3. Форма known_contacts на контракт-сервере сменилась на форму ANSWERS_S5 §1 (было — список объектов с `observation_id`). Без `observation_id` от ARGUS `changed` уходит без `supersedes_observation_id` (контракт допускает null).
4. Теги: git-прокси сессии не пропускает отправку тегов — теги созданы локально, команда для владельца в сдаче.

## T3.4. Самопроверка

`pytest`: **531 passed**, 0 failed (было 500 в T2). Гейты `scripts/run_gates.py`: **11 ok**, 0 failed. Новые тесты: `worker_auth/tests/test_pairing_key.py` (17), `ui/tests/test_ui_connection.py` (5, под Xvfb: вставка ключа, автоподключение, неверный ключ, отклонённый токен, ARGUS недоступен), `scheduler/tests/test_extra_fields.py` (5), `contract_server/tests/test_extra_rule.py` (7).

## T3.5. Версии и теги

| Версия | Шаг | Коммит в `main` | Тег |
|---|---|---|---|
| 0.4.4.0 | `stage-5/step-3-a2-country` | `eeaf4c9`, `a916967` (05.10 04:27, 04:50 UTC) | `cv0.4.4` → `a916967` |
| 0.4.5.0 | `stage-5/step-4-a4-history` | `cc67a39` (05.10 05:12 UTC) | `cv0.4.5` → `cc67a39` |
| 0.4.6.0 | `stage-5/step-5-a5-pilot` | `48c9e35`, `446e308` (05.10 05:36, 05:40 UTC) | `cv0.4.6` → `446e308` |
| 0.4.7.0 | `stage-5/step-6-pairing` | коммит шага (в сдаче) | `cv0.4.7` → коммит шага |

`v0.4.3` (на `b700d40`, по «ок S5») — как раньше.

## T3.6. Живая проверка (контейнер, 05.10.2026, время UTC)

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.7.0 (ei asennustietoa)`; Yhteys — одно поле «Paritusavain» и «Yhdistä», `Ei paritettu: liitä ARGUSista saatu paritusavain…`, `Ei yhteyttä` | 07:08:18 |
| 2 | Ключ стенда | Запустил контракт-сервер | В выводе: `pairing key worker-main-pc: argus://pair?url=http%3A%2F%2F127.0.0.1%3A8900&worker=worker-main-pc&token=test-token-abc` | 07:08 |
| 3 | Неверный ключ | Вставил `http://127.0.0.1:8900 worker-main-pc test-token-abc`, Enter | Красным `Paritusavain ei kelpaa: muoto on argus://pair?url=…&worker=…&token=…`, поле пустое; на стенде worker не появлялся, в каталоге панели ничего не сохранено | 07:09:12 |
| 4 | http на другую машину | Ключ с `url=http://argus.example.fi`, «Yhdistä» | `Paritusavain ei kelpaa: osoitteen pitää alkaa https:// (http vain tällä koneella)` | 07:09:25 |
| 5 | Неверный токен | Ключ стенда с `token=wrong-token-0000` | `Paritettu: http://127.0.0.1:8900 · worker-main-pc · tunnus ************0000`, красным `Tunnus hylätty` | 07:09:59 |
| 6 | Паринг | Вставил ключ из п. 2, «Yhdistä» | `Yhdistetty`, `Viimeksi: 07:10:09`, `tunnus **********-abc`; стенд: worker `connected`, `last_seen_at 07:10:09`; `worker_connection.json` — адрес и worker_id, токена в открытом виде на диске нет | 07:10:12 |
| 7 | Сам при запуске | Закрыл и открыл панель, ничего не вводил | `Yhdistetty`, `Viimeksi: 07:10:25` (панель запущена в 07:10:24) | 07:10:30 |
| 8 | ARGUS выключен | Остановил стенд, открыл панель | `Ei verkkoa: HTTP 0: …/workers/heartbeat: <urlopen error [Errno 111] Connection refused>` | 07:10:49 |
| 9 | ARGUS вернулся | Запустил стенд в 07:10:50 | Панель сама: `Yhdistetty`, `Viimeksi: 07:11:13` | 07:11:15 |
| 10 | Сбор и `extra` | Пакет Ledvance + Malux, «Käynnistä» | Jono: LEDVANCE Oy 6 · Malux Finland Oy 25, оба `Valmis`, `Lähetetty`; 36 событий контактов приняты, 0 отклонений. Ledvance: офис — `phone +358974223300`, `email asiakaspalvelu@ledvance.com`, `extra:country FI` (цитата `Finland`), `extra:office_name`, `extra:address`, `extra:fax +358974223301` (цитата `09-7422 3301`); люди — `extra:country FI` (цитата `fi-FI`). Malux: Joakim Flakholm `extra:department Johto`, шведы `extra:country SE`. Прямых `country`/…/`fax` — 0. Field audit: `extra`/country 240, department 145, office_name 1, address 1, fax 2; `mapped` 1160 | 07:11:31 → 07:12:04 |

Найдено живой проверкой и исправлено до сдачи: в смотровом виде стенда (`/_stand/.../contacts`) не было `extra_label` — добавлен.

## T3.7. Совпадения legacy (гейт `check_legacy`, 57 предупреждений)

Гейт хэширует каждую строку кода длиной ≥ 40 символов без пробелов и ищет хэш в `docs/legacy_line_hashes.txt`; одна строка — предупреждение, три подряд — красный гейт. На коммите шага: **57 совпадений, самая длинная серия — 2 строки подряд** (гейт зелёный). Все 57 — общие строки стандартной библиотеки, идиомы Python, сгенерированное из OpenAPI поле и HTML-шаблон тестового сайта; логики старой системы среди них нет. По типам: meta viewport тестового сайта — 22, импорт stdlib — 8, `mkdir(parents=True, exist_ok=True)` — 7, чтение JSON-файла — 3, сигнатура `HTMLParser.handle_starttag` — 3, перехват ошибок `subprocess` — 3, строковая идиома — 2, `sys.path.insert` скрипта — 2, проверка `isinstance(..., dict)` — 2, замер мс через `time.monotonic` — 2, `ast.parse` — 1, поле из OpenAPI — 1, `unicodedata.normalize` — 1.

| # | Файл:строка | Тип строки | Строка |
|---|---|---|---|
| 1 | `collector/src/argus_collector/api_client/types_2.py:26` | поле типа, сгенерированное из OpenAPI | `participation_status: ParticipationStatus` |
| 2 | `collector/src/argus_collector/delivery/contract.py:18` | импорт стандартной библиотеки | `from datetime import UTC, datetime, timedelta` |
| 3 | `collector/src/argus_collector/diagnostics/repository.py:51` | перехват ошибок subprocess (stdlib) | `except (OSError, subprocess.TimeoutExpired) as exc:` |
| 4 | `collector/src/argus_collector/discovery/service.py:7` | импорт стандартной библиотеки | `from urllib.parse import urlsplit, urlunsplit` |
| 5 | `collector/src/argus_collector/discovery/service.py:50` | строковая идиома (срез / поиск) | `return host[4:] if host.startswith("www.") else host` |
| 6 | `collector/src/argus_collector/evidence/repository.py:15` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 7 | `collector/src/argus_collector/extraction/repository.py:33` | сигнатура метода HTMLParser (stdlib) | `def handle_starttag(self, tag: str, attrs: list[tuple[str, str \| None]]) -> None:` |
| 8 | `collector/src/argus_collector/models/contract.py:96` | замер длительности в мс (stdlib time) | `elapsed = int((time.monotonic() - started) * 1000)` |
| 9 | `collector/src/argus_collector/models/repository.py:57` | замер длительности в мс (stdlib time) | `elapsed_ms = int((time.monotonic() - started) * 1000)` |
| 10 | `collector/src/argus_collector/models/service.py:117` | строковая идиома (срез / поиск) | `start, end = text.find("{"), text.rfind("}")` |
| 11 | `collector/src/argus_collector/models/service.py:124` | проверка типа значения (идиома Python) | `return parsed if isinstance(parsed, dict) else None` |
| 12 | `collector/src/argus_collector/pilot/service.py:82` | проверка типа значения (идиома Python) | `usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}` |
| 13 | `collector/src/argus_collector/runtime/journal.py:13` | импорт стандартной библиотеки | `from datetime import UTC, datetime, timedelta` |
| 14 | `collector/src/argus_collector/runtime/journal.py:15` | импорт стандартной библиотеки | `from urllib.parse import urlsplit, urlunsplit` |
| 15 | `collector/src/argus_collector/runtime/journal.py:45` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 16 | `collector/src/argus_collector/scheduler/tests/test_collector_recovery.py:5` | импорт стандартной библиотеки | `from datetime import UTC, datetime, timedelta` |
| 17 | `collector/src/argus_collector/scheduler/views.py:7` | импорт стандартной библиотеки | `from datetime import UTC, datetime, timedelta` |
| 18 | `collector/src/argus_collector/walk/context.py:57` | Unicode-нормализация (stdlib) | `decomposed = unicodedata.normalize("NFKD", text.casefold())` |
| 19 | `collector/src/argus_collector/walk/sink.py:14` | импорт стандартной библиотеки | `from dataclasses import asdict, dataclass, field` |
| 20 | `collector/src/argus_collector/worker_auth/repository.py:84` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 21 | `collector/src/argus_collector/worker_auth/repository.py:107` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 22 | `collector/src/argus_collector/worker_auth/repository.py:116` | чтение JSON-файла (stdlib) | `data = json.loads(path.read_text(encoding="utf-8"))` |
| 23 | `collector/tests/unit/test_gates.py:25` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 24 | `contract_server/htmltext.py:21` | сигнатура метода HTMLParser (stdlib) | `def handle_starttag(self, tag: str, attrs: list[tuple[str, str \| None]]) -> None:` |
| 25 | `contract_server/persistence.py:49` | создание каталога (pathlib, stdlib) | `directory.mkdir(parents=True, exist_ok=True)` |
| 26 | `contract_server/tests/conftest.py:6` | импорт стандартной библиотеки | `from datetime import UTC, datetime, timedelta` |
| 27 | `test_site/site/contact.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 28 | `test_site/site/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 29 | `test_site/site/team-2.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 30 | `test_site/site/team.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 31 | `test_site/sites/ledvance/en-int/company/contact/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 32 | `test_site/sites/ledvance/en-int/company/contact-select/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 33 | `test_site/sites/ledvance/en-int/company/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 34 | `test_site/sites/ledvance/en-int/products/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 35 | `test_site/sites/ledvance/fi-fi/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 36 | `test_site/sites/ledvance/fi-fi/tuotteet/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 37 | `test_site/sites/ledvance/fi-fi/yhteystiedot/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 38 | `test_site/sites/ledvance/fi-fi/yritys/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 39 | `test_site/sites/ledvance/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 40 | `test_site/sites/malux/fi/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 41 | `test_site/sites/malux/fi/tuotteet/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 42 | `test_site/sites/malux/fi/yhteystiedot/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 43 | `test_site/sites/malux/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 44 | `test_site/sites/malux-se/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 45 | `test_site/sites/malux-se/sv/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 46 | `test_site/sites/malux-se/sv/kontakt/index.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 47 | `test_site/templates/challenge.html:7` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 48 | `test_site/tests/blocks.py:54` | сигнатура метода HTMLParser (stdlib) | `def handle_starttag(self, tag: str, attrs: list[tuple[str, str \| None]]) -> None:` |
| 49 | `test_site/variants/departed/site/team.html:5` | HTML-шаблон: meta viewport (тестовый сайт) | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| 50 | `scripts/codegen/spec.py:26` | чтение JSON-файла (stdlib) | `data = json.loads(path.read_text(encoding="utf-8"))` |
| 51 | `scripts/gates/check_codegen.py:64` | перехват ошибок subprocess (stdlib) | `except (OSError, subprocess.TimeoutExpired) as exc:` |
| 52 | `scripts/gates/check_i18n.py:29` | чтение JSON-файла (stdlib) | `data = json.loads(path.read_text(encoding="utf-8"))` |
| 53 | `scripts/gates/check_i18n.py:36` | разбор Python-файла (ast, stdlib) | `tree = ast.parse(path.read_text(encoding="utf-8"))` |
| 54 | `scripts/gates/check_tools.py:37` | перехват ошибок subprocess (stdlib) | `except (OSError, subprocess.TimeoutExpired) as exc:` |
| 55 | `scripts/gen_api_client.py:18` | путь импорта скрипта (stdlib sys) | `sys.path.insert(0, str(Path(__file__).resolve().parent))` |
| 56 | `scripts/gen_api_client.py:36` | создание каталога (pathlib, stdlib) | `path.parent.mkdir(parents=True, exist_ok=True)` |
| 57 | `scripts/run_gates.py:13` | путь импорта скрипта (stdlib sys) | `sys.path.insert(0, str(Path(__file__).resolve().parent))` |

## T3.8. Сдачи шагов 0.4.4–0.4.6 (по шаблону; подробно — T2.1–T2.6)

**cv0.4.4.0** — шаг `stage-5/step-3-a2-country`, коммиты `eeaf4c9` + `a916967` (05.10 04:27 / 04:50 UTC), тег `cv0.4.4` → `a916967`. Что изменилось: в списке стран открывается только Finland и её офис (адрес, vaihde, общий email), по ссылке /fi-fi — за людьми; проверка «не бот» ждётся 20 с, иначе Huomio (`Tarvitsee huomiota`); все вкладки отделов, продажи первыми; при seed `.fi` / `/fi/` — сначала финская версия, потом шведская с SE; закрытые вкладки читаются после открытия; панель прокручивается. Модули: discovery, browser, extraction, walk, scheduler, ui. Живая проверка: T2.6 строки 1–5 (04:28–04:41).

**cv0.4.5.0** — шаг `stage-5/step-4-a4-history`, коммит `cc67a39` (05.10 05:12 UTC), тег `cv0.4.5` → `cc67a39`. Что изменилось: повторный пакет подтверждает известные контакты (`reconfirmed`, строк не прибавляется), ушедший — `not_seen_in_checked_scope`, изменённое поле — `changed`; gap на каждую непройденную ветвь; `coverage.basis` / `expected_count`; «Pysäytä» из ARGUS — после текущей страницы (3.9 с). Модули: scheduler (history, freshness), walk (coverage, actions). Живая проверка: T2.6 строки 6–9 (05:13–05:16).

**cv0.4.6.0** — шаг `stage-5/step-5-a5-pilot`, коммиты `48c9e35` + `446e308` (05.10 05:36 / 05:40 UTC), тег `cv0.4.6` → `446e308`. Что изменилось: cookie-баннер — «только необходимые» первыми; модуль `pilot` и `scripts\pilot_report.ps1` — таблицы сборщика для отчёта пилота. Модули: browser, pilot (новый), scheduler, delivery. Живая проверка: T2.6 строки 10–11 (05:36–05:38).

## T3.9. Расход

Claude Code (Исполнитель-2), основная сессия, шаг 6 — в сдаче (токены сессии; € — в биллинге владельца). Субагентов в шаге 6 не было. Рантайм-модель — подмена, платных вызовов нет.

# Шаг 7: разбор Beckhoff, тайминг, маршрутизация моделей — версия 0.4.8.0

**Дата:** 05.10.2026 · **Основание:** «Разбор живого обхода Beckhoff (05.10, MAIN-PC) … две задачи», «Маршрутизация моделей (владелец 05.10)» · **Ветка:** `stage-5/step-7-routing`, ff в `main` · **Контракт:** не менялся.

## T4.1. Лог Beckhoff с MAIN-PC

Лог из `%LOCALAPPDATA%\Gridex\ArgusCollector\logs\` в сессию не пришёл. Принято решение: причину ухода в Germany и замер «до» снимаю на фикстуре `beckhoff` (по описанию владельца: `beckhoff.com/en-en/company/global-presence`, вкладки Germany / Beckhoff Worldwide) кодом 0.4.7.0; для лога MAIN-PC — `scripts\walk_timing.ps1 -Log <файл>`: те же таблицы по живому логу (лог до 0.4.8.0 даёт вызовы моделей по назначениям, время между страницами и доставку; фазы — только с 0.4.8.0). Цифры по MAIN-PC — после этого прогона.

## T4.2. Почему Germany, а не Worldwide → Finland

На странице Global presence открыта вкладка «Germany», вкладка «Beckhoff Worldwide» закрыта, стран выставки на странице нет. В 0.4.7.0 ни одно структурное правило не срабатывало: правило списка стран требует ≥ 3 стран среди элементов (видна одна — Germany), правило вкладок отделов исключает вкладки-страны и требует ≥ 2 вкладок (осталась одна). Решение уходило модели, а ей предлагались и «Germany», и ссылка `www.beckhoff.com/de-de`, и «Deutsch»; модель (14b) выбрала Germany. Замер 0.4.7.0 на фикстуре: `en-en/` → … → `en-en/company/global-presence/` → … → `de-de/` → `de-de/kontakt/`, 12 страниц, 0 финских людей, 22 вызова 14b (11 карточек + 11 шагов).

Правка (дополнение A2 к этому кейсу): закрытый элемент «Worldwide / Global presence / Weltweit …» раскрывается, пока страна выставки не названа на странице; пока seed не местная версия, элементы и ссылки другой страны (подпись `Germany` или путь `/de-de/`, не домен) модели не предлагаются; после того как достигнута `/fi-fi/`, не предлагаются и другие языковые версии (`/en-en/`); открытая вкладка-страна — раздел этой страны (офисы Germany уходят с `extra:country DE`, «Muut maat»). Замер 0.4.8.0: `en-en/` → `en-en/company/global-presence/` (Worldwide → Finland) → `fi-fi/` → `fi-fi/yhteystiedot/` → `fi-fi/tuotteet/` → `fi-fi/yritys/` → `fi-fi/yritys/johto/`, 7 страниц, 8 из 8 финских людей (2 — из JSON-LD без модели), офис FI с факсом, `/de-de/` не открыт.

## T4.3. Тайминг: где уходит время

Фазы на состояние страницы (журнал 0.4.8.0, контейнер, подменная модель — её время ≈ 1 мс, поэтому видна вся немодельная часть):

| Фаза | 0.4.7.0 (фикс. ожидание) | 0.4.8.0 |
|---|---|---|
| Загрузка (навигация / клик до готовности) | ≈ 1650 мс на состояние: 2 × 800 мс фиксированного ожидания + ≈ 50 мс | **456 мс** в среднем (37 состояний, 338–3672 мс; максимум — проверка «не бот» Ledvance 3 с) |
| Снимок, извлечение, привязка, запись (outbox) | ≤ 30 мс каждая | ≤ 30 мс каждая |
| Выбор шага без модели | — | ≤ 3 мс |
| Доставка (отдельный поток, обход её не ждёт) | — | 17–109 мс на компанию до стенда |

Без модели больше всего уходило на фиксированное ожидание готовности страницы (98–100 % измеренных фаз): оно заменено ожиданием «тихого» DOM (300 мс без изменений, не дольше 800 мс, один раз). На MAIN-PC к этому добавляется время модели: по числу вызовов оно сокращено так (одинаковые сайты-фикстуры, «до» — 0.4.7.0, «после» — 0.4.8.0):

| Компания | Страниц до → после | Людей до → после | Вызовы 14b до (карточки + шаги) | 14b после | 7b после | Время прогона в контейнере, с |
|---|---|---|---|---|---|---|
| Nordtec | 7 → 5 | 4 → 4 | 12 (6 + 6) | 2 | 1 | 12.2 → 2.4 |
| Vogel | 7 → 6 | 5 → 5 | 11 (5 + 6) | 3 | 2 | 13.1 → 3.1 |
| LEDVANCE | 8 → 8 | 6 → 6 | 16 (9 + 7) | 3 | 4 | 18.6 → 7.2 |
| Malux | 5 → 5 | 25 → 25 | 11 (7 + 4) | 5 | 2 | 13.9 → 3.6 |
| Beckhoff | 12 → 7 | 0 → 8 | 22 (11 + 11) | 1 | 2 | 20.4 → 3.9 |
| **Всего** | 39 → 31 | 40 → 48 | **72** | **14** | **11** | 78.2 → 20.2 |

Ожидаемая экономия на MAIN-PC = (72 − 14) × t(14b) − 11 × t(7b) на эти пять сайтов плюс ≈ 1.2 с на каждое состояние страницы; t(14b) и t(7b) даст `walk_timing.ps1` по живому логу (столбец `ms mean`).

## T4.4. Маршрутизация: доля решений на компанию (живой прогон панели, 0.4.8.0)

| Компания | Решений (шаги + чтение карточек) | Правила | 14b (`qwen2.5:14b-instruct`) | 7b (`qwen2.5:7b`) | VL | Кэш меню |
|---|---|---|---|---|---|---|
| Nordtec AB | 10 | 7 (70 %) | 2 (20 %) | 1 (10 %) | 0 | 0 |
| Vogel Antriebstechnik GmbH | 12 | 7 (58 %) | 3 (25 %) | 2 (17 %) | 0 | 0 |
| LEDVANCE Oy | 18 | 11 (61 %) | 3 (17 %) | 4 (22 %) | 0 | 0 |
| Malux Finland Oy | 16 | 9 (56 %) | 5 (31 %) | 2 (12 %) | 0 | 0 |
| Beckhoff Automation Oy | 18 | 15 (83 %) | 1 (6 %) | 2 (11 %) | 0 | 0 |

14b теперь зовётся только для карточек людей и только там, где они есть: Yhteystiedot / вкладки отделов Malux / страницы с личными адресами; домашние страницы, продукты, Global presence, Johto (JSON-LD) — без 14b. VL на фикстурах не понадобился (нет страниц без DOM-текста и проверок с одним признаком); работает в тестах (`test_vision_routing.py`). Кэш меню не сработал ни разу: после правил модель спрашивают редко, и набор ссылок к повтору уже другой — польза кэша на живых сайтах будет видна в отчёте тайминга, иначе убрать.

Предложения, не сделанные в этом шаге (с замером на MAIN-PC): параллельные вызовы 14b (карточки) и 7b (шаг) одной страницы при `OLLAMA_NUM_PARALLEL=3`; параллельная доставка — не нужна для скорости обхода (поток отдельный, фаза `record` ≤ 30 мс), только для скорости появления данных в ARGUS, если `... in N ms` до прода окажется большим.

## T4.5. Самопроверка

`pytest`: **566 passed**, 0 failed (было 531 в шаге 6); полный набор теперь идёт 4 мин 38 с вместо 8 мин 47 с (ожидание DOM). Гейты: 11 ok. Совпадений legacy 75 (57 + 18 строк `meta viewport` новой фикстуры), серия ≤ 2.

## T4.6. Живая проверка (контейнер, 05.10.2026, UTC)

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.0 (ei asennustietoa)` | 10:37 |
| 2 | Reititys | Модельный стенд со списком `qwen2.5:14b-instruct`, `qwen2.5:7b`, `qwen2.5-vl:7b` | Resurssit: `Reititys: säännöt ensin · navigointi qwen2.5:7b · kuvakaappaus qwen2.5-vl:7b` (зелёным) | 10:37:15 |
| 3 | Пакет | Ключ паринга → «Yhdistä», пакет Beckhoff + LEDVANCE + Malux + Nordtec + Vogel, «Käynnistä» | Все 5 `Valmis` за 22 с; Jono: Beckhoff 8 людей, 36 каналов, 9 источников; 0 отклонений | 10:37:28 → 10:37:50 |
| 4 | Beckhoff в ARGUS | `check_extra.py beckhoff` по стенду | Офис FI: `+358201233800`, `finland@beckhoff.example`, `extra` FI / название / адрес / факс; офис DE из вкладки Germany с `extra:country DE`; люди с отделами и FI; прямых country…fax — 0; источники без `/de-de/` | 10:38 |
| 5 | model.called | События `model.called` Beckhoff на стенде | `qwen2.5:14b-instruct` · `card_parsing` 1, `qwen2.5:7b` · `action_planning` 2 | 10:38 |
| 6 | Отчёт тайминга | `python -m argus_collector.pilot timing --log … --db …` | Таблицы T4.4 с названиями компаний; доставка 17–109 мс на компанию | 10:39 |

# Правка 1 шага 7: причина отказа доставки на экране — версия 0.4.8.1

**Дата:** 05.10.2026 · **Основание:** «Сборщик MAIN-PC не может доставить события…» и «Приоритет (владелец 05.10): два отказа без причины…» · **Ветка:** `stage-5/step-7-delivery-reasons`, ff в `main` · **Контракт:** не менялся.

## T5.1. Что проверено и что вне доступа сборщика

Пункты про сервер ARGUS — `/api/health`, journal `argus20-api` по `/api/collector/*`, правило Caddy для worker-методов (`render_caddy` после 0.4.24), `POST /api/collector/workers/heartbeat` с действующим токеном, ответ `POST /api/collector/batches` на «Lähetä Selaimeen» и тексты ошибок экрана ARGUS — у сборщика доступа нет (CLAUDE.md: «К `/opt/argus20`, серверу, базе и проду ARGUS у тебя доступа нет»; токен сборщика хранится только на MAIN-PC в DPAPI). Это работа сессии `gridex-argus20`. Со стороны сборщика сделано так, чтобы каждый отказ был виден на MAIN-PC с id и словами, а `request_id` из тела ошибки ARGUS связывал строку журнала сборщика с записью journal `argus20-api`.

## T5.2. Что значит «Lähetysvirhe 2» в панели сборщика

Это число элементов outbox (события + снимки), которым ARGUS **ответил отказом с кодом**: отказ по событию в ответе 200 на пакет или отказ всего запроса 4xx (кроме 401/403/409 lease/429). Ответ 5xx, 429, обрыв связи — не отказ: элемент остаётся `Odottaa lähetystä` и отправляется снова. Значит, «Lähetysvirhe 2» на MAIN-PC — ARGUS принял запросы и отклонил два элемента по коду, а не «сервер недоступен». Какие именно — покажет `scripts\delivery_check.ps1` на MAIN-PC: компания, event_id / evidence_id, seq, код, слова, плюс строки журнала с `request_id`.

Найдено в сборщике и исправлено:
1. Журнал писал только счётчик (`2 events sent, 1 accepted/duplicate, 1 rejected`): ни event_id, ни кода, ни компании — причину на MAIN-PC нельзя было найти без SQLite.
2. Запрос событий, отклонённый целиком (4xx), помечал первое событие `rejected`, но не засчитывал отказ компании: `Lähetysvirhe` рос, а у строки Jono причины не было.
3. Ответ 5xx на heartbeat показывался как `Ei verkkoa: HTTP 502: <html>…` («нет сети» и сырой HTML страницы прокси); 5xx на отправке был виден только как `Lähetetään`.
4. Подсказка Keruu ссылалась на кнопку «Testaa yhteys», которой с 0.4.7.0 нет.

## T5.3. Самопроверка

`pytest`: **576 passed**, 0 failed, 0 skipped (было 566 в 0.4.8.0; +10 новых). Гейты: 11 ok (version, no_cyrillic, size, docs, i18n, legacy — предупреждения как в 0.4.8.0, ruff, mypy, import_linter, pip_audit, gen_api_client).

## T5.4. Живая проверка (контейнер, 05.10.2026, время UTC)

Стенд: контракт-сервер `:8910`; перед ним испытательный прокси `:8911` (scratchpad, не в репозитории): по файлу режима пропускает запросы, переписывает 2-й результат пакета событий в `rejected <код>` или отвечает 502 с HTML-страницей. Панель спарена с прокси ключом `argus://pair?url=http://127.0.0.1:8911…`.

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.1 (ei asennustietoa)` | 15:26 |
| 2 | Паринг | Ключ → «Yhdistä» | `Yhdistetty`, `Viimeksi: 15:26:20`; журнал `http: heartbeat: HTTP 200 answered` | 15:26:19 |
| 3 | Отказ по событию | Режим `reject:evidence_hash_mismatch:2`, пакет Nordtec + Vogel + Malux, «Käynnistä» | Lähetys: `Lähetysvirhe: 2 (lainaus ei vastaa lähdettä)` красным; Jono: `Nordtec AB … Valmis · Hylätty 2: lainaus ei vastaa lähdettä`; журнал: `delivery: job b70d95aa… (Nordtec AB): contact.observed event 3b7729e6… seq 2 rejected evidence_hash_mismatch (the quote is not in the snapshot)` и такая же для seq 14 | 15:26:31 → 15:27:11 |
| 4 | Таблица отказов | `python -m argus_collector.pilot rejected --db …` | `# Rejected by ARGUS: 2`, две строки: время, Nordtec AB, job, `contact.observed`, event_id, seq 14 / 2, код, слова | 15:27 |
| 5 | 502 на heartbeat | Режим `502`, перезапуск панели | Yhteys: `Palvelinvirhe: 502` красным (до этой правки на том же стенде, 15:28: `Ei verkkoa: HTTP 502: <html><body><h1>502 Bad Gateway</h1></body></html>`); журнал `heartbeat: HTTP 502 http_502 (server error 502)` один раз, не каждые 30 с | 15:29:43 |
| 6 | 502 на отправке | Режим `pass`, пакет LEDVANCE, «Käynnistä», через 3 с режим `502` | Lähetys: `Odottaa lähetystä: 24 · Lähetysvirhe: 2 (lainaus ei vastaa lähdettä) · p95 (1 min): 2.2 s · Palvelinvirhe: 502` красным; журнал `delivery: job db83f20f…: HTTP 502 http_502 (server error 502)` с backoff 1–8 с | 15:30:39 → 15:30:53 |
| 7 | Восстановление | Режим `pass` | Через 3 с `transport syncing -> synced`, `Odottaa lähetystä: 0`, `Palvelinvirhe` исчез, Yhteys `Yhdistetty`, LEDVANCE `Valmis` 6 людей | 15:31:00 → 15:31:14 |
| 8 | claim при 502 | «Käynnistä», режим `502` на 22 с | `http: claim: HTTP 502 http_502 (server error 502)` каждые 10 с (было `claim: HTTP 502`) | 15:33:41 → 15:34:06 |

`scripts\delivery_check.ps1` в контейнере не запускался (нет PowerShell); его Python-часть — строка 4.

## T5.5. «Ei verkkoa» при Odottaa lähetystä 146 → 144 (вопрос владельца 05.10)

Журнал `/api/collector` — на сервере ARGUS, у сборщика доступа нет. По коду сборщика: поток доставки от heartbeat не зависит — при «Ei verkkoa» (heartbeat без ответа) он продолжает слать снимки и события каждые 0.5 с, с backoff только после собственной ошибки. Ничего не удаляется: число `Odottaa lähetystä` убывает только когда ARGUS ответил на элемент — принят / дубликат (уходит из счётчика) или отклонён с кодом (переходит в `Lähetysvirhe`). Значит, 146 → 144 при неизменном `Lähetysvirhe` — два элемента дошли до ARGUS и приняты, пока heartbeat не отвечал. У heartbeat, событий и снимков один адрес, один режим прокси и одинаковый таймаут 10 с, поэтому сеть MAIN-PC → ARGUS работает, а не отвечает за 10 с именно `POST /workers/heartbeat` — это проверяет сессия `gridex-argus20` (journal `argus20-api`, правило Caddy для worker-методов). Пока heartbeat не отвечает, аренды не продлеваются: по `lease_expires_at` сборщик перестанет начинать новые действия и сделает reconcile — это видно в журнале как `reconcile job …`. На MAIN-PC подтверждают строки журнала `delivery: job …: N events sent …` / `evidence … uploaded` в те же минуты, что `http: heartbeat: HTTP 0 offline` (команда — в сдаче).

## T5.6. Принятые решения (поправь, если не так)

1. Срочная правка доставки — 0.4.8.1; правка Ellego (извлечение до навигации, детектор цикла, параллельные вызовы моделей) идёт следующей версией 0.4.8.2, тоже в cv0.4.8.
2. Текст `detail` из ответа ARGUS в журнал не пишется (может содержать цитату с контактом); пишутся код, слова и `request_id`. На экране Yhteys `detail` показывается, как и раньше.
3. Название компании пишется в строку отказа журнала: это не значение контакта.

## T5.7. Расход

Подписка, ≈ 0.35 млн токенов основной сессии на правку 0.4.8.1 (счётчик сессии). Субагент фикстуры Ellego (относится к 0.4.8.2) — 169 тыс. токенов. Рантайм-модель — подмена, платных вызовов нет.

# Правка 2 шага 7: связь панели — версия 0.4.8.2

**Дата:** 05.10.2026 · **Основание:** «ок cv0.4.8.1 … Следующее — cv0.4.8.2: связь панели» и «В журнале 16:03:17 UTC четыре transport offline -> synced … Один цикл heartbeat, один переходник состояния транспорта» · **Ветка:** `stage-5/step-7-heartbeat`, ff в `main` · **Контракт:** не менялся. Ellego — 0.4.8.3 (черновик сохранён на `claude/laughing-wozniak-jbtvf4`, b95cc97).

## T6.1. Почему цикл не возобновлялся

Лог MAIN-PC за тот час в сессию не приходил; причина установлена по коду 0.4.8.1. Пути, на которых heartbeat останавливался навсегда:
1. Поток цикла ловил только ошибки HTTP (`ApiError`). Любое другое исключение внутри попытки завершало поток: чтение полей heartbeat и применение ответа идут в SQLite (`database is locked` после 30 с ожидания), применение аренд и команд вызывает `dispatch` → `finish_run`. После этого на экране оставались состояние прошлой попытки (`Ei verkkoa` от таймаута) и «Viimeksi», а перезапуска не было.
2. Ответ 401 останавливал цикл до нового ключа (решение 0.4.7.0).
3. Мёртвый поток цикла никто не проверял.

Правка: один поток часов (`ui/heartbeat_loop.py`) шлёт все heartbeat каждые 30 с от начала прошлой попытки при любом исходе; исключение попытки ловится, пишется в журнал и показывается (`Paneelin virhe: …`); панель раз в секунду проверяет часы и запускает их снова, если поток умер; попытка дольше таймаута + 5 с видна как `Hidas yhteys: N s`. Таймаут чтения heartbeat — 30 с.

## T6.2. Несколько циклов параллельно (вопрос владельца)

- Внутри одного процесса 0.4.8.1: heartbeat слали поток цикла и отдельный поток на каждое «Yhdistä» / старт панели — отсюда несколько heartbeat в одну секунду. Переход транспорта писали оба потока (heartbeat через `link()`, доставка через `tick()`) — до двух одинаковых строк на один переход.
- Четыре `transport offline -> synced` в одну секунду — больше, чем может дать один процесс (в процессе один поток доставки): значит, работали несколько процессов панели одновременно. Все потоки панели фоновые, закрытое окно завершает процесс; `install.ps1` панель не запускает, но меняет файлы под работающей старой — открытие панели ярлыком после установки при открытой старой даёт два процесса. Проверить на MAIN-PC — первая часть PowerShell в сдаче (список процессов панели).
- Теперь: одна панель на машину (`runtime/instance.py`, блокировка `state/panel-lock`, снимается ОС при завершении процесса, в том числе аварийном), один поток heartbeat, переход транспорта — одна строка (`Deliverer._note` под замком).

## T6.2а. Yhteys «Yhdistetty», Lähetys «Ei verkkoa», очередь убывает (третье сообщение владельца)

В 0.4.8.1 состояние Lähetys считалось из двух мест: heartbeat (`link`) и проход доставки (`tick`). Один запрос доставки без ответа за 10 с ставил всему транспорту `offline` до первого полностью успешного прохода — даже когда heartbeat проходил (`Yhdistetty`) и другие запросы того же прохода доставлялись (очередь убывала). Теперь одно состояние из одного источника (`delivery/transport.py`): `Ei verkkoa` — только когда heartbeat не получил никакого ответа и доставка тоже (последний её запрос без ответа или после падения heartbeat ни один запрос не получил ответа); запрос доставки без ответа при живом heartbeat — `Lähetetään` с повтором; ответ доставки при оборванном heartbeat — не `Ei verkkoa`. Таймаут heartbeat (`Hidas yhteys`) Lähetys не переводит в `Ei verkkoa`, поэтому `Ei verkkoa` в Lähetys бывает только вместе с `Ei verkkoa` в Yhteys. Каждый переход — одна строка журнала из одного места.

## T6.3. Самопроверка

`pytest`: **593 passed**, 0 failed, 0 skipped (было 576 в 0.4.8.1; +17). Гейты: 11 ok.

## T6.4. Живая проверка (контейнер, 05.10.2026, время UTC)

Стенд: контракт-сервер `:8920`, перед ним испытательный прокси `:8921` (scratchpad) с режимами `pass` / `slow:N` (heartbeat отвечает через N с) / `502`. Боевые значения: интервал 30 с, таймаут 30 с.

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.2 (ei asennustietoa)`; Yhteys `Ei yhteyttä`, «Yhdistä uudelleen» неактивна; журнал `http: panel started: pid 23424` | 16:12:29 |
| 2 | Пустое поле | «Yhdistä» без ключа | Ничего: нет строки `Paritusavain ei kelpaa`, состояние прежнее | ≈ 16:12:41 |
| 3 | Паринг | Ключ → «Yhdistä» | `Yhdistetty`, `Viimeksi: 16:12:44`, «Yhdistä uudelleen» активна; журнал `heartbeat: HTTP 200 answered`, один `transport offline -> synced` | 16:12:44 |
| 4 | Медленный ARGUS | Режим `slow:40` | Heartbeat 16:13:14 без ответа 30 с → `Hidas yhteys: 30 s` жёлтым, `Viimeksi: 16:12:44`; Lähetys остался `Lähetetty`; следующий heartbeat ушёл в 16:13:44 сам; журнал `heartbeat: no answer in 30 s (slow, not offline)` один раз | 16:12:55 → 16:13:57 |
| 5 | Возобновление | Режим `pass`, ничего не нажимал | Heartbeat 16:14:14 → `Yhdistetty`, затем `Viimeksi: 16:14:44` — часы идут | 16:14:05 → 16:14:55 |
| 6 | Yhdistä uudelleen | Нажал кнопку | Heartbeat сразу: `Viimeksi: 16:15:05` (время нажатия) | 16:15:05 |
| 7 | Вторая панель | Запустил вторую панель | Окно `ARGUS Selain on jo auki tällä koneella (prosessi 23424). Käytä avointa ikkunaa…`, после OK процесс завершился; журнал `panel not started: pid 23424 has the panel open`; первая панель работает | 16:15:08 |
| 8 | Доставка без ответа, heartbeat живой (A) | Второй стенд (`:8930`/`:8931`, сайт и модель), пакет Malux + LEDVANCE + Nordtec + Vogel, режим `dropdelivery` (запросы событий и снимков обрываются), «Käynnistä» | Yhteys `Yhdistetty`, `Viimeksi: 16:27:37`; Lähetys `Odottaa lähetystä: 142 · Lähetysvirhe: 0` и `Lähetetään` (в 0.4.8.1 здесь было `Ei verkkoa`) | 16:27:21 → 16:27:49 |
| 9 | Heartbeat без ответа, доставка проходит (B) | Режим `cuthb` (heartbeat обрывается без ответа) | 16:28:07 heartbeat без ответа: Yhteys `Ei verkkoa: HTTP 0: … Remote end closed connection without response`; Lähetys `Ei verkkoa`, пока доставка ждала повтора; 16:28:24 доставка прошла — Lähetys `Lähetetty`, очередь 142 → 0, Yhteys по-прежнему `Ei verkkoa`; журнал: одна строка на каждый переход | 16:27:58 → 16:28:58 |
| 10 | Оба без ответа (C) | Перезапуск панели (подключилась сама), пакет Beckhoff + Fixture Oy, «Käynnistä», через 4 с режим `cutall` | Yhteys `Ei verkkoa`, Lähetys `Odottaa lähetystä: 34` и `Ei verkkoa`; журнал `heartbeat: HTTP 0 offline …`, `transport syncing -> offline (heartbeat)` — по одной строке | 16:29:47 → 16:30:31 |
| 11 | Возврат | Режим `pass` | 16:31:02 доставка прошла — `transport offline -> synced`, очередь 0; 16:31:09 heartbeat — `Yhdistetty`, `Viimeksi: 16:31:09` | 16:30:40 → 16:31:20 |

502 (`Palvelinvirhe`), отказ соединения (`Ei verkkoa`), 401 с продолжением heartbeat, ошибка внутри панели и зависшая попытка проверены тестами `test_connection_clock.py` на том же стенде с короткими интервалами.

## T6.5. Принятые решения (поправь, если не так)

1. Heartbeat продолжается и после `Tunnus hylätty` (401): если токен снова разрешат, панель подключится сама.
2. Таймаут 30 с — у heartbeat; события, снимки, claim и reconcile — по-прежнему 10 с с повтором.
3. `Hidas yhteys` не переводит Lähetys в `Ei verkkoa` (`Ei verkkoa` в Lähetys только вместе с `Ei verkkoa` в Yhteys и без ответов доставки); «Käynnistä» по-прежнему требует `Yhdistetty`.
4. Вторая панель не запускается совсем, а показывает номер процесса открытой.

## T6.6. Расход

Подписка, ≈ 0.18 млн токенов основной сессии на правку 0.4.8.2 (счётчик сессии); субагентов не было. Рантайм-модель — подмена, платных вызовов нет.

# Правка 3 шага 7: тесты 0.4.8.2 на Windows — версия 0.4.8.3

**Дата:** 05.10.2026 · **Основание:** вывод `install.ps1` на MAIN-PC — 7 падений (`test_instance.py` ×2, `test_connection_clock.py` ×5), «STOP: tests failed - nothing installed» · **Ветка:** `stage-5/step-7-heartbeat-win`, ff в `main` · **Контракт:** не менялся.

## T7.1. Причины

| Тест | Причина | Правка |
|---|---|---|
| `test_connection_clock.py` (4 из 5) | Испытательный стенд `slow_argus.py` пересылал в контракт-сервер через `urllib.request.urlopen` — через системный прокси Windows (на MAIN-PC он есть); до 127.0.0.1 запросы не доходили. Остальные стенды репозитория ходят напрямую | Стенд ходит напрямую (`ProxyHandler({})`) |
| `test_no_answer_at_all_is_ei_verkkoa` | На Windows отказ соединения с закрытым портом localhost приходит примерно через 2 с; правило 0.4.8.2 «≥ 90 % таймаута — медленно» при тестовом таймауте 1 с называло отказ медленным | В панели: `Hidas yhteys` — только по `timed out` сокета; отказ — `Ei verkkoa` |
| `test_instance.py` (2) | На Windows байт, заблокированный `msvcrt.locking`, не читается другим дескриптором: номер процесса читался как `?` | Номер процесса — в отдельном `state/panel-pid`; блокировка снимается явно перед закрытием |

Воспроизведение в контейнере: недоступный прокси в окружении (`http_proxy=http://127.0.0.1:9`, `no_proxy` пуст) и стенд 0.4.8.2 — те же 4 падения `test_connection_clock.py`; исправленный стенд — 5 из 5.

## T7.2. Самопроверка

`pytest`: **594 passed**, 0 failed — прогнан с недоступным системным прокси в окружении, как на MAIN-PC (было 593; +1 тест правила таймаута). Гейты: 11 ok.

## T7.3. Живая проверка (контейнер, 05.10.2026, UTC)

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.3 (ei asennustietoa)`; журнал `panel started: pid 1478` | 17:03:41 |
| 2 | Отказ соединения | Ключ на закрытый порт `127.0.0.1:9` → «Yhdistä» | Yhteys `Ei verkkoa: HTTP 0: … Connection refused` (не `Hidas yhteys`); Lähetys `Ei verkkoa` | 17:03:49 |
| 3 | Вторая панель | Запустил вторую | Окно `ARGUS Selain on jo auki tällä koneella (prosessi 1478)…` — номер процесса первой панели (`state/panel-pid`); журнал `panel not started: pid 1478 has the panel open` | 17:03:53 |

Блокировка `msvcrt` в контейнере (Linux, `fcntl`) не проверяется; на MAIN-PC её проверяют `test_instance.py` при установке.

## T7.4. Решение (поправь, если не так)

0.4.8.2 уже в `main`, поэтому исправление — новая версия 0.4.8.3; Ellego — 0.4.8.4 (позже владелец: правка тестов — 0.4.8.4, Ellego — 0.4.8.5).

## T7.5. Расход

Подписка, ≈ 0.04 млн токенов основной сессии на правку 0.4.8.3 (счётчик сессии); субагентов не было.

# Правка 4 шага 7: два теста 0.4.8.3 на Windows — версия 0.4.8.4

**Дата:** 05.10.2026 · **Основание:** «Вернуть 0.4.8.3: на MAIN-PC install остановился, 2 падения … Правка — cv0.4.8.4, Ellego → 0.4.8.5» · **Ветка:** `stage-5/step-7-heartbeat-win2`, ff в `main` · **Контракт и поведение панели:** не менялись, правка в тестах.

## T8.1. Причины

| Тест | Что было на MAIN-PC | Причина | Правка |
|---|---|---|---|
| `test_instance.py::test_a_panel_process_holds_the_lock_and_its_end_frees_it` | `owner()` = 2952, `Popen.pid` = 32676 | `venv\Scripts\python.exe` на Windows — лаунчер; интерпретатор — его дочерний процесс, pid пишет он | Сравнение с pid, который сообщил сам державший процесс; завершается он (TerminateProcess), не лаунчер; ожидание освобождения до 10 с |
| `test_connection_clock.py::test_no_answer_at_all_is_ei_verkkoa` | За 10 с не наступило `Ei verkkoa` | Отказ 127.0.0.1:9 на Windows ≈ 2 с (повтор SYN после RST), таймаут стенда 1 с: каждая попытка истекала по таймауту — `Hidas yhteys` | Таймаут теста 10 с (в панели 30 с), ожидание до 30 с, печать фактического времени; при неудаче — состояние, секунды, текст ошибки |

Механизм второго падения воспроизведён в контейнере: порт, который рвёт соединение через 2 с без ответа, при таймауте 1 с — `slow 1 s`, при 10 с — `Ei verkkoa` через 2.0 с.

## T8.2. Самопроверка

`pytest`: **594 passed**, 0 failed — с недоступным системным прокси в окружении (число тестов не изменилось: правка внутри двух тестов). Гейты: 11 ok. **Не проверено на Windows:** `test_instance.py` (оба теста: `msvcrt` и лаунчер venv), время отказа в `test_no_answer_at_all_is_ei_verkkoa` — их проверяет `install.ps1` на MAIN-PC.

## T8.3. Живая проверка

Поведение панели не менялось (правка только в тестах); живая проверка 0.4.8.3 (T7.3) в силе, версия в панели — `cv0.4.8.4`.

## T8.4. Расход

Подписка, ≈ 0.03 млн токенов основной сессии на правку 0.4.8.4 (счётчик сессии); субагентов не было.

# Правка 5 шага 7: петля доставки `evidence_missing` — версия 0.4.8.5

**Дата:** 05.10.2026 · **Основание:** «Приоритет над Ellego, cv0.4.8.5. Петля доставки: ARGUS отклоняет contact.observed как evidence_missing (16 событий, 5 заданий…)» · **Ветка:** `stage-5/step-7-evidence-loop`, ff в `main` · **Контракт:** не менялся.

## T9.1. Почему петля была бесконечной

В 0.4.8.1–0.4.8.4 ответ `evidence_missing` оставлял событие в очереди: снимок снова ставился в загрузку, событие ждало его и уходило снова — без ограничения числа кругов. Если ARGUS снимок не находит и после повторной загрузки (ответ на загрузку `duplicate`, на событие — снова `evidence_missing`), круг повторяется вечно. ARGUS не засчитывает seq такого события, поэтому все следующие события задания получали `sequence_gap` и тоже ходили по кругу (в журнале — строка на каждое). Почему ARGUS на MAIN-PC не находит загруженный снимок — на стороне ARGUS; с 0.4.8.5 в журнале при каждом повторе видно, что ответил ARGUS на прошлую загрузку снимка (`was {…: 'duplicate'}`), — это строка для сессии `gridex-argus20`.

## T9.2. Что сделано

| Ситуация | Поведение 0.4.8.5 |
|---|---|
| `evidence_missing`, снимок хранится здесь | Снимок загружается снова, событие ждёт его и уходит снова; не более 3 повторов с этим кодом |
| 4-й отказ с тем же кодом | Событие отброшено: Jono `Hylätty N: todiste puuttuu`, Lähetys `Lähetysvirhe: N (todiste puuttuu)`, `pilot rejected` — его event_id; больше не отправляется |
| Снимка здесь нет (строка загрузки есть, файлов нет) | Отброшено сразу, без повторов |
| Seq отброшенного события ARGUS не засчитал | Seq занимает `source.blocked` без снимков (`status` `evidence_missing`, URL страницы, `detail` — какое событие и почему); остаток прогона и `job.finished` доходят |
| `sequence_gap` | Не считается (следствие); в журнале — одна строка на ответ: `N events from seq M wait for the seq before them` |
| Нет ответа, 5xx, 429 | Не отказ события: повтор с паузой, как раньше |

Тесты больше не пишут в рабочий журнал: строки тестовых заданий в журнале MAIN-PC во время `install.ps1` (например, 18:17:54–18:18:38 в выводе установки 0.4.8.4; вероятно, и «четыре `transport offline -> synced` в 16:03:17») — от тестов, не от панели. Прогон в контейнере с каталогом-приманкой вместо `%LOCALAPPDATA%`: до правки тесты писали туда журнал (переходы транспорта, `collecting on/off`, страницы и вызовы модели тестовых заданий; базу, паринг и токен — нет), после — ни одного файла.

## T9.3. Самопроверка

`pytest`: **598 passed**, 0 failed (было 594; +4) — прогон без `ARGUS_COLLECTOR_HOME` и с каталогом-приманкой вместо рабочего каталога данных: в него не записано ни одного файла. После прогона в `test_evidence_loop.py` подготовка очереди вынесена в помощник (гейт размера функции) — этот тест прогнан ещё раз: passed. Гейты: 11 ok.

## T9.4. Живая проверка (контейнер, 05.10.2026, UTC)

Стенд: контракт-сервер `:8940`, перед ним прокси `:8941`; режим `fakedup` — загрузка одного снимка получает ответ `duplicate`, но в контракт-сервер не попадает (как на MAIN-PC: снимок «есть», события «без снимка»).

| # | Строка | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.5`, `Yhdistetty` | 20:21 |
| 2 | Снимок не доходит до ARGUS | Пакет Nordtec AB, режим `fakedup`, «Käynnistä» | Журнал: два события страницы — `rejected evidence_missing … snapshot uploaded again first (was {…: 'duplicate'}), retry 1 of 3` … `retry 3 of 3`, затем `(Nordtec AB) … (evidence_missing after 3 retries) rejected evidence_missing`, `seq 2 carries source.blocked … instead of contact.observed …` | 20:21:42 → 20:21:48 |
| 3 | Панель | — | Jono `Nordtec AB … Valmis · Hylätty 2: todiste puuttuu`; Lähetys `Odottaa lähetystä: 0 · Lähetysvirhe: 2 (todiste puuttuu)` | 20:22:27 |
| 4 | Таблица отказов | `python -m argus_collector.pilot rejected` | 2 строки: Nordtec AB, `contact.observed`, event_id, seq 2 и 3, `evidence_missing` | 20:22 |
| 5 | Новый код журнала | Vogel, тот же режим | `sequence_gap` — одна строка на ответ (`19 events from seq 3 wait for the seq before them`); Vogel `Valmis · Hylätty 2: todiste puuttuu`, Lähetysvirhe 4, очередь 0 | 20:23:49 → 20:24:34 |
| 6 | ARGUS | Состояние контракт-сервера | Оба задания `completed`; принято 4 `source.blocked` `lost:<event_id>` со статусом `evidence_missing` и URL страницы | 20:25 |

## T9.5. Принятые решения (поправь, если не так)

1. Замена `source.blocked` на свободном seq: без неё отброшенное событие навсегда держало бы остаток прогона в `sequence_gap`, а лимит в 3 повтора отбросил бы и весь хвост, включая `job.finished`.
2. Лимит — только для отказов события, при которых оно остаётся в очереди (`evidence_missing`); `sequence_gap` и ошибки связи не считаются.
3. Каждое событие считает свои 3 повтора, даже если у нескольких событий один снимок (так буквально по правилу; лишние ~2 с на событие).
4. Изоляция тестов включена в эту правку.

## T9.6. Расход

Подписка, ≈ 0.09 млн токенов основной сессии на правку 0.4.8.5 (счётчик сессии); субагентов не было.

# Правка 6 шага 7: Ellego, петли, общий Chrome, правило цели, Reimax, p95 — версия 0.4.8.6

**Дата:** 06.10.2026 · **Основание:** «ок cv0.4.8.5. Дальше Ellego — cv0.4.8.6…» (Kontaktit, петли), «Дополнение к cv0.4.8.6: видимый Chrome не перезапускается на каждую компанию…», «Дополнение (владелец 06.10, 14:16, Reimax)», «Правило завершения обхода (владелец 06.10)», «Сдача 0.4.8.6 — тест-карта по пунктам» · **Ветка:** `stage-5/step-7-ellego`, ff в `main` · **Контракт:** не менялся (1.1).

## T10.1. Что было и что сделано

| Пункт | Было (0.4.8.5) | Стало (0.4.8.6) |
|---|---|---|
| Ellego | первая страница контактов: 9000+ символов мега-меню до первой карточки, модель получала первые 8000 символов, обход ходил по фильтрам по кругу | правила читают 40 из 40 до любого клика; модели нет; фильтры не нажимаются; ни одно состояние не повторяется |
| Петля WPML | `/contact-us/` ↔ `/fi/ota-yhteytta/`: ссылка оставалась «новой», 25 переходов на 2 страницы | ссылка, которая привела на другую страницу своих хостов, помечается пройденной; переход на прочитанную страницу запрещён; нажатая кнопка в том же состоянии больше не предлагается; 6 действий без нового состояния → `no_progress`; `walk.action_budget` 60 |
| Chrome | новый процесс на каждую компанию | один процесс на сбор, на компанию новый контекст (чистые cookies), закрывается контекст; старт — `chrome start=… ms` и колонки в `walk_timing` |
| Правило цели | обход шёл до бюджета, финиш запрещался при непосещённой сильной ссылке | итог перед каждым действием: продажи / маркетинг + прямой канал → completed; люди без этого → ≤ 2 доп. страницы; в панели «Tavoite saavutettu: N henkilöä, M kanavaa» |
| Reimax: правила нашли людей | модель всё равно вызывалась (каналы без карточки) | на такой странице модель не вызывается — ни для карточек, ни для шага |
| Reimax: шаблон почты | «firstname.lastname@…» — не распознавался (мог попасть каналом) | `email_pattern` компании с цитатой; каждому человеку страницы без адреса — адрес по шаблону, `inferred` (oletettu), цитата — строка шаблона |
| p95 (1 min) | считал события из очереди с их ожиданием (89984.8 s) | только события, поставленные и подтверждённые в эту минуту |

## T10.2. Почта по шаблону и строка в ARGUS

Вопрос владельца: сервер уже выводит oletettu по вычисленному шаблону — адрес с шаблоном с сайта должен попасть в ту же строку как источник с цитатой, не второй строкой.

**Что позволяет контракт 1.1.** Адрес по шаблону — наблюдение `email` человека: `extraction_status=ambiguous`, `binding=none`, `quote` — строка шаблона (span в снимке). Сервер выводит `inferred` по §9.4. Шаблон — поле `email_pattern` (не канал, без статуса) на сущности канала компании. Ту же строку в контракте делает `change_kind`:
- `reconfirmed` — то же значение у известного контакта: строка та же, к ней добавляется источник;
- `changed` + `supersedes_observation_id` — шаблон сайта вытесняет вычисленный адрес.

Сборщик выбирает `change_kind` по `ClaimedJob.known_contacts`. Проверено на контракт-сервере и вживую (T10.4): повторный прогон Reimax — у каждого из 14 человек одна строка почты, `inferred`, с `last_confirmed_at`; `email_pattern` — одна строка.

**Что нужно от сервера ARGUS** (сборщик сделать не может):
1. Отдавать вычисленный сервером адрес человека в `known_contacts[].fields.email` вместе с `observation_id` (форма `{value, observation_id}` сборщиком уже читается). Без этого сборщик не знает о вычисленном адресе, отправит `new`, и одну строку сервер должен собрать сам: тот же контакт, то же поле, то же значение.
2. При `email_pattern` компании, пришедшем со страницы сайта с цитатой, — пересчитать вычисленные адреса остальных людей компании по нему: шаблон с сайта приоритетнее вычисленного. Сборщик шаблонов не вычисляет, у него приоритет и так абсолютный.
3. `FinishedPayload.completion_reason` не имеет `goal_reached`: окончание по цели уходит `frontier_exhausted`, при этом `coverage.frontier_status=partial`, известные контакты — `not_checked`. Если ARGUS нужен отдельный код — перевыпуск контракта.

## T10.3. Самопроверка

`pytest`: **635 passed**, 0 failed (было 598; +37) — после последней правки кода прогнан целиком дважды. Гейты: 11 ok.

Что поймали тесты и живая проверка по ходу правки:
- **Продолжение после Huomio падало** (`test_collector_attention`): второй sync-Playwright в потоке сбора не запускается. Профиль рабочего браузера теперь открывает Playwright общего хоста.
- **`email_pattern` второй строкой при повторном прогоне** (живая проверка, 12:41). Шаблон теперь едет на канале компании; известный контакт-канал ищется и по каналу из ключа. После этого в контракт-тесте и вживую — одна строка.
- **Правило «ссылку, приведшую на новую страницу, не помечать — ломает gold»** проверено: временно включил пометку всегда и прогнал `walk` + `scheduler` — gold не меняется, упал только мой тест старого поведения. Принято правило владельца «независимо от редиректа».
- **Две ошибки чтения правилами**, найденные на `innerText` браузера:
  - «Vogel Drive Technology» принималось за имя и съедало следующее имя (Anna Schmidt);
  - строка подвала с каналом компании отменяла карточку Marja Hakala.

  После правки правила читают Ellego 40/40, Beckhoff 8/8, Reimax 14/14, Vogel 5/5, Nordtec 4/4, ложных людей нет.

**Не проверено на Windows** (контейнер Linux):
- установленный Chrome (`channel=chrome`) как один процесс на весь сбор через `chromium.launch`;
- закрытие Chrome при «Pysäytä» и при закрытии окна панели (в контейнере закрытие окна проверено тестом — без оконного менеджера окно не закрыть);
- `install.ps1` с новыми тестами.

## T10.4. Живая проверка (контейнер, 06.10.2026, UTC)

Стенд: контракт-сервер `:8950` с чистым состоянием, прокси сбоев `:8951`, тестовый сайт `:8765`, подмена модели `:11500`, панель под Xvfb с чистым каталогом данных и сохранённым паринком.

| # | Строка тест-карты | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 1 | Версия | Открыл панель | `cv0.4.8.6 (ei asennustietoa)`, Yhteys «Yhdistetty» | 12:49:05 |
| 2 | Ellego (0 повторов) | Пакет из 5 компаний (Fixture, Vogel, Beckhoff, Reimax, Ellego), «Käynnistä» | Ellego: `Valmis`, 40 henkilöä, 62 kanavaa, 2 страницы (`/`, `contact/`); 0 вызовов модели; в журнале ни одной строки петли / повтора, ни одна страница не входила дважды | 12:49:12 → 12:49:19 |
| 3 | Общий браузер (1 старт на сбор) | Тот же сбор, затем ещё 3 задания без перезапуска | Журнал: `chrome start=547 ms` у первой компании, `chrome start=0 ms shared=yes` у остальных семи; `walk_timing`: «Chrome: 1 start(s) for 8 job(s), 0.5 s». «Pysäytä» → `chrome closed: 1 starts, 547 ms`, процессов Chrome 11 → 2 | 12:49:12 → 12:52:13 |
| 4 | Правило завершения | — | Keruu: «Tavoite saavutettu: 40 henkilöä, 60 kanavaa»; все 8 заданий `completed (frontier_exhausted)`; весь пакет из 5 компаний — 8 с | 12:49:20 |
| 5 | Reimax | Тот же пакет, затем повторный прогон Reimax | Keruu: «Tavoite saavutettu: 14 henkilöä, 14 kanavaa», в таблице «oletettu: heidi.salonen@reimax.example» и т. д.; 0 вызовов модели. ARGUS (контракт-сервер): 14 человек, у каждого одна строка почты `inferred`, цитата «Our e-mail addresses are the following: firstname.lastname@reimax.example», телефоны `published_direct`, `email_pattern` — одна строка без статуса. После повторного прогона: те же строки, у всех `last_confirmed_at` | 12:49:18; 12:51:16 → 12:51:26 |
| 6 | p95 | Прокси режет события и снимки (heartbeat проходит), пакет Nordtec + LEDVANCE; 75 с; затем пропускает | 29 событий ждали в очереди; после доставки Lähetys: «Odottaa lähetystä: 0 · Lähetysvirhe: 0 · p95 (1 min): –»; по старому правилу было бы 79.5 s | 12:49:42 → 12:51:06 |

## T10.5. Принятые решения (поправь, если не так)

1. Прямой канал для правила цели — телефон или почта человека, напечатанные на сайте. Адрес по шаблону и общий номер — не прямой канал.
2. Роли продаж / маркетинга — по словам должности (sales, marketing, key account, export, area / country manager, myynti, markkinointi, vienti, vertrieb, försäljning / sälj, …).
3. «Не более 2 дополнительных страниц» действует и тогда, когда у людей есть каналы, но нет ролей продаж.
4. На странице, где правила нашли людей, структурные действия правил (вкладки, кнопки отделов) остаются; модель не вызывается.
5. Шаблон — к людям той же страницы; `email_pattern` — на сущности канала компании.
6. Правило цели выключается `walk.stop_at_goal: false`; тесты полного чтения по gold идут с выключенным.
7. Пометка «oletettu: » стоит перед адресом: в узкой колонке суффикс обрезался (живая проверка, 12:39).
8. Ссылка, приведшая на другую страницу своих хостов, помечается пройденной всегда (правило 06.10, gold не меняется).

## T10.6. Расход

Подписка, ≈ 0.7 млн токенов основной сессии (счётчик сессии с момента сжатия контекста; часть работы над Ellego до сжатия не посчитана); субагентов не было.
