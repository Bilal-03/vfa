-- Atomically keep each newest successful field across local/cloud writers.
create function public.save_market_data_cache(p_symbol text, p_category text, p_entry jsonb)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare
  previous jsonb;
  merged jsonb;
  payload jsonb;
  quality jsonb;
  field text;
  old_meta jsonb;
  new_meta jsonb;
  chosen_meta jsonb;
  chosen_value jsonb;
  path text[];
begin
  perform pg_catalog.pg_advisory_xact_lock(64108912);
  select entry into previous from public.market_data_cache
    where symbol=p_symbol and category=p_category for update;
  previous := coalesce(previous, '{}'::jsonb);
  payload := coalesce(previous->'payload','{}'::jsonb) || coalesce(p_entry->'payload','{}'::jsonb);
  quality := coalesce(previous->'quality','{}'::jsonb) || coalesce(p_entry->'quality','{}'::jsonb);
  for field in select jsonb_object_keys(quality) loop
    old_meta := previous->'quality'->field;
    new_meta := p_entry->'quality'->field;
    path := string_to_array(field,'.');
    if old_meta is not null and (new_meta is null or coalesce(old_meta->>'fetched_at','') > coalesce(new_meta->>'fetched_at','')) then
      chosen_meta := old_meta;
      chosen_value := previous->'payload' #> path;
    else
      chosen_meta := new_meta;
      chosen_value := p_entry->'payload' #> path;
    end if;
    if chosen_value is not null and chosen_value <> 'null'::jsonb then
      payload := jsonb_set(payload,path,chosen_value,true);
      quality := jsonb_set(quality,array[field],chosen_meta,true);
    end if;
  end loop;
  if p_category='news' and jsonb_typeof(payload->'articles')='array' and jsonb_array_length(payload->'articles')>0 then
    payload := payload || jsonb_build_object('status','ready','count',jsonb_array_length(payload->'articles'));
  end if;
  merged := p_entry || jsonb_build_object('payload',payload,'quality',quality,
    'missing',(coalesce(previous->'missing','{}'::jsonb)||coalesce(p_entry->'missing','{}'::jsonb)) - array(select jsonb_object_keys(quality)));
  insert into public.market_data_cache(symbol,category,entry,last_accessed_at)
    values(p_symbol,p_category,merged,now())
    on conflict(symbol,category) do update set entry=excluded.entry,last_accessed_at=excluded.last_accessed_at;
  return merged;
end;
$$;
revoke all on function public.save_market_data_cache(text,text,jsonb) from public, anon, authenticated;
grant execute on function public.save_market_data_cache(text,text,jsonb) to service_role;
