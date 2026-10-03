# ARGUS20_COLLECTOR_CHANGELOG

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
