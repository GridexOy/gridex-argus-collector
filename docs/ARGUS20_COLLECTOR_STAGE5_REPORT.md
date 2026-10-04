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
