# ARGUS20_COLLECTOR_STAGE0_REPORT — этап S0, версия 0.0.1.0

**Дата:** 03.10.2026 · **Ветка:** `stage-0/step-1-diagnostics` · **Шаблон:** TZ_BLOCK0 §14 (без diff Caddyfile) · **Тест-карта:** TZ_SELAIN §13.1

## 1. Сделано

1. Панель `ARGUS Selain` (tkinter, одно окно, светлая тема, финский из `collector/messages/fi.json`): версия и дата внизу слева (`cv0.0.1.0 (<дата> klo <время>) <hash>` из `VERSION` + `build.json`), блок Yhteys со строкой `Yhteys: Ei yhteyttä`, блок Keruu с неактивными «Käynnistä» / «Keskeytä» / «Pysäytä» и двумя неактивными настройками автозапуска, блок Resurssit со строками из диагностики, кнопка «Avaa työselain» со строкой состояния, красный баннер при файле `STOP`.
2. `scripts/diagnose.ps1` (PowerShell 5.1): Windows, Chrome (реестр App Paths → известные пути, версия файла), NVIDIA (nvidia-smi, иначе Win32_VideoController), RAM, диск системного раздела, локальная модель (`<endpoint>/health`); каждая строка — состояние словами из `fi.json`; `-Json` — документ `argus-collector-diagnose/1`, который панель разбирает и сверяет с теми же правилами на Python (расхождение = ошибка на экране, не молчание).
3. `test_site/`: сервер на stdlib (`python -m test_site.server`, порт 8765 из `config.yaml`), фикстура `fixture_oy` (главная + контакты с тремя людьми + footer), gold `test_site/gold/fixture_oy.json`, тест сверяет gold с HTML.
4. Smoke-тест Playwright: `launch_persistent_context` с профилем `%LOCALAPPDATA%\Gridex\ArgusCollector\browser-profile` и `channel="chrome"` на Windows (вне Windows — встроенный Chromium, чтобы тесты шли в CI); кнопка панели запускает отдельный процесс `python -m argus_collector.browser --url … --serve-test-site 8765`, который поднимает тестовый сайт и держит видимое окно до закрытия.
5. `scripts/install.ps1`: только `main` с чистым деревом; Python 3.12 с tkinter; venv с закреплёнными зависимостями (`requirements.txt`, `requirements-dev.txt`, `pyproject.toml`); гейты и pytest **до** копирования; копия дерева в `%LOCALAPPDATA%\Gridex\ArgusCollector\app`; `build.json` (версия, коммит, дата); `config.yaml` из примера при первом запуске; ярлык «ARGUS Selain» на рабочем столе; `scripts/start.ps1` (`-Console` показывает ошибки Python).
6. Гейты §12.3: `scripts/run_gates.py` (+ `run_gates.ps1`, `check_*.ps1`): `version`, `no_cyrillic`, `size` (≤ 200 строк/файл, ≤ 40 строк/функция для .py и .ps1), `docs`, `i18n`, `legacy` (sha256 строк без пробелов ≥ 40 символов по `docs/legacy_line_hashes.txt`), `ruff`, `mypy --strict`, `import-linter` (слои `ui → browser|diagnostics → runtime`, вход только через `contract.py`), `pip-audit`.
7. Модули `runtime`, `diagnostics`, `browser`, `ui` — каждый с README, contract, service, repository, tests; реестр и changelog обновлены.

## 2. Принятые решения (поправь, если не так)

См. `ARGUS20_COLLECTOR_CHANGELOG.md` 0.0.1.0, пп.1–14. Ключевые: панель — tkinter (TZ §7); «Avaa työselain» в S0 стоит под блоком Resurssit, в Huomio появится с S3; подпись `Yhteys: Ei yhteyttä` по §5.1/тест-карте; профиль `browser-profile`; `playwright install` не нужен (установленный Chrome); состояние модели по `/health` + занятой видеопамяти; `fi.json` содержит только используемые ключи; Task Scheduler — S5; `check_i18n` на Python, а не `.mjs`.

## 3. Отклонения от ТЗ

1. `check_i18n` реализован на Python (`scripts/gates/check_i18n.py`), а не как `check_i18n.mjs` (§11): Node на MAIN-PC не требуется.
2. Гейт «регенерация клиента (`git diff` пуст)» не подключён — клиента нет до S1; `run_gates.py` говорит об этом в docstring.
3. Task Scheduler (§12.1 п.2) не настраивается в S0; настройка показана неактивной.
4. Блок Yhteys в S0 — только состояние; адрес ARGUS, «Testaa yhteys», worker_id, heartbeat — S1 (кнопка без работы не показывается, правило №5).
5. Содержимое тестового сайта в S0 на английском; финские подписи — в фикстурах S2.

## 4. Самопроверка (Linux-контейнер, Python 3.12.3, Xvfb, Chromium 141 из Playwright 1.56.0)

- **pytest:** 61 passed (runtime 25, diagnostics 11, browser 7 — включая headless smoke против тестового сайта и CLI-лаунчер, ui 6 — включая реальное окно под Xvfb, test_site 3, гейты 9).
- **Гейты (`scripts/run_gates.py`):** 10 ok, 0 failed. `legacy` — 7 одиночных предупреждений на типовые строки (`from __future__`-подобные: `except (OSError, subprocess.TimeoutExpired) as exc:`, `<meta name="viewport" …>`, `json.loads(path.read_text(encoding="utf-8"))`, `sys.path.insert(0, …)`), ни одной серии из трёх; проверено вручную — копирования нет.
- **Панель живьём под Xvfb** (скрипт вне репо, `xvfb-run`): `cv0.0.1.0 (ei asennustietoa)`; `Yhteys: Ei yhteyttä`; start/pause/stop = disabled, open_browser = enabled; Resurssit: `Käyttöjärjestelmä: Linux …`, `Chrome: ei käytettävissä`, `Malli: ei ladattu`, `Levy /: 29.4 GB vapaana, 88 % käytössä`, `Levytila alle 15 %`, `Muisti: 15.1 / 15.7 GB vapaana`, `NVIDIA: ei ajuria`; клик «Avaa työselain» → `Avataan työselainta…` → `Työselain avattu: http://127.0.0.1:8765/` через 6,2 с, процесс-лаунчер жив, профиль `browser-profile/` создан (BrowserMetrics, Default, …).
- **Что здесь выполнить нельзя:** `.ps1` (нет PowerShell) — проверены чтением на синтаксис PS 5.1 (без `&&`, без тернарных операторов, без `??`); ветка `diagnostics.collect()` через PowerShell; `channel="chrome"`; ярлык, robocopy, DPAPI не нужен в S0.

## 5. Живая проверка тест-карты §13.1 на MAIN-PC

**Не пройдено, требует MAIN-PC** (Windows, NVIDIA, настоящий Chrome). Разработка шла в Linux-контейнере без PowerShell; версия в панели с датой установки и коммитом появится только после `install.ps1`. Сдача этапа без этой проверки неполная — ниже команды, которыми владелец (или сессия на MAIN-PC) проходит карту.

Установка из `main` (после ff-merge ветки):
```
& {
  Set-Location 'C:\dev\gridex-argus-collector' -ErrorAction Stop
  git checkout main; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: checkout main'; return }
  git status --porcelain | ForEach-Object { Write-Host "STOP: dirty tree: $_" }
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: install.ps1 failed'; return }
  Get-Content (Join-Path $env:LOCALAPPDATA 'Gridex\ArgusCollector\build.json')
}
```

| # | Что сделать | Команда / действие | Что должно быть |
|---|---|---|---|
| 1 | Открыть панель | ярлык «ARGUS Selain» или `powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\gridex-argus-collector\scripts\start.ps1 -Console` | внизу слева `cv0.0.1.0 (<сегодня> klo <время>) <hash>` — хэш совпадает с `git rev-parse --short HEAD`; `Yhteys: Ei yhteyttä`; «Käynnistä» / «Keskeytä» / «Pysäytä» серые; Resurssit без «unknown» |
| 2 | Запустить диагностику | `powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\gridex-argus-collector\scripts\diagnose.ps1` и то же с `-Json` | строки `Käyttöjärjestelmä`, `Chrome: käytettävissä (<версия>)`, `NVIDIA: NVIDIA GeForce RTX 4090, ajuri <версия>`, `GPU-muisti`, `Muisti`, `Levy C:`, `Malli: ei ladattu (http://127.0.0.1:8080: no answer …)`; `-Json` — документ со `"schema": "argus-collector-diagnose/1"` |
| 3 | Нажать «Avaa työselain» | кнопка под Resurssit | в панели `Avataan työselainta…` → `Työselain avattu: http://127.0.0.1:8765/`; открылось отдельное окно Chrome (не личный профиль, папка `%LOCALAPPDATA%\Gridex\ArgusCollector\browser-profile`) со страницей «Fixture Oy - Industrial fasteners»; после закрытия окна — `Työselain suljettu` |

Дополнительно: создать файл `STOP` в `C:\dev\gridex-argus-collector` и перезапустить панель — красный баннер `STOP-tiedosto löytyi, keruu estetty: …`; удалить файл.

## 6. Версия

`VERSION` = `0.0.1.0`, `pyproject.toml` = `0.0.1.0`; тег `cv0.0.1` ставит основная сессия при мерже в `main`. `build.json` и строка в панели с датой — после `install.ps1` на MAIN-PC.

## 7. Расход

Сессия Claude Code (Исполнитель-2, одна модель, без субагентов); платных вызовов рантайма нет (`model_call` пуст: модели в S0 нет). Токены и € — в сдаче основной сессии.

## 8. Вопросы Архивариусу

Нет: внешние сервисы в S0 не используются.
