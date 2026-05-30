create table if not exists public.medinsight_chat_memory (
  session_id text primary key,
  messages jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.medinsight_chat_memory enable row level security;

drop policy if exists "Allow browser chat memory reads" on public.medinsight_chat_memory;
create policy "Allow browser chat memory reads"
on public.medinsight_chat_memory
for select
to anon
using (true);

drop policy if exists "Allow browser chat memory inserts" on public.medinsight_chat_memory;
create policy "Allow browser chat memory inserts"
on public.medinsight_chat_memory
for insert
to anon
with check (true);

drop policy if exists "Allow browser chat memory updates" on public.medinsight_chat_memory;
create policy "Allow browser chat memory updates"
on public.medinsight_chat_memory
for update
to anon
using (true)
with check (true);

create table if not exists public.medinsight_chat_cache (
  session_id text primary key,
  source_query text not null,
  query_embedding jsonb not null default '[]'::jsonb,
  cleaned_keywords jsonb not null default '[]'::jsonb,
  topic_terms jsonb not null default '[]'::jsonb,
  pubmed_query text not null default '',
  papers jsonb not null default '[]'::jsonb,
  retrieved_chunks jsonb not null default '[]'::jsonb,
  cached_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.medinsight_chat_cache
add column if not exists topic_terms jsonb not null default '[]'::jsonb;

alter table public.medinsight_chat_cache enable row level security;

drop policy if exists "Allow browser cache reads" on public.medinsight_chat_cache;
create policy "Allow browser cache reads"
on public.medinsight_chat_cache
for select
to anon
using (true);

drop policy if exists "Allow browser cache inserts" on public.medinsight_chat_cache;
create policy "Allow browser cache inserts"
on public.medinsight_chat_cache
for insert
to anon
with check (true);

drop policy if exists "Allow browser cache updates" on public.medinsight_chat_cache;
create policy "Allow browser cache updates"
on public.medinsight_chat_cache
for update
to anon
using (true)
with check (true);
