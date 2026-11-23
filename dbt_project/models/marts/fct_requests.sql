-- FACT: one row per request, with business-friendly measures.
select
    request_id,
    created_at,
    cast(created_at as date)                    as created_date,
    closed_at,
    agency_code,
    complaint_type,
    descriptor,
    status,
    borough,
    zip_code,
    latitude,
    longitude,
    closed_at is not null                       as is_closed,
    case
        when closed_at >= created_at
        then date_diff('minute', created_at, closed_at) / 60.0
    end                                         as resolution_hours,
    loaded_at
from {{ ref('stg_nyc_311__requests') }}
