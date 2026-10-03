# ARGUS20_COLLECTOR_CHANGELOG

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
