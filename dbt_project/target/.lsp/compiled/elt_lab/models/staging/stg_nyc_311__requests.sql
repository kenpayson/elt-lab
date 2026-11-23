-- STAGING: one clean, typed row per 311 request.
-- Raw is append-only, so the same request can appear in several batches
-- (e.g. Open on Monday, Closed on Friday). Keep the latest observation.

with successful_batches as (
    select batch_id
    from "warehouse"."raw"."load_log"
    where status = 'SUCCESS'           -- ignore rows from failed/partial loads
),

raw as (
    select r.*
    from "warehouse"."raw"."nyc_311_requests" r
    join successful_batches b on r._batch_id = b.batch_id
),

latest as (
    select
        *,
        row_number() over (partition by unique_key order by _loaded_at desc) as rn
    from raw
)

select
    cast(unique_key as bigint)                          as request_id,
    try_cast(created_date as timestamp)                 as created_at,
    try_cast(closed_date  as timestamp)                 as closed_at,
    upper(trim(agency))                                 as agency_code,
    trim(agency_name)                                   as agency_name,
    trim(complaint_type)                                as complaint_type,
    trim(descriptor)                                    as descriptor,
    trim(status)                                        as status,
    resolution_description,
    coalesce(nullif(upper(trim(borough)), ''), 'UNSPECIFIED') as borough,
    nullif(trim(incident_zip), '')                      as zip_code,
    try_cast(latitude  as double)                       as latitude,
    try_cast(longitude as double)                       as longitude,
    _batch_id                                           as batch_id,
    _loaded_at                                          as loaded_at
from latest
where rn = 1