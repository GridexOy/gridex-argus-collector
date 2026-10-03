# KIT_MANIFEST — комплект сборщика Selain

**Источник:** репозиторий `GridexOy/gridex-argus20`, ветка `main`, коммит `196d2ba2a0185535ee499f8bcae3ac677ef51999` (ARGUS VERSION 0.4.7.0).
**Собран:** 03.10.2026. Копии ARGUS побайтно совпадают с git-объектами этого коммита (проверено скриптом при сборке).

## Состав

| Файл | Происхождение | sha256 |
|---|---|---|
| `docs/ARGUS20_TZ_SELAIN.md` | копия ARGUS | `3b75cb214087ffd0c8fbc4bc8e56a6bc119db7ef8fa9944afbc130db38d708d6` |
| `docs/ARGUS20_COLLECTOR_OPENAPI.json` | копия ARGUS | `7b0eb0ba8a5a9dc57e53c5cfeb35a9efa42c4de7a66d67c6b0db2ceaf51f5d6b` |
| `docs/ARGUS20_ASSETS.md` | копия ARGUS | `d1dc138293727a03cfef2d93759efd597dc471ecaa9977bbf1ff482e9e5b7a98` |
| `docs/ARGUS20_VISION.md` | копия ARGUS | `e9f47172fa2e90f83a07b0991df280f260bec9afb1fd05ea0fc4bc96c262120a` |
| `docs/ARGUS20_DONE_AND_NON_GOALS.md` | копия ARGUS | `fc492adaf922ac1b679d11488acb4e61f86768fcecbbf70a9bd90df08f2b7683` |
| `docs/ARGUS20_WAYS_OF_WORKING.md` | копия ARGUS | `9bf308cde51dd9506cf1733feaef801360488e8bbaf4c1675b5733e52fbc22f0` |
| `docs/ARGUS20_RULES.md` | копия ARGUS | `8eae0026c922b98ee1a50f766f03ade28dd79b8cac23cee8eb8b10f97916b5da` |
| `docs/ARGUS20_ARCHITECTURE.md` | копия ARGUS | `4059303633ede1e3ff9143f0236275185fa45e4016468e43ac4068326e1da8bc` |
| `docs/ARGUS20_TZ_BLOCK0.md` | копия ARGUS | `083b2c216549cb882927aa15c9cf00a6442b6cf29321da8c44c79dc4b65f6775` |
| `docs/ARGUS20_SCREENS.md` | копия ARGUS | `760e6ce3071aa65cba38fadefffe509701ef142c7738d486e3339ae04c15cecb` |
| `docs/ARGUS20_BLOCKS.md` | копия ARGUS | `aef8e5269c20e47713b84a5dae0c027e017c51bafe1e8aa2686e19072e53d211` |
| `docs/legacy_line_hashes.txt` | копия ARGUS | `44818ac3260d9c6c5b5a65cd67453e04d07970d362d0185bfc5621f9c4c8c4e4` |
| `.gitattributes` | новый, для сборщика | `812c49f62bb4be9b44f1ab86abe76f92cdaf9cc78547e0f731c448f5aacf2f3b` |
| `.gitignore` | новый, для сборщика | `5af6389ca159c0b862b3e91b2d8cafe4e26dd692008b2bfb2da10db6256cab58` |
| `AGENTS.md` | новый, для сборщика | `5cb8f721c95fd9e0f882ebfd40edce97528fde45b708bdfa9d56643aff74e014` |
| `CLAUDE.md` | новый, для сборщика | `91faf9acb6c47d52d342c3f68861399bee372794cab4ca14ff9caa6830310cf5` |
| `README.md` | новый, для сборщика | `ccaa3bc53ca56e3d31d8107a5cb6889f9ec4218135849ac0543d676bb2cf9912` |
| `START_HERE.md` | новый, для сборщика | `0d1e76601c72e482c2ed48d1b8a80b7a9920145ca9b083dc1ef27f92abf67910` |
| `VERSION` | новый, для сборщика | `88f60d29a333b431a69f3325d338405ffa73295d9feef714a9abafc3817c7b9a` |
| `docs/ARGUS20_COLLECTOR_CHANGELOG.md` | новый, для сборщика | `893704033c7e0633bfa6477e5e3db9b49e28b2009599a65470157005ad15df4f` |
| `docs/ARGUS20_COLLECTOR_MODULES.md` | новый, для сборщика | `9fef07fbfa0cba58b6f2953f53f611c5dac607a12207ae7d4972ff7f6e47425d` |

## Версии

| Документ | Версия / правка |
|---|---|
| ARGUS20_TZ_SELAIN.md | v3.0, правка 03, 03.10.2026 |
| ARGUS20_COLLECTOR_OPENAPI.json | 3.0.0, OpenAPI 3.1.0, wire schema 1.1, base path `/api/collector` |
| ARGUS20_RULES / WAYS / ARCHITECTURE / NON_GOALS / SCREENS / BLOCKS | правка 03, 03.10.2026 |
| ARGUS20_TZ_BLOCK0.md | v1.4, 19.09.2026 |
| ARGUS20_VISION.md | правка 02, 17.09.2026 |
| ARGUS20_ASSETS.md | архивация 17.09.2026 (ТЗ ARGUS20-ARCHIVIST v1.1) |

## Проверки при сборке

- да — ТЗ Selain — версия 3.0
- да — ТЗ объявляет OpenAPI 3.0.0 и wire schema 1.1
- да — OpenAPI info.version = 3.0.0
- да — OpenAPI description ссылается на TZ_SELAIN 3.0
- да — OpenAPI: все const schema_version = 1.1
- да — RULES ссылается на TZ_SELAIN v3.0
- да — NON_GOALS ссылается на TZ_SELAIN v3.0
- да — правила из ТЗ (E1, E2, E3, E6, K1, K3, K4, K5, K7, K8, K9, R2, R3, R7, R8) определены в RULES
- да — все внутренние §-ссылки ТЗ ведут на существующие разделы
- да — все ссылки `ARGUS20_*` в комплекте ведут на файл комплекта или перечислены ниже как отсутствующие намеренно
- да — пути, которые ТЗ пишет буквально (`docs/ARGUS20_ASSETS.md`, `docs/legacy_line_hashes.txt`, `docs/ARGUS20_COLLECTOR_OPENAPI.json`), существуют
- да — правила в `CLAUDE.md` и `AGENTS.md` совпадают дословно

## Ссылки, которых нет в комплекте намеренно

| Имя | Где упомянуто | Почему нет |
|---|---|---|
| `ARGUS20_TZ_BLOCK6` | docs/ARGUS20_TZ_SELAIN.md | ТЗ блока 6 ARGUS ещё не написано (пишется после «ок» блока 5) |
| `ARGUS20_COLLECTOR_STAGE` | AGENTS.md, CLAUDE.md, docs/ARGUS20_BLOCKS.md, docs/ARGUS20_TZ_SELAIN.md | шаблон имени отчёта этапа; создаёт исполнитель при сдаче |
| `ARGUS20_COLLECTOR_STAGE0_REPORT` | START_HERE.md | отчёт этапа S0; создаёт исполнитель при сдаче S0 |
| `ARGUS20_ARCHIVIST_REQUEST` | docs/ARGUS20_WAYS_OF_WORKING.md | задание read-only сессии Архивариуса в старом репо; сборщику не нужно (вопросы Архивариусу — через отчёт) |
| `ARGUS20_BLOCK` | docs/ARGUS20_BLOCKS.md | шаблон имени отчёта блока ARGUS (`ARGUS20_BLOCK<N>_REPORT.md`) |
| `ARGUS20_BLOCK0_REPORT` | docs/ARGUS20_TZ_BLOCK0.md | отчёт блока 0 ARGUS; к сборщику не относится |
| `ARGUS20_BLOCK0_TESTCARD` | docs/ARGUS20_TZ_BLOCK0.md | тест-карта блока 0 ARGUS; к сборщику не относится |
| `ARGUS20_CHANGELOG` | docs/ARGUS20_TZ_BLOCK0.md | журнал ARGUS; у сборщика свой `ARGUS20_COLLECTOR_CHANGELOG.md` |
| `ARGUS20_MODULES` | docs/ARGUS20_TZ_BLOCK0.md | реестр модулей ARGUS; у сборщика свой `ARGUS20_COLLECTOR_MODULES.md` |

## Замечания к содержанию (не блокируют S0)

1. ТЗ §2.3 называет состояние панели «API: ei yhteyttä», а §5.1, i18n-ключи (`connection.title = Yhteys`, `connection.state.disconnected = Ei yhteyttä`) и тест-карта §13.1 — `Yhteys: Ei yhteyttä`. Приёмка — по тест-карте.
2. §5.1 помещает «Avaa työselain» в блок Huomio (виден только при `needs_attention`), а тест-карта S0 требует кнопку без заданий. Размещение в S0 решает исполнитель и пишет в сдаче.
3. `ARGUS20_ARCHITECTURE.md` пишет «согласовано с ТЗ блока 0 v1.3»; в комплекте ТЗ блока 0 v1.4 (добавлена живая проверка исполнителя, п.9а). На сборщик не влияет.

Документы ARGUS здесь не редактируются. Новая редакция приходит от владельца одним коммитом `docs: sync from gridex-argus20@<hash>` с новой описью.
