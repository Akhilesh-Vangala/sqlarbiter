-- Apply once using the Supabase database owner. PostgreSQL 15+.
-- No service-role credential is used by the application.
begin;

create table public.sqlarbiter_projects (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (length(btrim(name)) between 1 and 80),
  created_at timestamptz not null default now(),
  unique (owner_id, id)
);

create table public.sqlarbiter_investigations (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid,
  parent_id uuid,
  title text not null check (length(btrim(title)) between 1 and 100),
  filename text not null check (length(filename) between 1 and 160),
  status text not null check (status in ('draft', 'completed')),
  source_sha256 text not null check (source_sha256 ~ '^[a-f0-9]{64}$'),
  contract jsonb not null check (octet_length(contract::text) <= 16000),
  profile jsonb not null check (octet_length(profile::text) <= 64000),
  source text check (octet_length(source) <= 400000),
  report jsonb check (octet_length(report::text) <= 350000),
  created_at timestamptz not null default now(),
  unique (owner_id, id),
  check ((status = 'draft' and report is null) or (status = 'completed' and report is not null)),
  foreign key (owner_id, project_id) references public.sqlarbiter_projects(owner_id, id),
  foreign key (owner_id, parent_id) references public.sqlarbiter_investigations(owner_id, id) on delete set null (parent_id)
);

create index sqlarbiter_projects_owner_time on public.sqlarbiter_projects(owner_id, created_at desc);
create index sqlarbiter_investigations_owner_time on public.sqlarbiter_investigations(owner_id, created_at desc);
create index sqlarbiter_investigations_project on public.sqlarbiter_investigations(owner_id, project_id);

alter table public.sqlarbiter_projects enable row level security;
alter table public.sqlarbiter_projects force row level security;
alter table public.sqlarbiter_investigations enable row level security;
alter table public.sqlarbiter_investigations force row level security;
revoke all on public.sqlarbiter_projects, public.sqlarbiter_investigations from public, anon, authenticated;
grant select, insert, delete on public.sqlarbiter_projects, public.sqlarbiter_investigations to authenticated;
-- Snapshots cannot be edited in place, including through direct REST calls.
create policy sqlarbiter_projects_read on public.sqlarbiter_projects for select to authenticated using (owner_id = (select auth.uid()));
create policy sqlarbiter_projects_insert on public.sqlarbiter_projects for insert to authenticated with check (owner_id = (select auth.uid()));
create policy sqlarbiter_projects_delete on public.sqlarbiter_projects for delete to authenticated using (owner_id = (select auth.uid()));
create policy sqlarbiter_investigations_read on public.sqlarbiter_investigations for select to authenticated using (owner_id = (select auth.uid()));
create policy sqlarbiter_investigations_insert on public.sqlarbiter_investigations for insert to authenticated with check (owner_id = (select auth.uid()));
create policy sqlarbiter_investigations_delete on public.sqlarbiter_investigations for delete to authenticated using (owner_id = (select auth.uid()));

-- Serialize each owner's inserts before enforcing storage quotas. These are
-- invoker functions: callers do not gain database-owner or cross-user access.
create function public.sqlarbiter_snapshot_quota() returns trigger language plpgsql
set search_path = pg_catalog, public as $$
declare record_count integer;
begin
  if new.owner_id is distinct from (select auth.uid()) then
    raise exception 'Owner does not match authenticated user' using errcode = '42501';
  end if;
  perform pg_advisory_xact_lock(hashtextextended(new.owner_id::text, 24017));
  if tg_table_name = 'sqlarbiter_projects' then
    select count(*) into record_count from public.sqlarbiter_projects where owner_id = new.owner_id;
    if record_count >= 20 then raise exception 'Project storage limit reached' using errcode = '23514'; end if;
  else
    select count(*) into record_count from public.sqlarbiter_investigations where owner_id = new.owner_id;
    if record_count >= 100 then raise exception 'Investigation storage limit reached' using errcode = '23514'; end if;
  end if;
  return new;
end;
$$;
revoke all on function public.sqlarbiter_snapshot_quota() from public, anon, authenticated;
create trigger sqlarbiter_projects_quota before insert on public.sqlarbiter_projects for each row execute function public.sqlarbiter_snapshot_quota();
create trigger sqlarbiter_investigations_quota before insert on public.sqlarbiter_investigations for each row execute function public.sqlarbiter_snapshot_quota();

commit;
