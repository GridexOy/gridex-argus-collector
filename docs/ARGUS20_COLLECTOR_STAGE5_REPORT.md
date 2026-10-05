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
