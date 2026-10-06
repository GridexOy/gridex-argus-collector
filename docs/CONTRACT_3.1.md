# Контракт 3.1.0 (wire schema 1.2) — для команды сборщика

Дата 05.10.2026. Запрос владельца: два отказа `contact.enriched` (Beckhoff, seq 452; BCC, seq 10) ARGUS вернул как
`invalid_input` без причины. Теперь в ответе есть код, правило, наблюдение и поле, не прошедшее проверку.
Изменение обратно совместимо: воркер 1.1 продолжает работать как с 3.0.0.

## Что изменилось
- `ARGUS20_COLLECTOR_OPENAPI.json`: `info.version` 3.0.0 -> 3.1.0.
- Новая схема `RefusalDetail {rule, observation_id, field, message}`, все четыре поля обязательны
  (`observation_id`, `field` могут быть `null`).
- `EventResult.detail`: `RefusalDetail | null`, НЕ входит в `required`.
- Везде, где был `schema_version: "1.1"` (запросы событий, `EventsRequest`, `JobDefinition`), принимается "1.1" и "1.2".

## Согласование версии
Воркер перечисляет в `heartbeat.schema_versions` все версии, которые понимает. ARGUS поддерживает "1.1" и "1.2",
выбирает наибольшую общую и запоминает её для воркера. Нет общей версии -> 400 `schema_unsupported`.
- Согласована 1.2: в каждом результате `events` есть ключ `detail` (`null`, если событие принято или отказ без правила).
- Согласована 1.1 или heartbeat ещё не было: ключа `detail` в ответе НЕТ вообще, ответ побайтно как в 3.0.0.
Чтобы получать причины, воркер шлёт `["1.1","1.2"]` (или `["1.2"]`) и принимает `detail` в ответе.
Повторная отправка отклонённого `event_id` возвращает сохранённый `detail` (для 1.2).

## Пример ответа 1.2
См. `events.response.v1_2.json`. Фрагмент отклонённого результата:

```json
{"event_id": "evt-0002", "seq": 2, "status": "rejected", "code": "invalid_input",
 "canonical_contact_id": null, "server_revision": 2, "state_applied": false, "channel_status": null,
 "detail": {"rule": "person_without_name", "observation_id": "o3", "field": "email",
            "message": "observation o3 (email): a person observation without full_name in this event; enrichment needs the person's name"}}
```

## Правила (`detail.rule`)
| rule | код | смысл |
|---|---|---|
| `person_without_name` | invalid_input | в событии `entity_type=person`, но нет наблюдения `full_name`/`name` со значением; `field` — наблюдение, пришедшее без имени |
| `no_channel` | invalid_input | наблюдение — не канал (email/phone) и не человек: нечего записать |
| `channel_value_unreadable` | invalid_input | значение email/телефона не читается (телефон: нужен международный формат с `+`) |
| `snapshot_missing` | evidence_missing | снимок страницы отсутствует или повреждён (не записывается, повтор после загрузки; с 0.4.24.4) |
| `quote_not_found` | invalid_input | `quote` не найдена в тексте снимка |
| `value_not_in_quote` | invalid_input | в `quote` нет самого значения |
| `job_mismatch` | invalid_input | `job_id` события не равен заданию запроса (событие не записывается, повтор с правильным `job_id` пройдёт) |

`observation_id` и `field` — наблюдение события (`observation_id`, `field` из payload); для `job_mismatch` оба `null`.

## Вероятная причина Beckhoff / BCC
`contact.enriched` для известного человека должен нести `full_name` (правило приёма не менялось): без него
наблюдение email/phone/job_title человека отклоняется как `person_without_name`. Имя нужно слать в каждом событии,
а не только в первом `contact.observed`.

## Прежние примеры
Все существующие примеры (`events.response.json` и др.) остаются валидными для 1.1.

## 0.4.24.4
- Событие раньше своего evidence (нет строки evidence с этим `evidence_id`) принимается в ожидание: ответ `accepted` +
  `code: evidence_pending`, `state_applied=false`, `canonical_contact_id`/`channel_status` = null (1.2: `detail` null);
  `seq` расходуется (`last_contiguous_seq` растёт). Сервер применяет событие сам, когда evidence загружено (в том же
  запросе загрузки) — слать повторно не нужно; итог (accepted или отказ с кодом и detail) записывается в журнал событий.
  Повтор такого `event_id` отвечает `duplicate` + `evidence_pending`, пока событие ждёт. Ожидающие дольше 5 минут
  досчитываются фоновым процессом; если evidence нет 24 часа — окончательный `rejected` / `evidence_missing`
  (`snapshot_missing`). Снимок есть, но не читается: событие не записывается, `seq` не расходуется, повтор после
  загрузки — как раньше.
- Снимок есть, но `quote` или значение в его тексте не найдены (`quote_not_found`, `value_not_in_quote`) — окончательный
  `invalid_input` с `detail` (1.2: rule/field/observation_id). Событие записывается, повтор с тем же `event_id` получает
  тот же ответ. Исправленное наблюдение шлите с новым `event_id`.
- Старые записи журнала, где такой отказ был сохранён как `evidence_missing`: повтор того же `event_id` с тем же
  payload не переигрывается, а проверяется заново (без проверки `seq` — он уже учтён); строка журнала обновляется новым
  итогом (accepted, ожидание `evidence_pending` или отказ с кодом и detail), и сервер отвечает им.
- Истечение lease: задание возвращается в очередь (`queued`), в Lokit строка `delivery.lease_expired`. Heartbeat по такому
  заданию отвечает `expired` (даже если токен и generation совпадают); evidence/events со старым токеном получают
  409 `lease_expired`. Это и есть «job_expired»: возьмите задание заново через claim.
