-- Tables for the alert-triage results. Run once in the Supabase SQL editor.
--
-- The scored system (system/run) never touches Supabase. tools/publish_supabase.py
-- copies its finished output here so the UI and an audit trail can read it.

create table if not exists triage_runs (
  run_id           text primary key,          -- "<institution>-<first 12 hex of the output hash>"
  institution      text not null,
  created_at       timestamptz not null default now(),
  output_sha256    text not null,             -- hash of the output file the system wrote
  repeat_runs      int  not null default 0,   -- how many times the system was re-run to check it
  repeat_identical boolean,                   -- true when every re-run gave the same bytes
  cases            int  not null,
  closes           int  not null,
  rfis             int  not null,
  escalations      int  not null,
  seconds          numeric
);

create table if not exists triage_decisions (
  run_id      text not null references triage_runs (run_id) on delete cascade,
  institution text not null,
  case_id     text not null,
  alert_ids   jsonb not null,
  verdict     text not null check (verdict in ('CLOSE', 'RFI', 'ESCALATE')),
  reason_code text not null,
  reason      text not null,
  evidence    jsonb not null,
  primary key (run_id, case_id)
);

create index if not exists triage_decisions_verdict on triage_decisions (institution, verdict);

-- Public-source context for an MLRO looking at an escalation, fetched with Tavily.
-- The verdict never uses it. Only a country name is ever sent to Tavily.
create table if not exists mlro_context (
  topic      text primary key,                -- for example "country:Lebanon"
  fetched_at timestamptz not null default now(),
  list_date  date,                            -- publication date of the newest FATF list among the sources
  query      text not null,
  sources    jsonb not null,                  -- [{"list", "title", "url", "list_date", "snippet", "names_country"}]
  note       text not null
);
alter table mlro_context add column if not exists list_date date;

-- What the analyst did with a decision in the UI. History is never rewritten:
-- an undo is a new 'undone' row.
create table if not exists analyst_actions (
  id         bigint generated always as identity primary key,
  run_id     text not null references triage_runs (run_id),
  case_id    text not null,
  action     text not null check (action in ('closed', 'rfi_sent', 'escalated', 'escalation_taken', 'sent_back', 'undone')),
  note       text,
  created_at timestamptz not null default now()
);

-- The queue reads this view: the decisions of the newest run for each institution.
create or replace view latest_decisions as
select d.*
from triage_decisions d
join (
  select distinct on (institution) institution, run_id
  from triage_runs
  order by institution, created_at desc
) newest using (run_id);

-- Anyone with the anon key may read. Only the service role key may write.
alter table triage_runs      enable row level security;
alter table triage_decisions enable row level security;
alter table mlro_context     enable row level security;

drop policy if exists "read runs" on triage_runs;
drop policy if exists "read decisions" on triage_decisions;
drop policy if exists "read context" on mlro_context;
create policy "read runs"      on triage_runs      for select using (true);
create policy "read decisions" on triage_decisions for select using (true);
create policy "read context"   on mlro_context     for select using (true);

-- The UI may read analyst actions and add new ones. It may not change or delete them.
alter table analyst_actions enable row level security;
drop policy if exists "read actions" on analyst_actions;
drop policy if exists "add actions" on analyst_actions;
create policy "read actions" on analyst_actions for select using (true);
create policy "add actions"  on analyst_actions for insert with check (true);
