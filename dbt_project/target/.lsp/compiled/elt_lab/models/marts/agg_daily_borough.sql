-- AGGREGATE: daily volume and resolution speed by borough.
select
    created_date,
    borough,
    count(*)                                   as requests,
    count(*) filter (where is_closed)          as closed_requests,
    round(median(resolution_hours), 2)         as median_resolution_hours
from "warehouse"."main_marts"."fct_requests"
group by created_date, borough