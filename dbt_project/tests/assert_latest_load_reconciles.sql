-- Singular test: the latest successful batch's logged count must match
-- the rows actually sitting in raw for that batch.
with latest as (
    select batch_id, loaded_count
    from {{ source('raw', 'load_log') }}
    where status = 'SUCCESS'
    order by finished_at desc
    limit 1
),
actual as (
    select _batch_id as batch_id, count(*) as n
    from {{ source('raw', 'nyc_311_requests') }}
    group by 1
)
select l.batch_id, l.loaded_count, coalesce(a.n, 0) as actual_rows
from latest l
left join actual a using (batch_id)
where l.loaded_count <> coalesce(a.n, 0)
