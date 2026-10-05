# Ответы ARGUS на вопросы сборщика (STAGE5_REPORT §T2.9) — 05.10.2026

Контракт (`docs/ARGUS20_COLLECTOR_OPENAPI.json` 3.0.0, wire schema 1.1) **не меняется**; ниже — как в его рамках
передавать спрошенное. Ответы — решения владельца 05.10. Примеры — фрагменты событий `contact.observed`
(`POST /api/collector/jobs/{job_id}/events`); общие поля события (`event_id`, `seq`, `run_id`, …) опущены.

## 1. Точная форма `KnownContact.fields`

В контракте `fields` — объект без фиксированных ключей (`additionalProperties`). ARGUS заполняет его так:
**ключ = имя поля наблюдения** (те же строки, что сборщик шлёт в `Observation.field`), **значение = нормализованное
значение**, которое ARGUS хранит. Только ключи, у которых есть значение. Один `KnownContact` на человека:
если у него несколько телефонов или адресов, значение ключа — список строк, первый — основной
(`"phone": ["+358406326632", "+358208351662"]`); при одном значении — строка, как в примере.

```json
{
  "canonical_contact_id": "5b2f0c1e-8d4a-4c55-9f6e-2b1a7d3e9c10",
  "entity_type": "person",
  "fields": {
    "full_name": "Mika Sormunen",
    "job_title": "Myynti",
    "phone": "+358406326632",
    "email": "mika.sormunen@naficon.fi"
  },
  "last_seen_at": "2026-10-04T18:31:31Z",
  "channel_status": "published_direct"
}
```
Канал без человека — `entity_type: "organization_channel"`, `fields` с одним ключом (`email` или `phone`).
Ключи из §2 (`country`, `department`, `office_name`, `address`) попадают в `fields` тем же именем, если ARGUS
их хранит. Телефоны — E.164, адреса — в нижнем регистре.

**Состояние сервера на 0.4.21.0:** `ClaimedJob.known_contacts` пока всегда `[]` — список заполняется с пары 4
(B4, свежесть контактов, TZ_TANDEM §8). Форма выше — то, что придёт, когда он заполнится.

## 2. `country` / `department` / `office_name` / `address`

Отдельных полей с такими именами в контракте **нет**: `Observation.field` — свободная строка, а для данных, у
которых нет своего канала, в контракте уже есть механизм «extra» — наблюдение с `field: "extra"` и ключом в
`extra_label`, плюс строка `field_audit` с `disposition: "extra"`. Сборщик кладёт их так, ключи — ровно
`country`, `department`, `office_name`, `address`. ARGUS читает их в карточку компании / человека.

```json
{
  "entity_id": "ent-7",
  "entity_type": "office",
  "relationship": "company",
  "observations": [
    {"observation_id": "o1", "field": "extra", "extra_label": "office_name",
     "raw_value": "Helsingin toimisto", "normalized_value": "Helsingin toimisto",
     "extraction_status": "confirmed", "evidence_id": "ev-3", "binding": "card",
     "quote": "Helsingin toimisto", "locator": {"kind": "text_span", "start": 0, "end": 18, "text_sha256": "…"}},
    {"observation_id": "o2", "field": "extra", "extra_label": "address",
     "raw_value": "Lahdentie 7 D, 21660 Nauvo", "normalized_value": "Lahdentie 7 D, 21660 Nauvo",
     "extraction_status": "confirmed", "evidence_id": "ev-3", "binding": "card",
     "quote": "Lahdentie 7 D, 21660 Nauvo", "locator": {"kind": "text_span", "start": 0, "end": 26, "text_sha256": "…"}},
    {"observation_id": "o3", "field": "extra", "extra_label": "country",
     "raw_value": "Suomi", "normalized_value": "FI",
     "extraction_status": "confirmed", "evidence_id": "ev-3", "binding": "card",
     "quote": "Suomi", "locator": {"kind": "text_span", "start": 0, "end": 5, "text_sha256": "…"}},
    {"observation_id": "o4", "field": "extra", "extra_label": "department",
     "raw_value": "Myynti ja tekniikka", "normalized_value": "Myynti ja tekniikka",
     "extraction_status": "confirmed", "evidence_id": "ev-3", "binding": "card",
     "quote": "Myynti ja tekniikka", "locator": {"kind": "text_span", "start": 0, "end": 19, "text_sha256": "…"}}
  ],
  "field_audit": {
    "evidence_id": "ev-3",
    "items": [
      {"source_field": "Toimipiste", "disposition": "extra", "observation_ids": ["o1"], "raw_value": "Helsingin toimisto", "reason": "office_name"},
      {"source_field": "Osoite", "disposition": "extra", "observation_ids": ["o2"], "raw_value": "Lahdentie 7 D, 21660 Nauvo", "reason": "address"},
      {"source_field": "Maa", "disposition": "extra", "observation_ids": ["o3"], "raw_value": "Suomi", "reason": "country"},
      {"source_field": "Osasto", "disposition": "extra", "observation_ids": ["o4"], "raw_value": "Myynti ja tekniikka", "reason": "department"}
    ],
    "dropped_contact_fields": 0
  }
}
```
- `country` — `normalized_value` двухбуквенный ISO 3166-1 (`FI`, `SE`); `raw_value` — как на странице.
- Цитата (`quote`) обязательна и проверяется сервером так же, как у каналов: не найдена в снимке —
  `evidence_missing`.
- Тот же приём у человека (`entity_type: "person"`): например `department` рядом с `full_name` / `job_title`.

**Состояние сервера на 0.4.21.0:** такие наблюдения принимаются (событие проходит, `field_audit` полон), но
пока не записываются в карточку — запись `extra` в карточку стоит в очереди ARGUS отдельным шагом, до того
как сборщик начнёт их слать в проде. Контракт для этого не меняется.

## 3. Факс

Факс — **не канал**: наблюдение `field: "extra"`, `extra_label: "fax"`, значение — номер как напечатан (в
`normalized_value` — E.164, если сборщик его привёл). В телефоны / каналы контакта он не попадает и в
Soittolista не показывается; хранится как сведение карточки.

```json
{"observation_id": "o5", "field": "extra", "extra_label": "fax",
 "raw_value": "020 835 1699", "normalized_value": "+358208351699",
 "extraction_status": "confirmed", "evidence_id": "ev-3", "binding": "card",
 "quote": "Faksi 020 835 1699", "locator": {"kind": "text_span", "start": 0, "end": 18, "text_sha256": "…"}}
```
и строка `field_audit`: `{"source_field": "Faksi", "disposition": "extra", "observation_ids": ["o5"], "raw_value": "020 835 1699", "reason": "fax"}`.

**Состояние сервера на 0.4.21.0 — расхождение, которое ARGUS исправит:** сейчас наблюдение с
`field: "fax"` (не через `extra`) сервер принимает как телефон (`contact_events.CHANNEL_FIELDS`). Правило
владельца — факс в каналы не идёт; это исправляется в том же шаге очереди, что и запись `extra` в карточку.
Сборщику: слать факс только как `extra` / `fax`, как в примере, — тогда он и сейчас не станет телефоном.
