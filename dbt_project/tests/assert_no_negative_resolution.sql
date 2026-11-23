-- Singular test: returns rows = failure. Resolution time can't be negative.
select request_id, resolution_hours
from {{ ref('fct_requests') }}
where resolution_hours < 0
