select * from {{ ref('fct_daily_revenue') }} where revenue_cents < 0
