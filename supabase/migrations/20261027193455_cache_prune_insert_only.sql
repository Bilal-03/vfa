-- INSERT/UPSERT statements prune; simple access-time touches need no pruning lock.
drop trigger bound_market_data_cache on public.market_data_cache;
create trigger bound_market_data_cache after insert on public.market_data_cache
for each statement execute function public.bound_market_data_cache();
