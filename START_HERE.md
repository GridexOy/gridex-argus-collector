# START HERE — сборщик Selain (gridex-argus-collector)

Комплект для отдельной сессии разработчика Windows-сборщика. Собран 03.10.2026 из `GridexOy/gridex-argus20`, ветка `main`, коммит `196d2ba2a0185535ee499f8bcae3ac677ef51999` (ARGUS 0.4.7.0). Опись, контрольные суммы и проверки — `docs/KIT_MANIFEST.md`.

## 1. Назначение
ARGUS 2.0 по названию выставки выдаёт продавцу компании-экспоненты и людей с каналами связи. Selain — локальный сборщик на Windows MAIN-PC (RTX 4090). Он берёт у ARGUS пакет компаний (по умолчанию 8) и проходит их собственные сайты: сначала кодом (HTTP), затем локальным Chrome — клики, поиск, фильтры, раскрытие карточек, пагинация. Каждый найденный контакт он отправляет в ARGUS потоком, с доказательством: снимок + locator + quote + URL. Это лестница И7 (RULES K1) с действиями в браузере. Серверный fetcher ARGUS остаётся резервом.

## 2. Порядок чтения
| # | Документ | Что взять |
|---|---|---|
| 1 | `CLAUDE.md` (или `AGENTS.md`) | правила репозитория, цикл, шаблон сдачи |
| 2 | `docs/ARGUS20_VISION.md` | что строим; п.5 «Люди» |
| 3 | `docs/ARGUS20_WAYS_OF_WORKING.md` | роль «Исполнитель-2» (§1), цикл (§2), kill switch (§8), потолки (§9) |
| 4 | `docs/ARGUS20_RULES.md` | правила данных: R2, R3, R7, R8, E1–E3, E6, K1, K3–K5, K7–K9 |
| 5 | `docs/ARGUS20_TZ_SELAIN.md` v3.0 | ТЗ целиком; для S0 — §2, §3, §5.1, §11, §12.1–12.3, §13.1, §14, §15 |
| 6 | `docs/ARGUS20_COLLECTOR_OPENAPI.json` 3.0.0 | контракт (wire schema 1.1); нужен с S1 |
| 7 | `docs/ARGUS20_TZ_BLOCK0.md` | §2.1 цикл шага, §3 правила №1–№4, §9 формат ошибки, §14 шаблон отчёта |
| 8 | `docs/ARGUS20_ASSETS.md` | единственный источник фактов о внешних сервисах |
| 9 | `docs/ARGUS20_DONE_AND_NON_GOALS.md`, `ARCHITECTURE.md`, `SCREENS.md`, `BLOCKS.md` | контекст ARGUS: чего не делаем, хозяева таблиц, экраны блока 6, дорожка S0–S6 |

## 3. Границы ответственности
| Кто | Отвечает за | Не делает |
|---|---|---|
| Исполнитель-2 (эта сессия) | репозиторий `gridex-argus-collector`: сборщик, панель, `contract_server/`, `test_site/`, скрипты установки, контрактные тесты (§12.4), документы сборщика | не имеет доступа к `/opt/argus20`, серверу, БД и проду; не правит ТЗ, OpenAPI и документы ARGUS; не включает платные сервисы без «ок» |
| Исполнитель ARGUS (основная сессия) | серверный модуль `collector` в блоке 6 по тому же OpenAPI | не пишет код сборщика |
| Владелец (Игорь) | «ок» по этапам S0–S6, токен в панели, решения §15 ТЗ, перевыпуск ТЗ/OpenAPI | — |

Единственная связь сборщика с ARGUS — `docs/ARGUS20_COLLECTOR_OPENAPI.json`. Контракт меняется только перевыпуском ТЗ и OpenAPI одной правкой.

## 4. Первое задание — этап S0 (версия 0.0.1.0)
Ветка `stage-0/step-1-diagnostics` от `main`; тег `stage-0-start` уже стоит на стартовом коммите.

Что должно появиться (TZ_SELAIN §2.3, §5.1, §12.1, §13.1):
- `scripts/diagnose.ps1` — Windows, Chrome, драйвер NVIDIA, RAM/диск/GPU, доступность модели; состояния словами, без «unknown»;
- `test_site/` — тестовый сайт поднимается локально;
- smoke-test Playwright открывает тестовый сайт в постоянном профиле Chrome;
- панель (финский, `collector/messages/fi.json`): версия и дата внизу слева, `Yhteys: Ei yhteyttä`, все кнопки сбора неактивны;
- кнопка «Avaa työselain» открывает видимый Chrome с отдельным профилем и тестовым сайтом;
- `scripts/install.ps1` (из `main` с чистым деревом) и гейты §12.3; любой красный гейт — установки нет.

Тест-карта владельца §13.1 (3 мин):
| # | Что сделать | Что должно быть |
|---|---|---|
| 1 | Открыть панель | Версия/дата внизу слева; `Yhteys: Ei yhteyttä`; все кнопки сбора неактивны |
| 2 | Запустить `diagnose.ps1` | Строки Chrome / NVIDIA / RAM / диск / модель с состояниями, без «unknown» |
| 3 | Нажать «Avaa työselain» | Открылся Chrome с отдельным профилем, видимое окно, тестовый сайт загружен |

Учти при S0:
- в §2.3 подпись состояния написана как «API: ei yhteyttä», в §5.1, i18n-ключах и тест-карте — `Yhteys: Ei yhteyttä`; приёмка идёт по тест-карте;
- в §5.1 «Avaa työselain» входит в блок Huomio, который виден только при `needs_attention`; тест-карта S0 требует кнопку без заданий. Где она в S0 — реши сам и запиши в «Решения» сдачи.

Сдача — шаблон из `CLAUDE.md`, отчёт `docs/ARGUS20_COLLECTOR_STAGE0_REPORT.md`. После сдачи — стоп до «ок».

## 5. Открыто до «ок» владельца (TZ_SELAIN §15)
Пп.1, 2, 4–8 — формулировки R8/K7/K9, таблица статусов, префикс API, **потолок €150 на разработку (п.5)**, облачный fallback, пилотные компании, язык панели. П.3 (отдельный репозиторий и сессия) принят 03.10.2026.

## 6. Установка комплекта на MAIN-PC (PowerShell 5, один блок)
Блок целиком, от `& {` до `}`. Остановится на первой ошибке и скажет, на какой.
```
& {
  $zip = Get-ChildItem -Path "$env:USERPROFILE\Downloads" -Filter 'gridex-argus-collector-kit*.zip' -ErrorAction Stop | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $zip) { Write-Host 'STOP: kit ZIP not found in Downloads'; return }
  if (Test-Path 'C:\dev\gridex-argus-collector') { Write-Host 'STOP: C:\dev\gridex-argus-collector already exists'; return }
  if (-not (git config user.email)) { Write-Host 'STOP: set git config --global user.name and user.email first'; return }
  New-Item -ItemType Directory -Force -Path 'C:\dev' -ErrorAction Stop | Out-Null
  Expand-Archive -Path $zip.FullName -DestinationPath 'C:\dev' -ErrorAction Stop
  Set-Location 'C:\dev\gridex-argus-collector'
  git init -q; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: git init'; return }
  git symbolic-ref HEAD refs/heads/main
  git add -A
  git commit -q -m 'stage-0: kit from gridex-argus20@196d2ba, no panel yet'; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: git commit'; return }
  git tag -a stage-0-start -m 'before stage S0'
  git log --oneline --decorate -1
}
```
Публикация на GitHub — после создания пустого репозитория `GridexOy/gridex-argus-collector` (без README):
```
& {
  Set-Location 'C:\dev\gridex-argus-collector' -ErrorAction Stop
  git remote add origin https://github.com/GridexOy/gridex-argus-collector.git
  git push -u origin main; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: push main - does the empty GitHub repo exist?'; return }
  git push origin stage-0-start
}
```
