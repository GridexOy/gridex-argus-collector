# ARGUS20_COLLECTOR_STAGE4_REPORT — этап S4 (M2, решение владельца 03.10.2026), версия 0.4.2.0

**Дата:** 03.10.2026 (шаг 1), 04.10.2026 (шаг 2) · **Ветка:** `stage-0/step-1-diagnostics` (решение владельца меняет порядок этапов; git — основная сессия) · **Шаблон:** TZ_BLOCK0 §14 · **Тест-карта:** шаг 1 — ближе всего TZ_SELAIN §13.1 + §13.5 (М2), обе написаны под другой набор функций, см. §3; шаг 2 — `ARGUS20_TZ_TANDEM.md` §5 (тест-карта пары 1), см. §9.

## 1. Сделано

Фактическая сдача объединяет три коммита в `main` (`92de0cc`, `7c83f91` — уже были; `90166b4`, `de5e04e`, `34162e7`, `84621f1` — эта сессия, живая проверка на MAIN-PC) и доводит их до полностью рабочего состояния на реальном железе:

1. **Panel `ARGUS Selain`** открывает реальное окно на MAIN-PC: поле «Yrityksen verkkosivu», «Käynnistä» (активна при `Malli ≠ ei ladattu`, Chrome доступен, нет STOP), «Pysäytä», строка состояния с шагами обхода, «Löydetty: N yhteystietoa», таблица Nimi · Titteli · Puhelin · Sähköposti · Lähde, двойной клик открывает источник в браузере. Resurssit перечитываются после каждого обхода.
2. **`qwen2.5:14b-instruct` на RTX 4090 через Ollama**, `scripts/install_model.ps1` пройден на MAIN-PC целиком: `nvidia-smi` → Ollama уже стоял → `ollama pull` (9.0 GB) → `OLLAMA_CONTEXT_LENGTH=16384` → тестовый вызов → `ollama ps` = `100% GPU`. `Malli: paikallinen (GPU)` в панели подтверждён живьём (скриншот приложен в чат).
3. **Обход (`walk`)** — страница → снимок (evidence) → детерминированные каналы → карточки модели (verbatim-проверка) → действие модели (navigate/click/scroll/finish) — пройден живьём против тестового сайта и шести реальных сайтов (см. §5).
4. **Три живые правки по итогам первого прогона на MAIN-PC** (подробности и обоснование — `ARGUS20_COLLECTOR_CHANGELOG.md` 0.4.1.1–0.4.1.3):
   - `fix-1` (`90166b4`): карточка без телефона и без почты больше не записывается и не показывается (на `ensto.com/.../owners-board-management/` раньше давало 10 пустых строк); строка ОС в Resurssit была нечитаемой кракозяброй на этой (русской) локали Windows — `run_powershell_diagnose` теперь декодирует stdout `diagnose.ps1` как UTF-8 явно.
   - `fix-2` (`de5e04e`): один неудачный клик (таймаут 10 с, перекрытый элемент — типично баннер cookie, он по-прежнему вне этого шага) больше не роняет весь обход в `Keruuvirhe`; `walk/runner.py` ловит новый `browser.ActionError` вокруг одного действия и завершает обход как обычно, с тем что уже нашли.
   - `fix-3` (`84621f1`): `install.ps1` падал на собственном pytest примерно в половине прогонов на MAIN-PC — гонка Windows/Tcl при создании второго `tk.Tk()` в процессе вскоре после `destroy()` первого (воспроизводится только в тестах; панель создаёт один `Tk()` за процесс). Добавлен короткий повтор `make_tk_root()`.
5. **Документация**: `ARGUS20_COLLECTOR_CHANGELOG.md` (0.4.1.1–0.4.1.3), `ARGUS20_COLLECTOR_MODULES.md` (`browser`, `walk`, `diagnostics`) обновлены в соответствующих коммитах.

## 2. Принятые решения (поправь, если не так)

1. Реальные сайты для живой проверки — помимо названных владельцем примеров (`ensto.com`, `abb.fi`, `phoenixcontact.fi`) добавлены `sarlin.com` и `junttan.com`: у всех трёх названных сайтов (крупные промышленные группы) личные страницы руководства не публикуют телефон/почту напрямую — результат `0 yhteystietoa`, но корректный, без ошибки (см. `fix-2`). Для живого показа «находит людей с каналами связи» нужны были сайты, которые публикуют прямые контакты сотрудников; выбраны два реальных финских промышленных поставщика с открытой страницей «Yhteystiedot»/«Contacts».
2. Тест `test_window_renders_keruu_block_and_live_rows` был жёстко завязан на текущий номер версии (`"cv0.4.1.0 ("`) — ломался при каждом поднятии `VERSION`; переписан на сравнение с `runtime.current_version_status().file_version`.
3. `walk/tests/test_walk.py` вышел за 200 строк (гейт `size`) после добавления нового теста устойчивости — общие фикстуры вынесены в `walk/tests/conftest.py`, тест на `ActionError` — в отдельный `walk/tests/test_walk_resilience.py`.
4. Гонка `tk.Tk()` (`fix-3`) — не трогал рантайм панели (`ui/contract.py` создаёт ровно один `Tk()` за процесс, там не воспроизводится); чинить затронутые тесты коротким повтором, а не переделывать порядок/изоляцию тестов — решение в пользу маленькой правки.
5. Контакт без обоих каналов (`fix-1`) — не записывается и не отправляется в панель вовсе (а не помечается как «неполный»): он всё равно будет пойман повторно, если тот же URL с другим текстом (после клика) откроет канал; если нет — в нём для ARGUS пользы нет (`VISION.md` §5: «люди с каналами связи»).

## 3. Отклонения от тест-карты ТЗ

TZ_SELAIN §13.1 и §13.5 писались под другой набор функций этого этапа (§13.1 — до панели вообще; §13.5 подразумевает контракт-сервер, PDF/OCR, каталог — S1–S3, которых по решению владельца 03.10.2026 ещё нет). Для этого шага («Keruu по одному URL с панели») собственная тест-карта:

| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Открыть панель | Внизу слева `cv0.4.1.3 (<дата> klo <время>) <hash>`; Resurssit без «unknown» и без кракозябр |
| 2 | `diagnose.ps1` / `-Json` | `Chrome: käytettävissä`, `Malli: paikallinen (GPU)`, строки GPU/диск/память |
| 3 | Обход тестового сайта | Ровно 7 карточек из gold, у каждой оба канала, «Keruu valmis: 5 sivua, 7 yhteystietoa» |
| 4 | Обход минимум 3 реальных сайтов | Контакты (если есть на сайте) — с телефоном/почтой и ссылкой-источником; если на сайте личных каналов нет — чистое «Keruu valmis», не ошибка |
| 5 | STOP / «Pysäytä» | Останавливает обход между шагами |

## 4. Гейты и тесты (MAIN-PC)

`scripts\run_gates.py`: **10 ok, 0 failed** (`legacy` — только предупреждения, без серии из трёх). `pytest -q`: **зелёный**, 3 прогона подряд после `fix-3` (до него — флейк `test_panel_drives_a_real_walk_with_the_fake_model` примерно в половине прогонов, см. `fix-3`).

## 5. Живая проверка на MAIN-PC (Windows 11, RTX 4090, настоящий Chrome 154, видимое окно)

Выполнено через `scripts/install.ps1` → панель `python -m argus_collector.ui` → поле URL → «Käynnistä», ровно тот код, что получает владелец. Таблица — из реального `%LOCALAPPDATA%\Gridex\ArgusCollector\state\collector.db` (все строки `runs.result = 'completed'`), каждый контакт сверен с `evidence_manifest`/файлом снимка.

| # | Шаг | Сделал | Увидел | Время |
|---|---|---|---|---|
| 1 | Версия/дата в панели | Открыл установленный `ARGUS Selain` (сначала `cv0.4.1.2`, после fix-3 — переустановка и перезапуск через настоящий `scripts\start.ps1`) | `cv0.4.1.2 (3.10.2026 klo 22.54) de5e04e` и финально `cv0.4.1.3 (3.10.2026 klo 23.13) 84621f1` — оба скриншота отправлены в чат; хэш совпадает с `git rev-parse --short HEAD` на `main` | 22:54, 23:13 |
| 2 | Resurssit | `diagnose.ps1` и панель | `Chrome: käytettävissä (154.0.8037.58)`; `Malli: paikallinen (GPU)`, `Malli qwen2.5:14b-instruct @ http://127.0.0.1:11434/v1: model listed`; `NVIDIA: NVIDIA GeForce RTX 4090, ajuri 616.56`; `Käyttöjärjestelmä: Майкрософт Windows 11 Pro для рабочих станций` — кириллица читается (fix-1) | 22:54 |
| 3 | Обход тестового сайта | URL `http://127.0.0.1:8765/` → «Käynnistä» | `Keruu valmis: 5 sivua, 7 yhteystietoa`; все 7 имён/должностей/телефонов/почт совпадают с `test_site/gold/fixture_oy.json` дословно, 0 дублей, 0 карточек-призраков | 19:55, elapsed 18.1 с |
| 4 | Обход `ensto.com` | `https://www.ensto.com/` → «Käynnistä» | 7 страниц, совет директоров/руководство без личных телефонов/почты на странице → `Keruu valmis: 7 sivua, 0 yhteystietoa` (до fix-1/fix-2: 10 пустых карточек, затем `Keruuvirhe` на клике) | 20:00, elapsed 34.9 с |
| 5 | Обход `abb.fi` | `https://www.abb.fi/` → «Käynnistä» | 4 страницы, `Keruu valmis: 4 sivua, 0 yhteystietoa` (без ошибки) | 19:56, elapsed 28.3 с |
| 6 | Обход `phoenixcontact.fi` | `https://www.phoenixcontact.fi/` → «Käynnistä» | 1 страница, не нашла одобренных кандидатов → чистое `Keruu valmis: 1 sivua, 0 yhteystietoa` | 19:56, elapsed 3.0 с |
| 7 | Обход `sarlin.com` | `https://www.sarlin.com/` → «Käynnistä» | `Keruu valmis: 15 sivua, 5 yhteystietoa`: Eija Halonen (Laatupäällikkö, +358105504210, eija.halonen@sarlin.com), Saana Mäntylä (Talousjohtaja), Tanja Valtonen (Tuotelinjajohtaja), Jiri Viholainen (Toimitusjohtaja), Mikko Ylilammi (Head of Product Management) — у всех телефон+почта+ссылка-источник; двойной клик открывает `sarlin.com/ota-yhteytta?...` в браузере | 19:56 и 20:01 (повтор), elapsed ≈104 с |
| 8 | Обход `junttan.com` | `https://junttan.com/` → «Käynnistä» | `Keruu valmis: 15 sivua, 3 yhteystietoa`: Jaana Strandman (Export Specialist, +358468505881), Ate Konkka (Sales and Rental, +358505781154), Mani Islander (Service coordinator, email без телефона) — источник `junttan.com/contact-us/` и `junttan.com/scandinavia/contacts/` | 19:58, elapsed 57.5 с |
| 9 | Проверка доказательства | `SELECT` по `observations`/`evidence_manifest` для Eija Halonen | `fields_json` с `start`/`end`; байты `evidence/82/82…ea47.txt[2382:2394]` = `"Eija Halonen"`, `[2410:2422]` = `"010 550 4210"`, `[2423:2446]` = `"eija.halonen@sarlin.com"` — дословное совпадение | — |
| 10 | `model_calls` | `SELECT COUNT(*), SUM(cost_eur) ...` | 202 вызова за сессию, `SUM(cost_eur) = 0.0` (локальная модель) | — |

**Не пройдено явно (вне этого шага):** STOP/«Pysäytä» между шагами — проверено только автотестами (`test_walk_stops_on_request_and_on_stop_file`), не отдельным живым кликом (при переносе внимания на правки fix-1…fix-3 посчитано избыточным: логика не менялась). Cookie-баннеры/модальные окна — осознанно вне этого шага (решение №8 к 0.4.1.0, перенесено в S3).

## 6. Версия

`VERSION` = `pyproject.toml` = `0.4.1.3`. Коммиты в `main`: `90166b4` (fix-1), `de5e04e` (fix-2), `34162e7` (docs), `84621f1` (fix-3). Тег `cv0.4.1` — основная сессия ставит при согласии владельца (первая `.0` этого шага была `92de0cc`, до начала этой живой проверки).

## 7. Расход

Сессия Claude Code (Исполнитель-2); один субагент `Explore` (обзор кода `install_model.ps1`/`diagnose.ps1`/панели/`walk` перед живой проверкой, ~100К токенов). Рантайм-модель — локальная `qwen2.5:14b-instruct` на RTX 4090 через Ollama: 202 вызова за сессию, `cost_eur = 0` у каждого (проверено в `model_calls`). Токены и € самой Claude Code сессии — в биллинге владельца.

## 8. Вопросы Архивариусу

Нет: внешние сервисы (кроме Ollama/локальной модели — факты уже в `ARGUS20_ASSETS.md`/changelog 0.4.1.0) в этом шаге не используются.

---

## 9. Шаг 2 — A1 «Связь» (`ARGUS20_TZ_TANDEM.md`, пара 1), версия 0.4.2.0

**Дата:** 04.10.2026. Владелец дал «ок» на `ARGUS20_TZ_TANDEM.md` и явно на старт A1 в чате 04.10.2026.

### 9.1. Сделано
Подробно — `ARGUS20_COLLECTOR_CHANGELOG.md` 0.4.2.0. Коротко: блок Yhteys панели подключён к реальному сетевому стеку — поля адреса/worker_id/токена, «Testaa yhteys» → один heartbeat через новый `api_client` (сгенерирован из `docs/ARGUS20_COLLECTOR_OPENAPI.json`, манифест операций — пока только `heartbeat`), токен и адрес сохраняются через новый `worker_auth` (DPAPI), автоматический heartbeat раз в 30 с при открытой панели. Новый `contract_server/` — опорный тестовый сервер на loopback, пока прод `/api/collector` не готов (B1 строит его параллельно). Ручной режим подписан «Paikallinen testi — ei lähetetä ARGUSiin».

### 9.2. Живая проверка на MAIN-PC
Через `install.ps1` → переустановленная панель (`python -m argus_collector.ui`, не заглушка) → отдельно поднятый `python -m contract_server.server --port 8900` с токеном `test-token-abc` → `worker-main-pc`.

| # | ТЗ_TANDEM §5 | Что сделал | Что увидел | Время |
|---|---|---|---|---|
| 2 | Ввести токен → «Testaa yhteys» | Через панель (`app.connection.test_connection`) с верным токеном | `Yhdistetty` (зелёным), `Viimeksi: 08:07:28`; тот же процесс позже сам обновил время (`08:08:59`) — автоматический heartbeat раз в 30 с подтверждён живьём | 08:07–08:09 |
| 5 | Неверный токен → «Testaa yhteys» | То же с `not-a-real-token` | `Tunnus hylätty` красным; `worker_token.bin` не создан/не перезаписан (сохранённый верный токен остался) | 08:07 |
| — | Хранение | `Get-Content worker_connection.json` | `{"base_url": "http://127.0.0.1:8900", "worker_id": "worker-main-pc"}` — адрес и worker_id открытым текстом (не секрет) | — |
| — | Хранение | `(Get-Item worker_token.bin).Length` | 230 байт шифротекста DPAPI (исходный токен — 14 символов; не читается как текст) | — |
| — | Версия в панели | Скриншот окна (`PrintWindow`, без риска захватить чужое окно поверх) | `cv0.4.2.0 (4.10.2026 klo 11.06) cebcdbd` — хэш совпадает с `git rev-parse --short HEAD` на `main` | 11:06 |

Пункты 1, 3, 4 тест-карты пары 1 — сторона ARGUS (Soittolista, шапка `Selain: …`) и требуют сессию ARGUS (шаг B1), которой ещё нет на проде; будут пройдены по факту готовности B1, токен внесёт владелец.

### 9.3. Решения (поправь, если не так)
См. `ARGUS20_COLLECTOR_CHANGELOG.md` 0.4.2.0, блок «Решения», пп.1–4.

### 9.4. Версия
`VERSION` = `pyproject.toml` = `0.4.2.0`. Коммит в `main`: `cebcdbd` (`stage-4 step-2`). Тег `cv0.4.2` — основная сессия ставит при согласии владельца.

### 9.5. Расход
Сессия Claude Code (Исполнитель-2); два субагента `general-purpose` параллельно (генератор `api_client` из OpenAPI; `contract_server/`) — оба работали в фоне, ядро работы (`worker_auth`, блок Yhteys, проводка, три найденных попутно бага, живая проверка) сделано основной сессией. Платных вызовов рантайма нет: `contract_server/` и `api_client` — локальный HTTP на loopback, без внешних сервисов и без модели. Токены и € самой Claude Code сессии (основной и субагентов) — в биллинге владельца.

### 9.6. Вопросы Архивариусу
Нет: `contract_server/` — временный тестовый стенд этого репозитория (не внешний сервис), реальный адрес/токен ARGUS ещё не существует и будет внесён владельцем после готовности B1.
