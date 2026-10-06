# ARGUS20_COLLECTOR_CHANGELOG

## 0.4.8.8 — 2026-10-06

**Правка 8 шага 7 (`stage-5/step-7-outbox-runs`): outbox не теряет события ни при каком ответе, кроме accepted / duplicate.** Дефект владельца: 06.10, 15:05–15:10 UTC, при 500/502 от сервера Tele-Tukku seq 28–34 и Sonepar seq 61–101 не дошли до ARGUS, и сборщик их больше не слал. Контракт не менялся (3.1.0).

**Где события останавливались (по коду cv0.4.8.6–0.4.8.7; журнал MAIN-PC за это окно запрошен в WINLOG, вопрос 9).** Сам 5xx событие не трогает: это повтор, проход доставки обрывается, outbox не меняется. Потеря шла по одному из трёх путей. Два воспроизведены тестами на коде 0.4.8.7:
1. **Новый run того же задания.** Аренда истекла, пока сервер отвечал 500/502: heartbeat не продлевал её 5 минут при сроке 180 с. ARGUS вернул задание в очередь, и claim выдал его с новым run. В журнале: `http: claim: job <id> new_run run <новый> gen <n>`.
   - `store_claimed` переписывал в `jobs` `run_id` и токен на новый run.
   - Для событий старого run `token_for` давал `None`, доставка их молча пропускала, каждый проход и навсегда. Они оставались `pending`, но больше не отправлялись: «сборщик больше не шлёт».
   - Воспроизведено: `test_outbox_kept.py`, на 0.4.8.7 три события старого run так и стоят `pending`.
2. **Запрос целиком отклонён 4xx** (например, 404 в окне деплоя, пока сервер поднимается). Первое событие пакета помечалось `rejected` и больше не уходило. Все следующие получали `sequence_gap` и повторялись без конца. Воспроизведено тем же файлом, на 0.4.8.7: `['rejected', 'pending']`.
3. **Поток доставки падал** на неожиданном ответе или исключении: у `_loop` не было защиты. `start()` поднимал потоки, только если мертвы оба, поэтому одна мёртвая полоса так и оставалась мёртвой. Это нашёл тест 0.4.8.8: два потока одновременно открывали базу с новой миграцией, второй падал на `duplicate column`.

**Что сделано.**
1. **Старый run досылается.**
   - Когда claim приносит новый run задания, токен прежнего run сохраняется (`run_tokens`, миграция 4, `scheduler/old_runs.py`), и его события и снимки идут с ним.
   - На 409 по старому run сборщик делает reconcile именно этого run. ARGUS отвечает drain-only токеном (поздние наблюдения старого run без права менять состояние, TZ_SELAIN 8.14), и остаток уходит с ним.
   - В журнале: `reconcile old run <run> of job <job>: drain_only`. Если reconcile не прошёл, события ждут и не отбрасываются.
2. **Запрос, отклонённый целиком (4xx, 409 по аренде), события не отбрасывает.**
   - Run ждёт backoff и спрашивается снова (`delivery/holds.py`), остальные run идут дальше в том же проходе.
   - Lähetys показывает «Lähetys epäonnistui», пока run ждёт.
   - Снимок отклоняется окончательно, только если ARGUS отказал в самом файле (`payload_too_large`, `evidence_hash_mismatch`).
   - `idempotency_conflict` по-прежнему отмечает событие: у ARGUS под этим id уже лежит другое.
3. **Поток доставки не умирает.** Исключение прохода (в том числе при открытии базы) пишется в журнал: `delivery: pass failed, the outbox waits: <тип>: <текст>`. Проход повторяется через 30 с. `start()` поднимает каждую упавшую полосу отдельно.
4. **Миграции хранилища идут под блокировкой.** Несколько потоков, открывающих базу одновременно, не мигрируют её дважды.

Окончательные вердикты ARGUS по отдельному событию (`invalid_input`, `quote_not_found`, …) остаются окончательными по контракту: событие записано, повтор получит тот же ответ. Это не потеря, а «Hylätty» с причиной.

**Модули.**
- Новые: `scheduler/old_runs.py`, `delivery/holds.py`.
- Изменены:
  - `scheduler` (leases, hooks);
  - `delivery` (loop, uploads, service);
  - `storage` (service: миграция 4; repository: блокировка миграций);
  - `pyproject.toml`.

**Тесты.**
- Новые: `scheduler/tests/test_outbox_kept.py` (новый run и старый run досылается; 404 на запрос — события ждут, другое задание идёт), `delivery/tests/test_holds.py` (holds, поток переживает исключение, гонка миграций).
- Проверено, что новые тесты ловят дефект:
  - на коде 0.4.8.7 оба теста `test_outbox_kept` падают;
  - без блокировки тест гонки миграций падает каждый раз.

**Не проверено на Windows:** что делает боевой ARGUS после истечения аренды. Выдаёт ли он задание с новым run и даёт ли drain-only токен на reconcile старого run — стенд выдаёт тот же run, а drain-only на старый run даёт. Это ответ MAIN-PC на вопрос 9.

**Решения (поправь, если не так).**
1. Правка — отдельная версия 0.4.8.8 (0.4.8.7 уже в `main`). Ставить на MAIN-PC 0.4.8.8: вопросы 1–8 к ней те же.
2. Run, ждущий после 4xx, повторяется с тем же backoff, что и обрыв связи (до 30 с). Если ARGUS отказывает всегда, outbox ждёт, и это видно в Lähetys. Событие не выбрасывается.

## 0.4.8.7 — 2026-10-06

**Правка 7 шага 7 (`stage-5/step-7-schema12`), одной сдачей: схема 1.2, дочитывание после цели, страновая версия сайта (K10 шаг 1), K7, Blåkläder, доставка по WINLOG.** Контракт — перевыпуск 3.1.0 (wire 1.2) из `gridex-argus20` (commit `004fcbd`): `ARGUS20_COLLECTOR_OPENAPI.json`, `CONTRACT_3.1.md`, `collector_contract/events.response.v1_2.json`; клиент API сгенерирован заново.

**Что сделано.**
1. **Схема 1.2.** В heartbeat `schema_versions: ["1.1", "1.2"]`, события уходят с `schema_version: "1.2"`. Отказ ARGUS несёт `detail {rule, observation_id, field, message}`: код в outbox хранится как `<код>/<правило>` (`invalid_input/person_without_name`). В Jono («Hylätty N: henkilöltä puuttuu nimi») и Lähetys причина показывается словами правила. В журнале — наблюдение, поле и сообщение ARGUS. Семь правил переведены (`delivery.rule.*` в `fi.json`). По `CONTRACT_3.1` (Beckhoff / BCC): каждое событие о человеке несёт его имя. `contact.enriched` без `full_name` больше не уходит: имя добавляется отдельным наблюдением с той же цитатой.
2. **Дочитывание после цели.** Цель достигнута, а на странице уже найдены ссылки team / henkilöstö / yhteystiedot / contact / staff / ansprechpartner / medarbetare. Они читаются, не более 2 (`ending.FOLLOWUPS`), затем «Tavoite saavutettu». Стенд `fixture_oy`: цель на `contact.html`, затем `team.html` — 5 человек вместо 3.
3. **Страна версии сайта = страна выставки** (Carlo Gavazzi ушёл на `/en-br/`).
   - **K10, шаг 1** (уточнение владельца: Wera и OMICRON ушли на `/ru/` из-за Accept-Language ru из Windows). Chrome сбора и рабочий профиль всегда идут как fi-FI, независимо от языка системы:
     - `--lang=fi-FI`, `--accept-lang=fi-FI,fi,sv,en`, поэтому `navigator.language` = fi-FI;
     - заголовок `Accept-Language: fi,sv;q=0.8,en;q=0.6` на каждом запросе, включая саму страницу;
     - `timezone Europe/Helsinki`.
     Опция Playwright `locale` не используется: она отправляет при навигации голое `fi-FI`, это поймал тест на живом сервере. Редирект по IP — шаг 2 K10, не в этой версии.
   - **Версия сайта.** Если первая страница обхода — версия другой страны (`/en-br/`, `lang=ru`) или глобальная, но называющая финскую, обход до чтения идёт на финскую. Порядок:
     1. `hreflang` (сначала `xx-FI`, потом `fi`);
     2. переключатель страны или языка (`Suomi`, `Finland`, `/en-fi/`);
     3. тот же путь под `/fi/`, `/en-fi/`, `/fi-fi/` — только на сайте с локалями в пути;
     4. страница Finland / Suomi / Nordic;
     5. иначе, если сайт чужой версии, — глобальная версия (`x-default`, `en`, `/en/`).
   - Кандидата сначала спрашиваем (статус и редиректы, не уходя со страницы). Кандидат, который возвращает туда, откуда пришли (редирект по IP), или ведёт в другую страну, пропускается.
   - Строка в Keruu:
     - «Maa: FI (vaihdettu en-br → en-fi)»;
     - «Maa: FI — maaversiota ei löytynyt, globaali sivusto (vaihdettu … → …)»;
     - «Maa: FI — maaversiota ei löytynyt, jatketaan sivustolla en-br».
   - **Страна человека:** заголовок его раздела → код телефона (`+358` → FI, цитата — сам телефон) → `<html lang>`. Раньше человек на `/en-br/` получал BR по `lang`.
4. **K7: люди и каналы — только со страниц домена компании** (Professor Roope Raisamo с `industryx.dimecc.com`).
   - Домены компании берутся из сида и одобренных хостов с основанием `seed`, `redirect_from_seed`, `owner_known_url`, `business_id_match`; поддомены входят.
   - Страница хоста, одобренного только как `linked_from_contact_section` (мероприятие, каталог), сохраняется как источник (подтверждение участия). Ни людей, ни каналов, ни шаблона почты с неё не берётся, модель на ней не вызывается.
   - В Keruu один раз на хост: «Vieras verkkotunnus …: vain lähteeksi, henkilöitä ja kanavia ei lueta».
5. **Blåkläder («Löydetty: 44» при 22 людях).**
   - Счётчик «Löydetty» и таблица Keruu при сборе считались за всю сессию. Теперь у каждой компании своя таблица и свой счёт.
   - Имена на сайте написаны обычным регистром, а капсом их показывает CSS `text-transform`, и `innerText` возвращал капс. Текст страницы и вкладок теперь читается с выключенным `text-transform`: имя и цитата — как в HTML.
   - На стенде `blaklader` без этого правила не читали ни одного из 22 (имена капсом для них не имена), с ним — 22 строки в ARGUS, ни одной дважды, хотя 7 продажников повторяются на `myynti/`.
   - Хвост Blåkläder после seq 23 терялся по `lease_expired` — это п. 6б.
6. **Доставка (WINLOG MAIN-PC 06.10 17:20).**
   - **а)** События идут своим потоком и не ждут очереди снимков (3–5 с на снимок у ARGUS). Пакет страницы уходит, как только записано её закрывающее событие (`source.processed`), опрос раз в 0,2 с; снимки грузятся своим потоком.
     - Контракт 3.1.0 (ARGUS 0.4.24.4): событие раньше своего снимка ARGUS принимает как `accepted` + `evidence_pending` и применяет при загрузке.
     - Событие, которому ARGUS ответил `evidence_missing`, по-прежнему ждёт свой снимок (до 3 повторов).
     - Конец прогона (`contact.freshness`, `job.finished`) ждёт, пока загрузятся все снимки прогона: проверка свежести называет наблюдения, которые ARGUS записывает только при загрузке снимка. Иначе проверка отклоняется `invalid_input` («observation is not sent in run»). Это поймал `test_collector_history`.
     - Событие, чей снимок здесь потерян или отклонён, отдаётся сразу: `Hylätty: todiste puuttuu`, его seq занимает `source.blocked`. Иначе ARGUS держал бы его 24 часа в ожидании, а панель показывала бы «принято».
   - **б)** Задание с законченным обходом остаётся в heartbeat, пока у его прогона есть недоставленные события: аренда продлевается, пока хвост не ушёл.
   - **в)** `CLICK_TIMEOUT_MS` 10 с → 3 с: отсутствующий или перекрытый элемент стоит 3 с, не 10.
   - **г)** (WINLOG 17:27, вопрос MAIN-PC 4) `claim_jobs`, `post_events`, `reconcile_job` ждут ответа 30 с, как heartbeat и загрузка снимка (`delivery.API_TIMEOUT_S`). Было 10 с: 73 из 106 claim за час без ответа при зелёной связи.
   - **д)** (вопрос MAIN-PC 5) Провал claim виден в Jono и при непустой очереди: красная строка «Uusien tehtävien haku epäonnistui — alla viimeksi haetut» над таблицей, до первого успешного claim.

**Модули.**
- Новые: `walk/scope.py`, `walk/country.py`, `discovery/versions.py`, `delivery/uploads.py`; `contract_server/pending.py`.
- Изменены:
  - `api_client` (сгенерирован заново);
  - `delivery` (loop, results, retry, service, contract);
  - `scheduler` (leases, runner, service);
  - `walk` (ending, entities, findings, goal, runner, page, context, state, service);
  - `discovery` (service, contract);
  - `browser` (service, host, session, scripts, page_tools, contract);
  - `normalization` (`phone_country`);
  - `ui` (heartbeat_call, queue_lines, walk_lines, app_walk, app_collect);
  - `collector/messages/fi.json`, `pyproject.toml` (import-linter).
- Стенд ARGUS:
  - схема 1.2 и `detail`;
  - правило `person_without_name` для `contact.enriched`;
  - `evidence_pending` и применение при загрузке (`contract_server/pending.py`).
- Стенды сайтов: `elkris` + `industryx` (K7), `blaklader`, `gavazzi` — с gold.

**Тесты.**
- Новые:
  - `walk/tests/test_walk_k7.py`, `test_walk_country.py`;
  - `discovery/tests/test_versions.py`;
  - `scheduler/tests/test_company_domains.py`, `test_lease_tail.py`, `test_collector_blaklader.py`;
  - `ui/tests/test_found_per_company.py`, `test_refusal_detail.py`;
  - `collector/tests/contract/test_event_lane.py`;
  - `delivery/tests/test_batch.py` (что уходит в следующем запросе);
  - `scheduler/tests/test_timeouts.py`, в `ui/tests/test_queue_lines.py` — провал claim над непустой очередью;
  - в `browser/tests/test_host.py`: fi-FI, Helsinki, Accept-Language, probe.
- Обновлены:
  - схема 1.2 в тестах клиента и стенда;
  - `evidence_pending` вместо `evidence_missing` для события раньше снимка;
  - цель + дочитывание: панель ждёт «Tavoite saavutettu: 5 henkilöä, 10 kanavaa».
- Проверено, что новые тесты ловят дефект: без продления аренды `test_lease_tail` падает, без снятия `text-transform` `test_collector_blaklader` получает 0 людей из 22.

**Не проверено на Windows** (контейнер Linux):
- закрытие Chrome при Pysäytä (общий Chrome на весь сбор проверен MAIN-PC 06.10: WINLOG, 1 запуск на 27 заданий);
- `--lang` / `--accept-lang` в установленном Chrome (`channel=chrome`, видимое окно): `navigator.language` и `Intl` на Windows с русской системой;
- heartbeat 1.2 и `detail` против прод-ARGUS;
- `evidence_pending` прод-ARGUS (0.4.24.4);
- `fetch`-проверка кандидатов версии через Hiddify.

**Решения (поправь, если не так).**
0. Предложения MAIN-PC 4 и 5 (WINLOG 17:27: таймаут 30 с для claim / events / reconcile, провал claim при непустой очереди) взяты в эту правку без отдельного «ок»: обе маленькие и прямо мешают сбору.
1. `Intl` (формат дат) остаётся языком системы: Playwright `locale` ломает Accept-Language навигации. Сайты выбирают версию по заголовку и `navigator.language`, оба — fi-FI.
2. Угаданные URL (`/fi/`, `/en-fi/`, `/fi-fi/`) пробуются только у сайта, где версия уже в пути (`/en-br/`), и только если первая страница — чужая версия. Глобальная страница без локали в пути (Reimax, Ellego) не трогается; глобальная `/en-en/` (Beckhoff) переходит, только если сама называет финскую версию.
3. Страна человека по адресу не читается: у карточки человека нет поля адреса. Страна — по разделу, телефону, `lang`. Офис получает страну по разделу, как и раньше.
4. K7 считает своими только основания `seed`, `redirect_from_seed`, `owner_known_url`, `business_id_match`; `linked_from_contact_section` и неизвестные — чужие.
5. Как Carlo Gavazzi попал на `/en-br/`: в WINLOG нет строк журнала этого задания. Вопрос — MAIN-PC (раздел «Вопросы облака»). Если сид отдаёт `/en-br/` по IP, это шаг 2 K10; переход на финскую версию из п. 3 работает и тогда, если сайт не возвращает обратно по IP.

## 0.4.8.6 — 2026-10-06

**Правка 6 шага 7 (`stage-5/step-7-ellego`): Ellego, петли Kontaktit, общий Chrome, правило цели, Reimax, p95.** Контракт 1.1 не менялся.

**Что сделано.**
1. **Ellego** (05.10: карточки видны на первой странице контактов, обход ходил по кругу, никого не извлёк). Люди страницы читаются до любого перехода или клика. Правила (`extraction/text_cards.py`) читают карточку «имя, ≤ 2 строки (первая — должность), свой телефон / почта ниже»: должности и пункты меню — не имена, страны — не имена, строка общего ящика или коммутатора закрывает карточку и не приписывается человеку. На стенде `ellego` правила читают 40 из 40 (мега-меню 9000+ символов перед первой карточкой), модель не вызывается, фильтры не нажимаются, ни одно состояние страницы не повторяется. Модели карточек (если правила никого не прочитали) текст подаётся окнами вокруг каналов, похожих на личные, до 3 вызовов параллельно, лимит ответа — 4096 токенов, оборванный ответ сохраняет целых людей.
2. **Петли (Kontaktit 05.10).** Ссылка, которая привела на другую страницу своих хостов (редирект WPML `/contact-us/` ↔ `/fi/ota-yhteytta/`), помечается пройденной вместе с этой страницей и больше не предлагается — при любом редиректе (правило владельца 06.10). Проверено: gold на всех стендах не меняется (сомнение из задания «не всегда — ломает gold» на 0.4.8.6 не подтвердилось). Переход на уже прочитанную страницу запрещён в любом источнике решения. Кнопка, нажатая в этом состоянии страницы, больше не предлагается. 6 действий подряд без нового состояния — обход завершается `no_progress` (completed). Лимит действий обхода из панели — `walk.action_budget` (60) в config.yaml.
3. **Общий Chrome.** Видимый Chrome больше не перезапускается на каждую компанию: один процесс на весь сбор (`browser/host.py`), на компанию новый контекст (чистые cookies), после обхода закрывается контекст, не браузер. Chrome закрывается при остановке сбора (Pysäytä, STOP) и запускается снова, если упал. В журнале на каждый обход: `chrome start=<ms> ms shared=yes` (0 — Chrome уже работал). В `walk_timing` — колонки «Chrome starts», «Chrome s» и строка «Chrome: N start(s) for M job(s), S s». Продолжение после проверки, пройденной владельцем в рабочем браузере (Huomio → Jatka), открывает профиль рабочего браузера (cookies проверки лежат там) тем же Playwright, что и общий Chrome: второй sync-Playwright в одном потоке не запускается — это поймал `test_collector_attention`. Закрытие окна панели останавливает сбор и ждёт до 10 с, пока поток закроет Chrome, — процесс не выходит с открытым браузером. Ошибка обхода теперь в журнале: `browser: job <id>: walk error <тип>: <строка>` (раньше было видно только `finished failed (technical_failure)`).
4. **Правило цели (владелец 06.10).** Перед каждым следующим действием сборщик подводит итог: найден человек с ролью продаж / маркетинга и прямым каналом (телефон или почта, напечатанные на сайте) — цель достигнута, обход завершается completed. Люди без такого канала — не более 2 дополнительных страниц, потом стоп. Запрет завершения при непосещённой сильной ссылке из `decide.py` убран. В панели (Keruu) при остановке: «Tavoite saavutettu: N henkilöä, M kanavaa». Выключается `walk.stop_at_goal: false`.
5. **«Модель читает, правила ходят» на странице с людьми от правил (Reimax 06.10, п. 2).** Если правила нашли людей на странице, модель на ней не вызывается ни для карточек, ни для выбора шага. Следующий шаг выбирают правила (контактная ссылка, иначе лучшая по рангу); страница повторно не обходится.
6. **Шаблон адреса с сайта (Reimax 06.10, п. 1).** Фраза страницы вида «Our e-mail addresses are the following: firstname.lastname@reimax.net» (также `etunimi.sukunimi@`, `vorname.nachname@`, `[first].[last]@`, обратный порядок) — поле компании `email_pattern` с цитатой строки, никогда не адрес и не канал (RULES K3). Каждый человек этой страницы без напечатанного адреса получает адрес по шаблону (ä→a, ö→o, ß→ss; имя и фамилия — первое и последнее слово) с цитатой — строкой шаблона. Адрес уходит как `email` с `extraction_status=ambiguous`, binding `none`, и ARGUS выводит `inferred` (§9.4). В панели — «oletettu: …». Напечатанный адрес всегда главнее. В правило цели адрес по шаблону как прямой канал не входит.
7. **p95 (1 min)** считается только по событиям, поставленным в очередь и подтверждённым в эту минуту. Событие, ждавшее в очереди раньше (89984.8 s), не входит.

**Почта по шаблону и строка в ARGUS (вопрос владельца).** Контракт 1.1 это позволяет, если ARGUS отдаёт свой вычисленный адрес человека в `ClaimedJob.known_contacts`. Тогда:
- адрес по шаблону сайта с тем же значением уходит как `change_kind=reconfirmed` и ложится в ту же строку как ещё один источник с цитатой;
- адрес с другим значением уходит как `changed` + `supersedes_observation_id`: шаблон сайта вытесняет вычисленный.

Это проверено на контракт-сервере (`test_collector_reimax.py`: повторный прогон — одна строка на человека, `last_confirmed_at`).

Что нужно от сервера:
- (а) в `known_contacts.fields.email` отдавать вычисленный адрес вместе с `observation_id` (форма `{value, observation_id}` уже читается), иначе сборщик отправит `new`, и сервер должен сам свести одинаковые значения в одну строку;
- (б) поле `email_pattern` компании от сборщика (с цитатой) должно быть приоритетнее вычисленного шаблона при пересчёте адресов остальных людей компании;
- (в) в `FinishedPayload.completion_reason` нет `goal_reached`: окончание по цели уходит `frontier_exhausted` (`coverage.frontier_status=partial`, у известных контактов `not_checked`); если ARGUS нужен отдельный код — перевыпуск контракта.

**Модули.**
- Новые: `browser/host.py`, `extraction/email_pattern.py`, `extraction/text_cards.py`, `walk/goal.py`, `walk/ending.py`, `walk/patterns.py`.
- Изменены: `walk` (cards, page, decide, runner, actions, state, sink, service, contract, timing, findings, context, rules, prompts), `extraction` (service, contract), `models` (Detached / Salvage), `scheduler` (collector, runner, service), `delivery` (repository: p95), `runtime` (config), `ui` (walk_lines, app_walk, app_collect), `pilot` (timing, timing_render), `collector/messages/fi.json`, `config.example.yaml`, `pyproject.toml` (import-linter).
- Стенды: `test_site/sites/ellego`, `test_site/sites/reimax` с gold.

**Тесты.**
- Новые: `walk/tests/test_walk_ellego.py`, `test_walk_reimax.py`, `test_goal.py`, `test_loops.py`; `extraction/tests/test_email_pattern.py`; `browser/tests/test_host.py`; `scheduler/tests/test_collector_chrome.py`, `test_collector_reimax.py`; `delivery/tests/test_p95.py`; `ui/tests/test_goal_lines.py`; `test_site/tests/test_ellego.py`, `test_reimax.py`.
- Обновлены под правило цели: Beckhoff и LEDVANCE заканчиваются по цели (Johto Beckhoff — CEO и CFO — не обходится); тесты панели ждут «Tavoite saavutettu: 3 henkilöä, 6 kanavaa». Тесты полного обхода по gold идут с `stop_at_goal=False`.

**Не проверено на Windows** (контейнер Linux): видимый установленный Chrome как один процесс на весь сбор (`channel=chrome`, `chromium.launch` вместо `launch_persistent_context`); закрытие Chrome при Pysäytä.

**Решения (поправь, если не так).**
1. Прямой канал для правила цели — телефон или почта человека, напечатанные на сайте. Адрес по шаблону и общий номер компании — не прямой канал.
2. Роли продаж / маркетинга — по словам должности (sales, marketing, key account, export, area / country manager, myynti, markkinointi, vienti, vertrieb, försäljning / sälj, …). Генеральный директор — не продажи.
3. «Не более 2 дополнительных страниц» действует и тогда, когда у людей есть каналы, но нет ролей продаж: «есть непосещённая ссылка» — не причина продолжать.
4. На странице, где правила нашли людей, структурные действия правил (вкладки, кнопки отделов) остаются: это правила, не модель. Модель на такой странице не вызывается.
5. Шаблон применяется к людям той же страницы, где он назван. `email_pattern` едет на сущности канала компании (общий ящик / коммутатор) этой или более ранней страницы: повторный прогон находит её по каналу и подтверждает шаблон в той же строке (`reconfirmed`); своя сущность `organization_channel` — только если канала компании нет. Для этого сборщик ищет известный контакт и по каналу из ключа сущности (на странице, где канал уже отправлен, событие несёт только шаблон) — найдено живой проверкой: шаблон ложился второй строкой.
6. Правило цели можно выключить (`walk.stop_at_goal: false`): тесты полного чтения сайтов по gold работают с ним выключенным.

## 0.4.8.5 — 2026-10-05

**Правка 5 шага 7 (`stage-5/step-7-evidence-loop`), приоритет владельца 05.10: петля доставки `evidence_missing`.** ARGUS отклонял `contact.observed` как `evidence_missing` (16 событий, 5 заданий, например job 87e9f874 seq 9–156), сборщик писал «the snapshot was not uploaded, sent again» и повторял событие каждые ~90 с без конца (шесть кругов за 8 минут по `delivery_check` 20:03–20:11 UTC). Контракт не менялся.

**Что сделано.**
- `evidence_missing`: сначала снимки, которые называет событие, снова ставятся в загрузку, событие ждёт их (как и раньше) и уходит снова — не более 3 повторов с этим кодом (`retry_count` в outbox). Снимка нет здесь (строка загрузки есть, файлов нет) или ARGUS отказал в 4-й раз — событие отброшено: `Hylätty N: todiste puuttuu` в Jono, `Lähetysvirhe: N (todiste puuttuu)` в Lähetys, в `pilot rejected` / `delivery_check.ps1` — его event_id и код; больше не отправляется.
- ARGUS не засчитывает seq события, отклонённого как `evidence_missing` (контракт: «observations require already uploaded evidence», seq остаётся свободным, следующие события получают `sequence_gap`). Чтобы остаток прогона, включая `job.finished`, дошёл, свободный seq занимает событие `source.blocked` без снимков: `status` `evidence_missing`, URL страницы, `detail` — какое событие и почему не доставлено. Если ARGUS этот seq уже засчитал (`last_contiguous_seq` ≥ seq), замены нет.
- `sequence_gap` — следствие пропуска перед ним, в лимит повторов не входит; переходы транспорта и ошибки запроса (нет ответа, 5xx, 429) — не отказ события и тоже не считаются.
- Журнал: `… rejected evidence_missing (the snapshot is missing in ARGUS): snapshot uploaded again first (was {…: 'duplicate'}), retry 1 of 3` — со статусом прошлой загрузки снимка (если ARGUS отвечал `duplicate`, а событие всё равно `evidence_missing`, расхождение на стороне ARGUS видно в журнале); отказ — строка с компанией и причиной; замена — `seq N carries source.blocked <id> instead of contact.observed <id>`.
- Тесты больше не пишут в рабочий журнал MAIN-PC (`conftest.py` в корне: временный `ARGUS_COLLECTOR_HOME` на весь прогон). Раньше `install.ps1` во время тестов дописывал в `%LOCALAPPDATA%\Gridex\ArgusCollector\logs` строки тестовых заданий (`transport …`, `collecting on/off`, страницы, вызовы модели) — например, 18:17:54–18:18:38 в выводе установки 0.4.8.4; базу, паринг и токен тесты не трогали.

**Модули.** Новые файлы: `delivery/retry.py`, `conftest.py` (корень). Изменены: `delivery` (results, repository, service, README), `storage` (миграция 3: `outbox.retry_code`, `retry_count`, `replaced_type`, `replaced_event_id`), `collector/messages/fi.json` (`delivery.rejected.evidence_missing`: «todiste puuttuu»). Тесты: `delivery/tests/test_retry.py`, `collector/tests/contract/test_evidence_loop.py` (контракт-сервер: отброшенное событие, замена на его seq, следующее событие принято).

**Решения (поправь, если не так).**
1. Замена `source.blocked` на свободном seq — без неё отброшенное событие навсегда держало бы остаток прогона в `sequence_gap`, а лимит в 3 повтора отбросил бы и весь хвост.
2. Лимит 3 повтора — только для отказов события с кодом, при которых оно остаётся в очереди (`evidence_missing`); `sequence_gap` и ошибки связи — не считаются.
3. Изоляция тестов включена в эту правку: строки тестов в рабочем журнале путали разбор живых логов.

## 0.4.8.4 — 2026-10-05

**Правка 4 шага 7 (`stage-5/step-7-heartbeat-win2`): `install.ps1` на MAIN-PC остановился на двух тестах 0.4.8.3.** Контракт и поведение панели не менялись — правка только в тестах.

**Причины и правка.**
1. `runtime/tests/test_instance.py::test_a_panel_process_holds_the_lock_and_its_end_frees_it`: `owner()` вернул 2952, `Popen.pid` — 32676. На Windows `venv\Scripts\python.exe` — лаунчер, интерпретатор работает его дочерним процессом, и pid в `state/panel-pid` пишет именно он (это правильный pid для диспетчера задач). Тест теперь сравнивает файл с pid, который сообщил сам процесс, державший блокировку, и завершает этот процесс (на Windows — `TerminateProcess`, как аварийное завершение), а не лаунчер; освобождения блокировки ждёт до 10 с.
2. `ui/tests/test_connection_clock.py::test_no_answer_at_all_is_ei_verkkoa`: Windows сообщает об отказе закрытого порта 127.0.0.1 примерно через 2 с (TCP повторяет SYN после RST; сам urllib не повторяет), а таймаут чтения в стенде был 1 с — сокет истекал по таймауту, панель честно показывала `Hidas yhteys`, и `Ei verkkoa` не наступало. В этом тесте таймаут 10 с (в панели 30 с), ожидание до 30 с, фактическое время печатается, а при неудаче сообщение показывает состояние, секунды и текст ошибки. Механизм проверен в контейнере: порт, который рвёт соединение через 2 с, при таймауте 1 с читается как `slow 1 s`, при 10 с — `Ei verkkoa` через 2.0 с.

**Не проверено на Windows** (в контейнере Linux): `test_instance.py` (путь `msvcrt` и лаунчер venv), время отказа в `test_no_answer_at_all_is_ei_verkkoa`.

**Решение (поправь, если не так).** Правка — 0.4.8.4 (решение владельца); Ellego — 0.4.8.5.

## 0.4.8.3 — 2026-10-05

**Правка 3 шага 7 (`stage-5/step-7-heartbeat-win`): `install.ps1` на MAIN-PC остановился на тестах 0.4.8.2 (7 падений; в контейнере на Linux всё проходило).** Контракт не менялся; поведение панели — как в 0.4.8.2, плюс одно уточнение правила «Hidas yhteys».

**Причины и правка.**
1. `ui/tests/test_connection_clock.py` (4 из 5): испытательный стенд `ui/tests/slow_argus.py` пересылал запросы в контракт-сервер через `urllib.request.urlopen`, то есть через системный прокси Windows; на MAIN-PC он есть, и запросы к 127.0.0.1 до стенда не доходили. Остальные стенды репозитория ходят напрямую (`ProxyHandler({})`) — теперь и этот. Воспроизведено в контейнере: со «старым» стендом и недоступным прокси в окружении — те же 4 падения, с исправленным — 5 из 5.
2. `test_no_answer_at_all_is_ei_verkkoa`: на Windows отказ соединения с закрытым портом localhost приходит примерно через 2 с, а правило 0.4.8.2 «прошло ≥ 90 % таймаута — значит, медленно» при тестовом таймауте 1 с называло отказ «Hidas yhteys». Правило уточнено в коде панели: `Hidas yhteys` — только когда сокет сам сообщил `timed out`; отказ соединения — `Ei verkkoa`, сколько бы Windows его ни сообщала.
3. `runtime/tests/test_instance.py` (2): на Windows байт, заблокированный `msvcrt.locking`, не читается другим дескриптором, поэтому номер процесса из файла блокировки читался как `?` (окно второй панели показало бы `prosessi ?`). Номер процесса теперь пишется в отдельный файл `state/panel-pid`; блокировка снимается явно перед закрытием (`runtime.panel_release`), потому что Windows освобождает её у закрытого файла не сразу.

**Самопроверка.** Полный набор тестов прогнан ещё и с недоступным системным прокси в окружении (`http_proxy` на закрытый порт, `no_proxy` пуст) — как на MAIN-PC.

**Модули.** Изменены: `runtime` (instance, contract), `ui` (connection_lines, app_connection, contract; тесты `slow_argus.py`, `test_connection_lines.py`, `test_instance.py`).

**Решение (поправь, если не так).** Правка 0.4.8.2 уже в `main`, поэтому исправление — новая версия 0.4.8.3; Ellego — 0.4.8.4.

## 0.4.8.2 — 2026-10-05

**Правка 2 шага 7 (`stage-5/step-7-heartbeat`), связь панели (владелец 05.10): после таймаута heartbeat цикл не возобновлялся, «Viimeksi» стоял 30 мин при открытом пути; в журнале несколько одинаковых переходов транспорта и heartbeat в одну секунду.** Контракт не менялся.

**Что видно.**
- Yhteys: heartbeat каждые 30 с всегда — после таймаута, 5xx, 401 (`Tunnus hylätty`) и ошибки внутри панели; отсчёт от начала прошлой попытки. Таймаут чтения heartbeat — 30 с (было 10 с).
- Нет ответа за 30 с — `Hidas yhteys: 30 s` жёлтым (раньше `Ei verkkoa: HTTP 0: … timed out`), Lähetys при этом не переходит в `Ei verkkoa`: события идут своими запросами. `Ei verkkoa` — только когда ответа нет вовсе (отказ соединения, нет DNS). Ошибка внутри панели при отправке heartbeat — `Paneelin virhe: <тип>: <текст>` красным, следующий heartbeat через 30 с.
- Кнопка «Yhdistä uudelleen» рядом с «Yhdistä»: heartbeat сразу по сохранённому ключу, ключ вставлять не нужно; неактивна, пока паринга нет или идёт проверка.
- «Yhdistä» с пустым полем ничего не делает и не пишет `Paritusavain ei kelpaa`; сообщение — только для непустого поля.
- Одна панель на машину: второй запуск показывает окно `ARGUS Selain on jo auki tällä koneella (prosessi N). Käytä avointa ikkunaa…` и закрывается; в журнале `http: panel started: pid N`, `panel closed: pid N`, `panel not started: pid N has the panel open`.
- Lähetys (владелец 05.10, «Yhdistetty + Ei verkkoa»): одно состояние транспорта из одного источника (`delivery/transport.py`). `Ei verkkoa` — только когда heartbeat не получил никакого ответа (Yhteys тоже `Ei verkkoa`) и доставка тоже: последний её запрос без ответа или после падения heartbeat ни один не получил ответа (пустая очередь ничего не шлёт). Запрос доставки без ответа при проходящем heartbeat — `Lähetetään` и повтор (раньше — `Ei verkkoa` до первого полностью успешного прохода, отсюда «Yhdistetty» рядом с красным «Ei verkkoa» при убывающей очереди); ответ доставки при оборванном heartbeat — не `Ei verkkoa`; медленный heartbeat (`Hidas yhteys`) Lähetys в `Ei verkkoa` не переводит; любой HTTP-ответ, в том числе 5xx, — ответ.
- Журнал: переход транспорта (`delivery: transport offline -> synced`) пишется один раз, кем бы из двух потоков (heartbeat или доставка) он ни был замечен; heartbeat — одна строка при смене ответа, в том числе `heartbeat: no answer in 30 s (slow, not offline)`; часы, остановленные чем угодно, панель запускает снова (`heartbeat: the clock had stopped, started again`).

**Причина (по коду; лог MAIN-PC за тот час не приходил).** До 0.4.8.2 heartbeat слал поток цикла плюс отдельный поток на каждое «Yhdistä» и старт панели. Цикл ловил только ошибки HTTP: любое другое исключение внутри попытки (SQLite `database is locked` после 30 с ожидания при чтении полей или применении ответа, ошибка при применении аренд и команд) завершало поток навсегда — на экране оставалось состояние прошлой попытки (`Ei verkkoa` от таймаута) и «Viimeksi», и никто цикл не перезапускал. Ответ 401 останавливал цикл по замыслу 0.4.7.0. Теперь все heartbeat шлёт один поток часов (`ui/heartbeat_loop.py`), исключение любой попытки ловится и показывается, мёртвые часы перезапускает панель раз в секунду, зависшая попытка видна как `Hidas yhteys: N s`.

**Параллельные циклы.** В одном процессе 0.4.8.1 могли одновременно идти поток цикла и потоки «Yhdistä»/старта — три heartbeat в одну секунду. Четыре одинаковых перехода транспорта в одну секунду — это несколько процессов панели (в одном процессе один поток доставки): все потоки панели фоновые, закрытое окно завершает процесс, значит панели были открыты одновременно — например, панель открыта ярлыком после `install.ps1`, пока старая ещё работала. Теперь: один процесс панели (блокировка `state/panel-lock`), один поток heartbeat, одна строка на переход транспорта.

**Модули.** Новые файлы: `ui/heartbeat_loop.py`, `ui/heartbeat_call.py`, `runtime/instance.py`, `delivery/transport.py`. Изменены: `ui` (app_connection, connection_lines, view_connection, view, app, contract, README), `runtime` (contract, README), `delivery` (loop, hooks, service, README), `scheduler/collector.py` (docstring), `collector/messages/fi.json` (`connection.reconnect`, `connection.state.slow`, `connection.state.panel`, `panel.alreadyOpen`). Тесты: `ui/tests/test_heartbeat_loop.py`, `test_connection_clock.py` (+ стенд `slow_argus.py`), `test_ui_reconnect.py`, `runtime/tests/test_instance.py`, `delivery/tests/test_transport.py`, дополнение `delivery/tests/test_link.py`, `scheduler/tests/test_collector_recovery.py` (ARGUS выключен — heartbeat тоже без ответа); `ui/tests/conftest.py` останавливает часы heartbeat каждого теста (фоновые потоки не пишут в журнал следующего).

**Решения (поправь, если не так).**
1. Heartbeat продолжается и после `Tunnus hylätty` (401) — «независимо от прошлой ошибки»: если токен снова разрешат в ARGUS, панель подключится сама; раньше нужен был новый ключ.
2. Таймаут 30 с — у heartbeat; события, снимки, claim и reconcile остаются с 10 с и повтором с backoff.
3. «Hidas yhteys» (таймаут heartbeat) не переводит Lähetys в `Ei verkkoa` и не блокирует отправку событий: `Ei verkkoa` в Lähetys бывает только вместе с `Ei verkkoa` в Yhteys. Кнопка «Käynnistä» требует, как и раньше, состояния `Yhdistetty`.
4. Вторая панель не запускается совсем (а не «подключается к первой»): окно с номером процесса открытой панели.

## 0.4.8.1 — 2026-10-05

**Правка 1 шага 7 (`stage-5/step-7-delivery-reasons`), приоритет владельца 05.10: «Lähetysvirhe 2» без причины.** Контракт не менялся. Сервер ARGUS (`/api/health`, journal `argus20-api`, Caddy, `POST /api/collector/batches`, «Lähetä Selaimeen») — вне доступа сборщика (CLAUDE.md); со стороны сборщика каждый отказ теперь виден с id, кодом и словами, а `request_id` из ответа ARGUS связывает строку журнала сборщика с записью в журнале API.

**Что видно.**
- Lähetys: `Lähetysvirhe: 2 (lainaus ei vastaa lähdettä)` — число отказов и причина последнего словами (раньше — только `Lähetysvirhe: 2`); пока ARGUS отвечает 5xx — `Palvelinvirhe: 502` красным до первого прошедшего прохода (раньше при 5xx было видно только `Lähetetään`). Ответ без тела ошибки (страница прокси) — `HTTP-virhe 422 ilman syytä` / `Palvelinvirhe: <код>`.
- Журнал `delivery`: на каждый отклонённый элемент — `job <id> (<компания>): contact.observed event <event_id> seq <n> rejected <код> (<слова>)` или `evidence <id>`; на ошибку запроса — `job <id>: HTTP <статус> <код> (<слова>) request_id=<id>`; `evidence_missing` / `sequence_gap` (отправляются снова) — тоже строкой. Текст `detail` из ответа ARGUS в журнал не пишется: в нём может быть цитата с контактом.
- Yhteys: ответ 5xx на heartbeat — `Palvelinvirhe: 502` (раньше `Ei verkkoa: HTTP 502: <html>…</html>` — «нет сети» и сырой HTML страницы прокси); другой отказ — `ARGUS vastasi 403: <detail>` или `ARGUS vastasi 404: HTTP-virhe 404 ilman syytä`; `Ei verkkoa` — только когда ответа нет вовсе. Подсказка Keruu: `Keruu vaatii yhteyden ARGUSiin (Yhdistä)` (была ссылка на прежнюю кнопку «Testaa yhteys»).
- Журнал `http`: смена ответа heartbeat — `heartbeat: HTTP 200 answered` / `heartbeat: HTTP 401 <код> (<слова>) request_id=…` / `heartbeat: HTTP 0 offline (no answer from ARGUS)`; строка пишется только при смене, не каждые 30 с. Строки `claim: HTTP …` и `reconcile job …: HTTP …` — тоже с кодом, словами и `request_id`.
- `scripts\delivery_check.ps1 [-Minutes 30]` (или `python -m argus_collector.pilot rejected`): таблица всех отказов из локального outbox — время, компания, job, тип, event_id / evidence_id, seq, код, слова → `reports\rejected-<дата>.md`, и строки журнала за последние N минут об отказах, heartbeat, claim, reconcile.

**Исправлено.** Пакет событий, отклонённый целиком (4xx без ответа по событиям), помечал первое событие `rejected`, но не засчитывал отказ компании: `Lähetysvirhe` рос, а строка Jono причины не показывала. Теперь засчитывается и показывается.

**Модули.** Новые файлы: `pilot/rejected.py`, `scripts/delivery_check.ps1`. Изменены: `delivery` (service, loop, results, hooks, repository, contract, README), `scheduler` (hooks, views, collector), `ui` (queue_lines, connection_lines, app_connection), `scheduler/leases.py`, `pilot` (contract, `__main__`, README), `collector/messages/fi.json` (`delivery.errorReason`, `delivery.serverError`, `delivery.rejected.http`, `connection.state.refused`; `collecting.notConnected` — «Yhdistä»). Тесты: `delivery/tests/test_reasons.py`, `scheduler/tests/test_rejected_reason.py`, `pilot/tests/test_rejected.py`, `ui/tests/test_connection_lines.py`, дополнения `ui/tests/test_queue_lines.py`, `ui/tests/test_ui_connection.py`, `ui/tests/test_ui.py`.

**Решения (поправь, если не так).**
1. Срочная правка доставки — 0.4.8.1; правка Ellego (извлечение до навигации, детектор цикла, параллельные вызовы) — следующей версией 0.4.8.2, тоже в cv0.4.8.
2. Название компании пишется в строку отказа журнала: это не значение контакта; значения контактов, цитаты и токены в журнал не попадают.

## 0.4.8.0 — 2026-10-05

**Шаг `stage-5/step-7-routing`: разбор живого обхода Beckhoff (MAIN-PC, 05.10), тайминг по фазам и маршрутизация моделей (решения владельца 05.10.2026).** Контракт не менялся.

**Что видно.**
- Beckhoff (`beckhoff.com/en-en/company/global-presence`): обход идёт Global presence → «Beckhoff Worldwide» → Finland → `/fi-fi/` → Yhteystiedot (раньше — Global presence → Germany → `/de-de/`). Вкладка «Germany», открытая по умолчанию, — раздел страны DE: её офисы уходят с `extra:country DE` (Muut maat), не в шапку компании. Финский офис — телефон, email, `extra` название/адрес/факс/страна FI; люди с `/fi-fi/`, двое из JSON-LD без модели.
- Пока seed не местная версия, элементы с другой страной (`Germany`, `/de-de/`, `Deutsch`) не предлагаются модели; после того как достигнута `/fi-fi/`, не предлагаются и другие языковые версии (`/en-en/`).
- Resurssit: строка `Reititys: säännöt ensin · navigointi qwen2.5:7b · kuvakaappaus qwen2.5-vl:7b` (не скачанная модель — `puuttuu`, жёлтым).
- В журнале — строка на каждое состояние страницы: `browser: job <id>: timing <url> load= snapshot= extract= cards= bind= record= action= total= decide=<кто выбрал шаг> reader=<кто читал карточки>`; у доставки — `... in N ms` для пакетов событий и снимков.
- `scripts\walk_timing.ps1 [-Log <файл>]` (или `python -m argus_collector.pilot timing --log ...`) → `reports\timing-<дата>.md`: фазы, «кто решал» (правила / каждая модель / кэш / резерв), вызовы моделей (модель, назначение, мс, токены), доставка — по компаниям. Лог до 0.4.8.0 тоже читается (видны вызовы моделей и время между страницами).

**Маршрутизация (владелец 05.10.2026).**
1. Правила без модели: структура (страна выставки в списке стран; закрытый «Worldwide» / «Global presence», пока страны выставки на странице нет; вкладки отделов), затем ссылки: версия страны выставки (`Finland`, `/fi-fi/`), поиск страны (`Global presence`), контакты по своим словам (`Yhteystiedot`, `Contact`, `Kontakt`, `Johto`; бонус `/fi/` не считается). Кэш меню: выбор модели для того же набора ссылок повторяется, пока выбранная не посещена.
2. Навигация — `model.navigation` (`qwen2.5:7b`); если её нет или она падает — карточная модель до конца прогона.
3. Карточки людей — `model.name` (14b) только когда JSON-LD (`schema.org Person`) и правила не прочли людей: страница без канала, который может быть личным (не общий ящик, не vaihde, не блок офиса страны), и не страница контактов — пропуск; тот же текст на другом URL — повтор найденного.
4. VL (`model.vision`, `qwen2.5-vl:7b`) — только по скриншоту: проверка «не бот» с одним признаком (DOM требует двух) — модель отвечает, проверка ли это; если да — ожидание 20 с и Huomio, как обычно (VL проверку не проходит и не кликает); страница без DOM-текста — шаг по скриншоту и списку элементов. Полей контактов со скриншота не берётся (у поля должна быть цитата из текста страницы).
5. Каждый вызов — `model.called` с именем модели и purpose (`walk.vision` → `vision`).
6. `install_model.ps1` докачивает `qwen2.5:7b` и `qwen2.5-vl:7b`, ставит `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=3` (пользовательские переменные, перезапуск Ollama); не скачалась 7b или VL — предупреждение, не остановка.

**Готовность страницы.** После загрузки / клика ожидание «тихого» DOM (300 мс без изменений, не дольше 800 мс) один раз вместо фиксированных 2 × 800 мс; повторное ожидание — только после прошедшей проверки «не бот» или ответа на cookie-баннер.

**Модули.** Новые файлы: `walk/rules.py`, `walk/cards.py`, `walk/vision.py`, `walk/timing.py`, `extraction/jsonld_people.py`, `pilot/timing.py`, `pilot/timing_render.py`, `ui/route_lines.py`, `scripts/walk_timing.ps1`. Изменены: `walk` (decide, structure, page, runner, state, service), `browser` (session, page_tools, scripts, service), `extraction` (sections, contract), `discovery` (countries, country_names, contract), `models` (service, contract), `scheduler` (runner, service, views, contract), `delivery` (loop, results), `pilot` (contract, `__main__`), `ui` (app, app_collect, app_walk, service), `runtime` (Config), `scripts/install_model.ps1`, `config.example.yaml`. Фикстура `test_site/sites/beckhoff` + `gold/beckhoff.json` (субагент), `collector/tests/fake_model_server.py` (части с картинкой, имя запрошенной модели, `missing`). Тесты: `walk/tests/test_rules.py`, `test_cards_routing.py`, `test_vision_routing.py`, `test_walk_beckhoff.py`, `pilot/tests/test_timing.py`, `extraction/tests/test_jsonld_panels.py`, `models/tests/test_images.py`, `ui/tests/test_route_lines.py`, дополнения `discovery`/`runtime`, `test_site/tests/test_beckhoff*.py`.

**Решения (поправь, если не так).**
1. Карточная модель — прежняя `qwen2.5:14b-instruct` (то же семейство, что `qwen2.5:14b` в решении; уже скачана на MAIN-PC, перекачивать ~9 ГБ не нужно). Имя VL — как в решении, `qwen2.5-vl:7b`; если в библиотеке Ollama оно другое, `install_model.ps1` предупредит, сборщик работает без VL.
2. Офисы открытой вкладки другой страны (Germany) отправляются с `extra:country DE` (для «Muut maat»), а не выбрасываются: они на странице, не «обход другой страны».
3. Кэш меню хранит только переходы по ссылкам (повтор клика мог бы зациклиться); на фикстурах он не сработал ни разу — оставлен, его доля видна в отчёте тайминга.
4. Параллельную доставку не делаю: поток доставки и так отдельный, обход его не ждёт (фаза `record` — до 30 мс на страницу); `... in N ms` в журнале покажет, нужна ли она для скорости появления данных в ARGUS.
5. Параллельные вызовы 14b (карточки) и 7b (шаг) на одной странице (`OLLAMA_NUM_PARALLEL=3`) — следующим шагом после замера на MAIN-PC: нужно разнести запись вызова в SQLite и сам HTTP-вызов по потокам.

## 0.4.7.0 — 2026-10-05

**Шаг `stage-5/step-6-pairing`: паринг в один клик (решение владельца 05.10.2026) и поля `extra` по `docs/ANSWERS_S5.md` (ответы ARGUS на вопросы STAGE5_REPORT §T2.9, решения владельца 05.10.2026; файл положен как есть из `GridexOy/gridex-argus20` `main` 8c0279c, blob d8b6c3d).** Контракт (`docs/ARGUS20_COLLECTOR_OPENAPI.json`) не менялся.

**Что видно.**
- Блок Yhteys: вместо трёх полей (адрес, worker_id, токен) и «Testaa yhteys» — одно поле «Paritusavain» и кнопка «Yhdistä» (или Enter). В поле вставляется строка из ARGUS `argus://pair?url=…&worker=…&token=…`; панель её разбирает, сохраняет (адрес и worker_id — `worker_connection.json`, токен — DPAPI `worker_token.bin`), сразу шлёт heartbeat и показывает `Paritettu: <адрес> · <worker_id> · tunnus ****abcd` и `Yhdistetty`. Поле замаскировано, не заполняется и очищается сразу после нажатия.
- При каждом следующем запуске панель подключается сама (`Tarkistetaan…` → `Yhdistetty`); пока ARGUS недоступен — `Ei verkkoa: …`, heartbeat повторяется каждые 30 с; `Tunnus hylätty` останавливает повторы до нового ключа.
- Неверный ключ — красная строка `Paritusavain ei kelpaa: …` (не тот формат, нет url/worker/token, поле дважды, пробелы или управляющие символы, не https), ничего не сохраняется и не отправляется; прежний паринг остаётся.
- Значения по умолчанию пустые: в `config.example.yaml` и в `runtime.Config` больше нет адреса ARGUS (`argus.base_url` убран; в старом `config.yaml` этот ключ просто игнорируется). Адреса стенда в коде сборщика нет: адрес приходит только из ключа.
- Контракт-сервер при старте печатает ключ паринга на каждый токен: `pairing key worker-main-pc: argus://pair?url=http%3A%2F%2F127.0.0.1%3A8900&worker=worker-main-pc&token=test-token-abc`.
- В ARGUS (ANSWERS_S5 §2–3): страна, отдел, название и адрес офиса и факс приходят только как `field="extra"` с `extra_label` = `country` / `department` / `office_name` / `address` / `fax`, с цитатой (`quote`) и locator; строка field audit — `disposition: "extra"`, `reason` = тот же ключ (страна теперь тоже в аудите). Факс больше не выбрасывается: он идёт как `extra` `fax` у офиса страны (или у общих каналов компании), телефоном не становится. Контракт-сервер отклоняет `country` и т. п. как прямое поле и `extra` без `extra_label` (`invalid_input`).
- Известные контакты (ANSWERS_S5 §1): `KnownContact.fields` — ключ = имя поля (extra — по метке: `country`, `department`, `office_name`, `address`), значение — строка или список строк (первый — основной); так их читает сборщик и так их теперь отдаёт контракт-сервер (адреса в нижнем регистре). Без `observation_id` в ответе ARGUS `changed` уходит без `supersedes_observation_id` (поле в контракте допускает null).

**Как работает.** `worker_auth.parse_pairing_key` (чистая функция): схема `argus`, действие `pair`, значения percent-decoded, `+` остаётся `+` (токены base64), каждое поле ровно один раз и без пробелов/управляющих символов; `url` — http(s) с хостом, http только для этой машины (127.0.0.1 / localhost / ::1 — стенд), хвост `/api/collector` снимается. `ui.app_connection.pair` → `save_pairing` → heartbeat; `start_if_saved` при запуске; ответы для заменённого ключа отбрасываются. `walk.sink.EXTRA_FIELDS` + `AuditEntry.extra_label`; `scheduler.events.observation` ставит `field="extra"` и `extra_label`, `field_audit` — `extra` с `reason`; `scheduler.history` читает известные поля по имени (строка / список строк / объекты). Стенд: `identity.field_name` (у `extra` — метка) в истории и known_contacts, `known.fields_of` в форме ANSWERS_S5 §1.

**Модули.** Изменены: `ui` (connection_lines, view_connection, app_connection, view, app), `worker_auth` (service, contract), `runtime` (Config без адреса ARGUS), `extraction` (вид канала `fax`, JSON-LD `faxNumber`, роль факса — общий канал компании), `walk` (sink, findings, offices, contract), `scheduler` (events, history), `contract_server` (server — ключ паринга; contacts — правило extra; identity, history — поле `extra` по метке; known — форма ANSWERS_S5 §1). Документ: `docs/ANSWERS_S5.md` (как есть). Тесты: `worker_auth/tests/test_pairing_key.py`, `ui/tests/test_ui_connection.py` (вставка ключа, автоподключение при запуске, неверный ключ, отклонённый токен, ARGUS недоступен), `scheduler/tests/test_extra_fields.py`, `contract_server/tests/test_extra_rule.py`, правки тестов факса и страны.

**Решения (поправь, если не так).**
1. Порядок «разобрал → сохранил → подключился» (как в задании): ключ сохраняется до ответа ARGUS, поэтому при `Ei verkkoa` панель сама подключится позже; при `Tunnus hylätty` ключ остаётся сохранённым, но повторы останавливаются до нового ключа.
2. `url` в ключе — адрес ARGUS без `/api/collector` (с ним тоже принимается). Нешифрованный http — только для этой машины: токен не уходит открытым текстом по сети.
3. `raw_value` и `quote` у `extra` — текст источника (заголовок раздела, вкладка, строки адреса, номер факса как напечатан; у страны из `<html lang>` — значение атрибута, locator `dom html[lang]`), `normalized_value` — ISO-код / нормализованный текст / E.164 (как в примерах ANSWERS_S5).
4. Факс вне раздела страны — общий канал компании (`organization_channel`, binding `caption`: подпись «Fax» и есть заголовок).
5. Коммита `04022ca` в `GridexOy/gridex-argus20` нет; файл взят из `main` на 8c0279c (первая попытка — на 4ac8e0f — файла ещё не было), blob d8b6c3d. Из репозитория ARGUS прочитан только этот файл (частичный клон без содержимого, один blob). В `docs/KIT_MANIFEST.md` (документ ARGUS) не вносил.
6. «Avaa työselain» в Resurssit по-прежнему открывает тестовый сайт (TZ_SELAIN, S2) — это не адрес ARGUS и не трогался.

**Найдено живой проверкой.** В смотровом виде контракт-сервера (`/_stand/.../contacts`) не было `extra_label` — добавлен.

## 0.4.6.0 — 2026-10-05

**Шаг `stage-5/step-5-a5-pilot`: пара 5 TZ_TANDEM «Пилот» (A5) — подготовка сборщика.** Сам пилот (8 компаний Sähkö-Electricity 2027 против прода ARGUS на MAIN-PC, `owner_known_url` для Schneider / Prysmian / Phoenix Contact) — действие владельца и сессии ARGUS (B2–B4 на проде); в контейнере не проводился.

**Что видно.**
- Cookie-баннеры отвечаются автоматически (TZ_SELAIN §8.5): «только необходимые» (`Vain välttämättömät`, `Only necessary`, `Nur notwendige`, …), иначе «отклонить» (`Hylkää`, `Reject all`, …), «принять» — только если другого нет; ответ — один раз на хост, до чтения страницы (текст баннера в снимок не попадает). Строка состояния `Evästeilmoitus: valittiin «Nur notwendige»`, журнал `browser: cookie banner on <host>: necessary (…)`, в `coverage.scope_description` — `cookie banners answered (<host>: necessary)`.
- Отчёт пилота со стороны сборщика: `scripts\pilot_report.ps1 [-Batch <id>]` (или `python -m argus_collector.pilot`) пишет `%LOCALAPPDATA%\Gridex\ArgusCollector\reports\pilot-*.md`: по компании — результат и причина, активное и полное время, страницы, действия, вызовы модели (число, токены, секунды), люди, каналы, `published_direct` среди событий, оценённых ARGUS; порог ≥ 50 % компаний с человеком, чей канал не `inferred`/`stale`; 10 случайных телефонов — хост снимка в `approved_hosts`, цитата на своём месте в снимке.

**Модули.** Новый: `pilot` (README, contract, service, repository, render, `__main__`, tests). Изменены: `browser` (`page_tools.py` — кандидаты, проверка «не бот», ответ на cookie-баннер; `scripts.py` — `CONSENT_JS`; `service.consent_choice`), `walk` (`checkpoint.consents`, шаг `consent`), `scheduler` (`job_facts`, scope с cookie-ответами), `delivery` (`run_results`, `local_evidence_id`), `ui` (строка шага), `messages/fi.json`; `test_site/sites/vogel/index.html` — баннер в духе Cookiebot (`Alle akzeptieren` / `Nur notwendige` / `Einstellungen`); `pyproject.toml` — слой `ui | pilot`, новые внутренние файлы шагов 3–5 закрыты import-linter'ом.

**Решения (поправь, если не так).**
1. При баннере только с «принять» сборщик принимает (TZ: «автоматически, предпочтение необходимым») и фиксирует это в журнале и в scope; баннер без понятных кнопок не трогается (если перекрывает клик — gap как раньше).
2. Метрики ARGUS (Gold P · R, Nimetty henkilö, Soitettavia, сравнение с серверной лестницей) отчёт сборщика не считает — это экран Soittolista и отчёт ARGUS; сборщик даёт свои таблицы для `ARGUS20_COLLECTOR_STAGE6_REPORT.md`.
3. `ARGUS20_COLLECTOR_STAGE6_REPORT.md` пишется после пилота (сейчас данных нет, демо-цифры не ставлю); порядок пилота — в `ARGUS20_COLLECTOR_STAGE5_REPORT.md`, раздел пары 5.

## 0.4.5.0 — 2026-10-05

**Шаг `stage-5/step-4-a4-history`: пара 4 TZ_TANDEM «История и полнота» (A4) и сокращение паузы по решению владельца 05.10.2026.**

**Что видно (в ARGUS / контракт-сервере; в панели — те же Jono / Lähetys).**
- Повторный пакет той же компании (`rerun_reason`): тот же человек приходит как `reconfirmed` — строк в ARGUS не прибавляется, `last_seen_at` — сегодня; изменённое поле — `changed` со ссылкой на прежнее наблюдение (`supersedes_observation_id`); человек, которого на сайте больше нет, — `contact.freshness` `not_seen_in_checked_scope` («Ei löytynyt tarkistetusta laajuudesta»), контакт остаётся.
- `job.finished`: `freshness_summary` = счёт проверок; `coverage.basis` / `expected_count` / `found_count` (каталог с заявленным размером — `catalog_total`, найдены все — `verified_against_catalog_total`); `scope_description` — страницы, состояния, хосты, открытые вкладки/разделы, заявленный размер, остаток frontier и число gaps.
- Gap на каждую непройденную ветвь: кончился бюджет — каждая оставшаяся релевантная ссылка `budget_reached` (возобновляемо); три сбоя подряд — `no_progress`; релевантная ссылка на хост того же бренда вне `approved_hosts` (`ledvance.fi` рядом с `ledvance.com`) — `domain_ownership_unresolved` (не возобновляемо, владелец может внести `owner_known_url`).
- «Pysäytä» из ARGUS исполняется после текущей страницы: состояние `paused` приходит в ответе на каждый пакет событий (обход шлёт их после каждой страницы), heartbeat для этого больше не нужен; команда по-прежнему подтверждается в heartbeat (`applied`).

**Как работает.** `scheduler.history`: известные контакты из claim (форма `fields` в контракте открыта — читаются строка, список, объект с `value`/`observation_id` и список объектов); человек сопоставляется по нормализованному имени, офис/общий канал — по телефону или почте; значение = известному → `reconfirmed`, другое значение известного поля → `changed` + `supersedes`, иначе `new`. `scheduler.freshness`: в конце прогона — по проверке на каждое поле каждого известного контакта, из наблюдений задания (checkpoint), с evidence наблюдения; события по ≤ 50 проверок перед `job.finished`. `walk.coverage`: заявленный размер каталога, gaps внешних ссылок бренда; `walk.state.gap_unwalked`; `walk.actions` — выполнение действий вынесено из `runner.py`.

**Модули.** Новые файлы: `scheduler/history.py`, `scheduler/freshness.py`, `walk/coverage.py`, `walk/actions.py`. Изменены: `scheduler` (events, sink, runner, finish, hooks, repository), `walk` (state, decide, page, runner, sink). Тесты: `scheduler/tests/test_history.py`, `test_collector_history.py` (повтор → reconfirmed без новых строк; вариант фикстуры без Pekka Salo → not_seen, контакт на месте), `test_collector_control.py::test_pause_takes_effect_after_the_current_page_without_a_heartbeat`, `walk/tests/test_coverage.py`.

**Решения (поправь, если не так).**
1. Формат `KnownContact.fields` контракт не фиксирует; сборщик читает все разумные формы, контракт-сервер отдаёт `{поле: [{value, raw_value, observation_id, observed_at}]}` — вопрос Архивариусу: какой формат отдаёт B4.
2. `not_seen_in_checked_scope` — только при исчерпанном frontier (`coverage.frontier_status=exhausted`); прогон, закончившийся бюджетом, отменой или сбоями, даёт `not_checked`.
3. `changed` для поля с несколькими значениями (телефоны) — когда ни одно известное значение на странице не встретилось; новое значение рядом с подтверждённым — `new`.
4. Gap на «непройденную ветвь» — только для релевантных ссылок (`discovery.strong_link`: контакты, команда, версия страны); слабые ссылки (продукты, новости) gap не дают, но входят в `scope_description` числом.
5. Заявленный размер каталога берётся только со страницы, где найдены люди, и только если он не меньше найденного там.

## 0.4.4.0 — 2026-10-05

**Шаг `stage-5/step-3-a2-country`: дополнение владельца к A2 от 05.10.2026, пп. 1–5 (страна выставки, вкладки отделов, проверка «не бот»).** S5 (cv0.4.3.1) принят владельцем 05.10.2026; тег `v0.4.3` поставлен локально на `b700d40` (отправить его не даёт git-прокси сессии — см. отчёт).

**Что видно.**
- Keruu: на международной странице контактов со списком стран (аккордеон, вкладки, выпадающий список, ссылки ≥ 3 стран) открывается только страна выставки; строка состояния — `Napsautetaan: Finland`. Обход идёт по ссылке на местную версию (`/fi-fi`, `/fi`, `fi.` домен), остальные страны не обходятся.
- Проверка «не бот» без клика (JS-заглушка Cloudflare / WAF): обход ждёт до 20 с; не прошла — строка `Selaintarkistus ei päästänyt läpi: <url> — katso Huomio`, в Jono `Tarvitsee huomiota` (не `Epäonnistui`).
- Новый блок **Huomio** (TZ_SELAIN §5.1, виден только при задании в `needs_attention`): `Tarvitsee huomiota: <компания> — selaintarkistus ei päästänyt läpi 20 sekunnissa: <url>`, кнопки «Avaa työselain» (рабочий браузер на этой странице; неактивна, пока идёт обход) и «Jatka käsin tehdyn toimen jälkeen» (задание идёт дальше с того же места). Пока рабочий браузер открыт, сборщик не начинает обход (один профиль).
- Страница людей с вкладками отделов: открываются все вкладки, продажи и маркетинг первыми, люди из каждой; у человека — отдел (заголовок группы или вкладка: Joakim Flakholm → `Johto`).
- Seed — уже версия страны выставки (`.fi`, `/fi/`, `fi.`): сначала она, затем версии других стран (malux.se); у людей оттуда — страна (`SE`) из `<html lang>`.

**Как работает.** `discovery.countries` (таблицы `country_names.py`): страна подписи (`Finland`, `Suomi`, `FI`), страна версии URL, «местный» seed, список стран (≥ 3), порядок отделов; `strong_link` — ссылки, мимо которых модель не может закончить обход (контакты, местная версия; при местном seed — переключатель на версию другой страны, «после»). `walk.structure` — правила до модели (TZ_SELAIN §8.4, guard-rails): страна выставки в списке стран (клик / выбор в списке / переход), все вкладки и свёрнутые разделы отделов на странице с контактами; каждое действие — один раз на URL и подпись (`checkpoint.acted`); другие страны списка модели не показываются и в frontier не попадают. `browser`: вкладки, заголовки аккордеона, выпадающие списки — кандидаты (`role`, `state`, `options`), действие `select`; кнопка без формы больше не считается «submit»; ожидание проверки «не бот» до 20 с (нужны два признака из трёх: заголовок, текст, элемент проверки; короткая страница). `extraction.sections`: разделы стран в тексте страницы (только при ≥ 3 странах), телефон в разделе — в формате его страны (`09-7422 3300` под Finland → `+358974223300`), строка с `Fax` / `Faksi` / `Telefax` — не телефон; строки названия и адреса офиса. `walk.offices`: офис раздела — одна сущность `office` (`country`, `office_name`, `address`, `phone`, `email`, binding `card` → `published_general`). `walk.context`: `department` (заголовок группы / вкладка карточки, цитата — текст заголовка перед именем) и `country` (заголовок раздела или регион `<html lang>`, locator `dom html[lang]`) у людей. `scheduler`: состояние `needs_attention` — событие `job.needs_attention` (gap `captcha` + counts), аренда продлевается, прогон не закрывается; «Jatka…» или `resume` из ARGUS → `queued`, обход продолжает с URL проверки, первым событием идёт `job.progress`.

**Найдено живой проверкой шага и исправлено до сдачи.**
1. `mailto:`/`tel:` из закрытых вкладок и разделов брались из HTML сразу: у Ledvance уходили почты 10 других стран (в шапку компании ARGUS как общие каналы), у Malux — почты людей скрытых вкладок как `unassigned_channel` (дубли людей). Теперь ссылки, которые браузер сейчас не показывает, не читаются; они берутся, когда вкладка или раздел открыты.
2. Общие каналы компании получают `country` (раздел страны или `<html lang>`), иначе шведский `Växel` Malux в ARGUS не отличить от финского `Vaihde`.
3. Пройденная владельцем проверка «не бот» оставалась в gaps `job.finished` — теперь gap снимается, когда страница открылась.
4. Панель выше экрана (с блоком Huomio — ~1250 px, кнопки Huomio за нижним краем): тело панели прокручивается, окно не выше экрана, строка версии всегда видна, при появлении Huomio панель прокручивается к нему.

**Модули.** Новые файлы: `discovery/countries.py`, `discovery/country_names.py`, `browser/scripts.py`, `extraction/sections.py`, `walk/structure.py`, `walk/entities.py`, `walk/offices.py`, `walk/context.py`, `ui/attention_lines.py`, `ui/view_attention.py`, `ui/app_browser.py`, `ui/view_scroll.py`. Изменены: `discovery`, `browser`, `extraction`, `walk`, `scheduler`, `ui`, `messages/fi.json`; `test_site/` (ledvance, malux, malux-se, варианты, проверка «не бот», `__PORT__`), `contract_server/` (история контактов компании, known_contacts, freshness, needs_attention — под пару 4).

**Решения (поправь, если не так).**
1. Факс по решению 05.10 не отправляется вовсе. FieldAudit требует учесть каждое контактное поле; факс распознаётся по подписи и контактным полем источника не считается (в аудит не попадает). Если нужен аудит `extra` с `extra_label=Fax` — поправь.
2. Страна у человека отправляется только с доказательством: заголовок раздела страны (text_span) или регион в `<html lang>` (`sv-SE`, locator `dom html[lang]`, цитата — значение атрибута). Язык без региона (`fi`) и домен страну не дают — ARGUS видит страну ещё по E.164.
3. Отдел — только из структуры страницы (заголовок группы перед карточкой, иначе вкладка); общие заголовки (`Yhteystiedot`, `Contact`), страны и названия компаний отделом не считаются. Отдел из должности не выводится.
4. «Не обходить другие страны» — для списков стран (≥ 3 стран на странице). Переключатель версий (`FI | SE`) — по фокусу: при местном seed другие версии идут после, иначе — как в 0.4.3.0 (третий язык вниз).
5. Свёрнутые разделы (не страны) раскрываются только на странице, где уже есть люди или каналы, не больше 12 на страницу.
6. Причина «не бот» — `captcha` (класс препятствия TZ_SELAIN §8.5; отдельного класса для JS-проверки в контракте нет).

## 0.4.3.1 — 2026-10-04

**Правка 1 шага `stage-5/step-2-a2-a3` — расхождения, найденные живой проверкой по тест-карте TZ_TANDEM §7 и TZ_SELAIN §13.5 стр. 5 (указание владельца: «расхождения исправь, не подгоняй»).**

**Чек-лист правки.**
1. Строка состояния Keruu после обхода задания оставалась на последней странице (`Ladataan sivua http://katsa-oy.localhost:8765/`) — теперь, как у локального теста, `Keruu valmis: N sivua, M yhteystietoa` по каждому заданию — **сделано**.
2. Причина `unresolved_access` в Jono была частным случаем (`sivustolle ei päästy (verkkotunnusta ei hyväksytty)`), а код покрывает любой неразрешённый доступ — теперь `pääsy sivustolle jäi ratkaisematta` — **сделано**.
3. ARGUS остановлен, а отправлять нечего: Lähetys показывал `Lähetetty`, хотя тест-карта §13.5 стр. 5 ждёт `Ei verkkoa`. Теперь heartbeat без ответа (HTTP 0) переводит Lähetys в `Ei verkkoa` и при пустом outbox; первый ответ после обрыва сразу отправляет ожидающее, не дожидаясь backoff (`Ei verkkoa` → `Lähetetään` → `Lähetetty`) — **сделано**.
4. Yhteys после неудачного heartbeat писал `Ei vielä heartbeatia`, хотя heartbeat были: теперь строка `Viimeksi: <время>` последнего ответа сохраняется, пока проверяется тот же worker — **сделано**.

**Модули.** `ui` (`app_collect`, `app_connection`, `app`), `delivery` (новый файл `results.py` — разбор ответа на пакет событий вынесен из `loop.py`, иначе файл > 200 строк), `scheduler` (`collector`), `walk` (`contract` экспортирует виды событий). Новые тесты: `delivery/tests/test_link.py`, `ui/tests/test_queue_lines.py`, `ui/tests/test_ui_connection.py::test_argus_down_keeps_the_last_heartbeat_and_shows_ei_verkkoa`; `test_ui_collect` проверяет строку `Keruu valmis`.

**Решения (поправь, если не так).**
1. `Ei verkkoa` в Lähetys — только когда ARGUS не ответил вовсе (HTTP 0, как у самой доставки); ответ с кодом (401, 5xx) — это связь есть, его класс показывает доставка.
2. Слова Jono для команд ARGUS — по таблице i18n TZ_SELAIN §5: pause → `Tauolla`, cancel → `Keskeytetty`. В тест-карте TZ_TANDEM §7 стр. 3/5 (сторона ARGUS) — `Keskeytetty` для «Pysäytä» и `Peruttu` для «Peruuta»; это слова ARGUS, не панели сборщика — вопрос Архивариусу в отчёте.

## 0.4.3.0 — 2026-10-04

**Пары 2 и 3 из `docs/ARGUS20_TZ_TANDEM.md` 1.1 — шаги A2 «Пакет и контакты» и A3 «Надёжность и управление» одним шагом `stage-5/step-2-a2-a3` (указание владельца 04.10.2026), плюс дополнение владельца по стране выставки.** Прод `/api/collector` (B2/B3) ещё не принят; сборщик проверен против своего `contract_server/`, который теперь реализует весь контракт и проверяет каждый запрос по OpenAPI.

**Что видно в панели (только блоки TZ_SELAIN §5.1).**
- Keruu: «Käynnistä» включает сбор заданий ARGUS (`collecting=true`): claim с `max_jobs` = свободные слоты (≤ 8), обход по одному заданию, Chrome сам открывает сайт компании. Активна при модели, Chrome, рабочей связи (Yhteys) и без STOP; подсказка говорит, чего не хватает (`Keruu vaatii yhteyden ARGUSiin (Testaa yhteys)`). «Pysäytä» останавливает обход и claim, outbox продолжает отправку. Ручной режим остался: поле «Yrityksen verkkosivu» + кнопка «Testaa paikallisesti» (или Enter), подпись «Paikallinen testi — ei lähetetä ARGUSiin».
- Jono: `Ladataan…` / `Jonon lataus epäonnistui` / `Ei tehtäviä` / таблица Yritys · Vaihe (`Odottaa` / `Selain käsittelee` / `Viimeistellään`) · Henkilöt · Kanavat · Lähteet · Tila (`Valmis` / `Osittain valmis` + причина словами / `Epäonnistui` / `Keskeytetty` / `Tauolla` / `Pysäytetty` / `Odottaa yhteyttä ARGUSiin`); отказ ARGUS — словами в строке компании: `Hylätty N: verkkotunnusta ei ole hyväksytty`.
- Lähetys: `Odottaa lähetystä: N · Lähetysvirhe: N · p95 (1 min): X s` и `Lähetetty` / `Lähetetään` / `Ei verkkoa` / `Lähetys epäonnistui` (красным). Jono и Lähetys перечитывают локальную SQLite раз в секунду.

**A2 — как работает.** Задание из claim хранится локально целиком (`jobs`). `walk` в режиме задания: стартовый URL — `seed_urls`, хосты — только `approved_hosts` задания (K7 ред. 02: основание `seed`; seed, ушедший редиректом на другой хост, — gap `domain_ownership_unresolved`, с того хоста ничего не отправляется), бюджет прогона = политика минус израсходованное кампанией. На каждую новую страницу — снимок в `evidence_uploads` (`POST /evidence`: точные байты, sha256, canonical text) и `source.processed`; на каждого человека и общий канал — `contact.observed` (новые поля того же человека — `contact.enriched`) с `evidence_id`, locator `text_span` (или `json_pointer`/`dom` для JSON-LD и ссылок без видимого текста), `quote`, `entity_type`, `binding`, `extraction_status` и `field_audit` страницы (каждое найденное поле → `mapped` с id наблюдения, `dropped_contact_fields=0`). Привязка — по DOM: имя и значение в одной небольшой карточке без других людей → `card`/`table_row` + `confirmed` (сервер даёт `published_direct`), только близость → `proximity_only` + `ambiguous` (`inferred`). Канал без человека: общий ящик, строка «Vaihde/Tel.», JSON-LD → `organization_channel` (`published_general`); строка с «office/toimisto» → `office`; прочее → `unassigned_channel` (`inferred`). Событие и запись outbox — одна транзакция SQLite с локальной строкой `observations`. Поток доставки: сначала снимки, потом события run'а по seq, ≤ 50 событий или 2 с, наблюдение не уходит раньше своего снимка. `job.finished`: `run_result_status`, `completion_reason`, `coverage` (`confirmation=unverified`, `basis`, `scope_description`, `found_count`, `gap_count`), gaps, checkpoint с frontier, budget, модели по назначению. `model.called` — на каждый вызов: токены, мс, `cost_eur=0`, `local=true`.

**Страна выставки (дополнение владельца).** `scope.priority_countries`/`priority_languages` → фокус обхода: ссылки на версию сайта для страны/языка (`Suomi`, `/fi/`, `?lang=fi`) и на местный офис (`Finland office`, `Suomen toimisto`, города) поднимаются в ранжировании; у компании без офиса в стране — родной язык сайта и английский, вверх идут export / Nordic / Scandinavia / international sales и marketing; третий язык — вниз. Модель получает то же правило в запросе действия (`FOCUS: …`); пока непосещена сильная ссылка (контакты/команда/страна, вес ≥ 10), модель не может закончить обход. Регион телефона — по странице (ccTLD, `lang` с регионом, путь `/fi/`, язык страницы), иначе страна выставки: немецкий `0711 123 4500` → `+497111234500`.

**A3 — надёжность и управление.** Перезапуск панели: задания, run, seq, checkpoint (посещённое, frontier, люди, id наблюдений), outbox и команды — в SQLite; прерванный обход продолжается с последней страницы, дублей нет (стабильные id). Обрыв сети: обход идёт, доставка `Ei verkkoa` с backoff, после связи — всё по порядку. Истечение аренды (локально по `lease_expires_at` или `expired`/`mismatch` в heartbeat, или 409 `lease_*` на отправке): новые действия прекращаются, `reconcile` → `resume` (тот же run и seq) или `drain_only` (только слив). Команды из ответа heartbeat: pause / resume / cancel / continue исполняются (cancel → `job.finished` `cancelled`/`manual_cancel`, если run начат) и подтверждаются в следующем heartbeat (`command_id` в acks; повтор — `already_applied`). «Pysäytä» и файл `STOP` останавливают обход и claim; outbox продолжает. Журнал `<данные>/logs/collector-YYYY-MM-DD.log` с префиксами Lokit `http` / `browser` / `extraction` / `delivery` / `model`, без значений контактов и токенов, 14 дней.

**Модули.** Новые: `scheduler`, `delivery`, `collector/tests/contract/`. Изменены: `api_client` (весь рабочий набор операций, генератор), `walk`, `browser`, `discovery`, `extraction`, `normalization`, `evidence`, `storage` (миграция 2), `models`, `runtime`, `ui`, `contract_server/` (весь контракт), `test_site/` (nordtec, vogel, katsa), гейты `check_i18n`, `check_codegen`.

**Найдено и исправлено попутно.** `evidence` писал снимки через `write_text`: на Windows `\n` превращался в `\r\n`, и байты файла переставали совпадать со своим sha256 — теперь точные utf-8 байты. Гейт `check_i18n` принимал значения провода (`job.finished` в сгенерированном клиенте) за ключи панели — сгенерированный `api_client` исключён из проверки.

**Решения (поправь, если не так).**
1. A2 и A3 — один шаг ветки `stage-5/step-2-a2-a3` (название ветки — указание владельца), одна версия `0.4.3.0`: линия 0.4.x по TZ_TANDEM §11 п.4, «следующий свободный номер» (§3); ожидавшиеся 0.4.3.0/0.4.4.0 для A2/A3 сведены в одну, A4 получит следующий свободный номер. Правило CLAUDE.md №3 (версия = этап.шаг) здесь расходится с TZ_TANDEM §11 п.4 — принято TZ_TANDEM. Тег не ставлю (как и раньше — при согласии владельца, TZ_TANDEM §11 п.4: `v0.4.M`).
2. «Käynnistä» по TZ_TANDEM A2.1 — сбор ARGUS; ручной обход получил свою кнопку «Testaa paikallisesti» в своей строке (A1.5 оставляет ручной режим). «Keskeytä» по-прежнему неактивна (S5).
3. Человек отправляется и без канала (имя + должность, TZ_SELAIN §8.11; FieldAudit не позволяет молча терять поле): только имя — `ambiguous`; канал, раскрытый позже на той же странице, приходит как `contact.enriched`. Таблица панели по-прежнему показывает только людей с каналом (0.4.1.1).
4. Привязка — только по структуре DOM, не по группировке модели; без браузерной привязки поле — `ambiguous`.
5. Фокус страны меняет порядок обхода, а не фильтрует людей: все люди на пройденных страницах отправляются.
6. «finish» модели = релевантный frontier исчерпан (`frontier_status=exhausted`), но не раньше, чем пройдены сильные ссылки (guard ≥ 10); `confirmation` всегда `unverified`, пока нет total каталога.
7. Неудачное действие (таймаут, перекрытый элемент) — gap (`timeout`/`network_error`/`unsupported_widget`), обход продолжается; три подряд — конец (`partial`/`technical_failure`). Это меняет 0.4.1.2, где первый неудачный клик завершал обход.
8. `job.progress` — не чаще раза в 15 с; `source.blocked` — на каждый gap.
9. Jono показывает активные задания и изменённые за последние 24 ч.
10. Регион телефона без контекста страницы — страна выставки задания (не FI по умолчанию); у ручного обхода — FI, как раньше.
11. Контракт-сервер — stdlib, состояние в JSON (`--state`), не SQLite/FastAPI из TZ_SELAIN §2.1: стенду нужна только сохранность между перезапусками. Решения стенда, которых нет в ТЗ: токен завершённого run'а остаётся токеном слива (повтор `job.finished` — `duplicate`); `email_pattern` не канал и не проверяется по K7; случаи вне таблицы §9.4 → `inferred`.
12. Reconcile из потока доставки делается, только если токен, получивший 409, всё ещё текущий (иначе аренду уже обновил другой поток).

**Не проверено живьём на MAIN-PC.** Windows, настоящий Chrome, qwen2.5:14b на RTX 4090 и боевой `https://argus.gridex.fi/api/collector` (B2/B3 ещё не на проде). Проверено в Linux-контейнере: 387+ тестов (настоящая панель под Xvfb, Chromium, контракт-сервер, тестовый сайт, подмена модели), живой прогон панели — в отчёте `ARGUS20_COLLECTOR_STAGE5_REPORT.md`.

## 0.4.2.0 — 2026-10-04

**Пара 1 «Связь» из `docs/ARGUS20_TZ_TANDEM.md` (решение владельца 03.10.2026 — связать сборщик с ARGUS сейчас, не дожидаясь блока 5). Шаг A1, владелец дал «ок» 04.10.2026.** Прод `/api/collector` ещё не существует (параллельно его строит сессия ARGUS, шаг B1); до «ок» на пару 2 сборщик проверен против своего `contract_server/` на loopback — живая проверка против `https://argus.gridex.fi` будет сделана по факту готовности B1, токен внесёт владелец.

**Что видно.** Блок Yhteys — больше не заглушка: поля «ARGUS-osoite» (по умолчанию `https://argus.gridex.fi`), «Worker-tunnus», «Tunnus (token)» (поле только для ввода, никогда не показывает сохранённое значение целиком), кнопка «Testaa yhteys» → один heartbeat; состояния `Ei yhteyttä` / `Tarkistetaan…` / `Yhdistetty` / `Tunnus hylätty` (красным) / `Ei verkkoa: <деталь>` (красным); строка «Viimeksi: <время>» / «Ei vielä heartbeatia». Успешная проверка сохраняет адрес+worker_id (`worker_auth`, не секрет) и токен (DPAPI) и дальше шлёт heartbeat каждые 30 с, пока панель открыта — без повторного ввода при следующем запуске. Поле «Yrityksen verkkosivu» получило подпись «Paikallinen testi — ei lähetetä ARGUSiin»: ручной обход по-прежнему ничего не отправляет в ARGUS (контракт не примет наблюдения без задания — пары 2+).

**Новые модули.**
- `api_client` — генерируется из `docs/ARGUS20_COLLECTOR_OPENAPI.json` (`scripts/gen_api_client.ps1` → `scripts/gen_api_client.py`, логика в `scripts/codegen/`), не пишется руками (правило №14). Манифест операций — пока только `heartbeat` (`scripts/codegen/manifest.py`); остальные операции контракта (claim, evidence, events, reconcile, control, batches, статусы) относятся к парам 2+ и появятся там же, где понадобятся — расширением манифеста и перегенерацией, без переписывания вручную. Гейт `check_codegen` проверяет, что регенерация — no-op (`git diff` пуст).
- `worker_auth` — локальное хранение: `worker_connection.json` (адрес + worker_id, не секрет) и `worker_token.bin` (токен через DPAPI, `CryptProtectData`/`CryptUnprotectData`; вне Windows — запасной XOR только для тестов). `mask_token` показывает исключительно последние 4 знака (TZ_TANDEM A1.2), остального токена нигде нет — ни в логах, ни на экране.
- `contract_server/` — опорный тестовый сервер (стенд, не прод) с единственным эндпоинтом `POST /api/collector/workers/heartbeat`: реестр токенов в памяти (`test-token-abc` → `worker-main-pc` по умолчанию, `--token TOKEN:WORKER_ID` добавляет свои), проверка `schema_versions` (ожидает `1.1`), 401 `unauthorized` / 400 `invalid_input` / `schema_unsupported`, пустые `leases`/`commands` (заданий ещё нет). `python -m contract_server.server --port N` поднимает его отдельно от панели.

**Сетевой слой.** `network.proxy: system | direct` в `config.yaml` (по умолчанию `system`) решает, идут ли запросы к ARGUS через системный прокси Windows; loopback (127.0.0.1/localhost, т.е. `contract_server/` на этапе разработки) всегда напрямую независимо от настройки — иначе прокси отвечает 502 на локальный адрес (тот же случай, что и у локальной модели, коммит `6b6467b`).

**Живьём на MAIN-PC проверено:** `pytest` гоняет реальную панель (`tk.Tk()`, не заглушка) против реально поднятого `contract_server/` — «Testaa yhteys» с верным токеном даёт `Yhdistetty` и сохраняет связку, с неверным — `Tunnus hylätty` без сохранения токена (`collector/src/argus_collector/ui/tests/test_ui_connection.py`); отдельно руками через `install.ps1` → `scripts\start.ps1` → реальный `contract_server.server` на другом порту.

**По ходу работы найдены и исправлены три бага, не связанные с A1 напрямую, но вскрытые при его сборке:**
1. Гейт `import_linter` был тихим no-op: `python -m importlinter.cli lint_imports` молча импортирует модуль и ничего не проверяет (у `importlinter` нет `__main__.py`); настоящий вызов — `importlinter.cli.lint_imports_command()`. После починки гейт впервые реально заработал и сразу нашёл 3 предсуществующих нарушения слоёв в тестах (`walk` → `browser.session` напрямую, `ui.tests.test_ui` → `diagnostics.tests`/`runtime.service` напрямую) — все три исправлены (импорт `PageState` через `browser.contract`; `runtime.version_status` и `diagnostics`-фикстура `sample_document` стали доступны/локальны без захода во внутренности чужого модуля).
2. `subprocess.run(..., text=True)` без `encoding="utf-8"` в `scripts/gates/check_tools.py` и `check_codegen.py` падал с `UnicodeDecodeError` на этой (русской) кодовой странице Windows, если инструмент печатал что-то вне cp1251 (тот же класс ошибки, что и у `diagnose.ps1` в 0.4.1.1) — добавлен явный `encoding="utf-8", errors="replace"`.
3. `contract_server`: клиент, отправивший тело запроса без токена, иногда получал `ConnectionAbortedError` вместо ответа 401 — Windows рвёт TCP-соединение, если сервер закрывает его, не вычитав присланные байты. Обработчик теперь всегда вычитывает тело прежде, чем отклонить запрос.

**Решения (поправь, если не так).**
1. `worker_id` вводится владельцем в панели отдельным полем (третье поле рядом с адресом и токеном), а не только получается из токена: `HeartbeatRequest.worker_id` обязателен на проводе, а B1 ещё не описал формат самого токена настолько, чтобы полагаться на его внутреннюю структуру.
2. `api_client` генерируется только для операций из явного манифеста (сейчас — только `heartbeat`), а не для всего OpenAPI сразу: остальные операции относятся к парам 2–5 и будут не нужны до соответствующего шага — генерация «на будущее» без явной надобности противоречит правилу «не больше, чем требует задача».
3. `argus.base_url` в `config.example.yaml` теперь по умолчанию `https://argus.gridex.fi` (раньше — пустая строка): это и есть значение по умолчанию поля адреса в блоке Yhteys per TZ_TANDEM A1.2.
4. Токен, введённый в поле и провалившийся при проверке (`Tunnus hylätty` или сетевая ошибка), не сохраняется — остаётся прежний сохранённый токен (если был), чтобы одна опечатка не затёрла рабочую связку.

**Не проверено живьём:** реальный `https://argus.gridex.fi/api/collector` (сервер B1 ещё не существует) — тест-карта TZ_TANDEM §5 пп.1 и 3–4 (сторона ARGUS, Soittolista) требует сессии ARGUS и будет пройдена по факту готовности B1.

## 0.4.1.3 — 2026-10-03

**Падающий гейт `install.ps1` примерно в половине запусков.** `scripts\run_gates.py`/`pytest` внутри `install.ps1` несколько раз подряд падали на `test_panel_drives_a_real_walk_with_the_fake_model` с `_tkinter.TclError` (`invalid command name "tcl_findLibrary"` либо `couldn't read ... tk.tcl`) прямо на `tk.Tk()`, хотя тест зелёный в одиночку. Похоже на гонку Windows/Tcl при повторном создании `Tk()` в одном процессе вскоре после `destroy()` предыдущего окна (`test_ui.py` создаёт и уничтожает окно прямо перед этим тестом). Правка не трогает рантайм панели (`ui/contract.py` создаёт ровно один `Tk()` за процесс — там это не воспроизводится): новый `ui/tests/conftest.py::make_tk_root()` оборачивает `tk.Tk()` в короткий повтор (до 3 попыток, пауза 0.3 с) и используется в обоих местах, где тесты открывают настоящее окно (`test_ui.py`, `test_ui_walk.py`). Три подряд живых прогона `pytest -q` на MAIN-PC после правки — зелёные.

## 0.4.1.2 — 2026-10-03

**Живая проверка, продолжение.** Два дальнейших находа:

1. Три реальных сайта (ensto.com, abb.fi, phoenixcontact.fi) показали, что крупные корпоративные сайты почти всегда ставят cookie-баннер; модель иногда успевает пройти несколько страниц до него, но рано или поздно клик по перекрытому баннером элементу зависает до таймаута (10 с) — и это роняло весь обход в `Keruuvirhe`, даже если до того уже было найдено несколько контактов. Баннеры по-прежнему вне этого шага (решение №8 к 0.4.1.0, S3), но единичный неудачный клик не должен стирать то, что уже нашли. Исправление: `walk/runner.py::_walk` ловит `browser.ActionError` (новый реэкспорт `playwright.sync_api.Error` из `browser/contract.py`) вокруг `_perform` и завершает обход как обычный «Keruu valmis» с тем, что успели найти, вместо красной ошибки. Новый тест `test_walk_resilience.py::test_a_failed_click_ends_the_walk_cleanly_with_what_was_found` подменяет `_perform`, чтобы падать на втором шаге, и проверяет чистое завершение.
2. Тест `test_ui.py::test_window_renders_keruu_block_and_live_rows` был жёстко завязан на `"cv0.4.1.0 ("` — ломался при каждом поднятии VERSION. Исправлено на сравнение с реальным `runtime.current_version_status().file_version`.

Заодно: `walk/tests/test_walk.py` разросся сверх 200 строк (гейт `size`) — общие фикстуры (`site`, `gold`, `_settings`) вынесены в новый `walk/tests/conftest.py`, резистентный тест — в `walk/tests/test_walk_resilience.py`.

Живьём на MAIN-PC после этой правки проверено: обход тестового сайта — ровно 7 контактов (не 9), у всех оба канала, панель показывает `Malli: paikallinen (GPU)` и читаемую кириллицу в «Resurssit». Обход настоящих сайтов компаний подробно — в сдаче этапа, не здесь.

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
