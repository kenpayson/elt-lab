-- DIMENSION: one row per agency.
select
    agency_code,
    max(agency_name)  as agency_name,
    count(*)          as total_requests
from {{ ref('stg_nyc_311__requests') }}
group by agency_code
