select event_id from {{ ref('int_payment_events') }}
group by event_id having count(*) != 1
