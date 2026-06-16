-- 001_rls_policies.sql
-- FARO — Row Level Security Policies
-- No user authentication. Anonymous insert only. No public reads/updates/deletes.
-- Updates (report_generated, report_downloaded) must use the service role key.

-- Enable RLS
alter table faro_sessions enable row level security;
alter table faro_eval_runs enable row level security;

-- faro_sessions: anonymous insert only
create policy "faro_sessions: anon insert only"
  on faro_sessions for insert
  to anon
  with check (true);

-- faro_eval_runs: anonymous insert only
create policy "faro_eval_runs: anon insert only"
  on faro_eval_runs for insert
  to anon
  with check (true);
