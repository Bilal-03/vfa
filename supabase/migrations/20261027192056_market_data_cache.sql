-- Market data only. Existing portfolio tables are intentionally untouched.
create table public.market_data_cache (
  symbol text not null check (length(symbol) between 1 and 25),
  category text not null,
  entry jsonb not null check (jsonb_typeof(entry) = 'object' and pg_column_size(entry) <= 1000000),
  last_accessed_at timestamptz not null default now(),
  primary key (symbol, category)
);
alter table public.market_data_cache enable row level security;
revoke all on table public.market_data_cache from public, anon, authenticated;
grant select, insert, update, delete on table public.market_data_cache to service_role;
create index market_data_cache_access_idx on public.market_data_cache (last_accessed_at);

create function public.bound_market_data_cache() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  perform pg_catalog.pg_advisory_xact_lock(64108912);
  delete from public.market_data_cache
    where symbol not in ('^NSEI', '^GSPC')
      and last_accessed_at < now() - interval '30 days';
  delete from public.market_data_cache
    where symbol in (
      select symbol from public.market_data_cache
      where symbol not in ('^NSEI', '^GSPC')
      group by symbol order by max(last_accessed_at) desc, symbol
      offset 100
    );
  return null;
end;
$$;
revoke all on function public.bound_market_data_cache() from public, anon, authenticated;
grant execute on function public.bound_market_data_cache() to service_role;
create trigger bound_market_data_cache
  after insert or update on public.market_data_cache
  for each statement execute function public.bound_market_data_cache();
