SELECT
    city,
    HOUR(order_timestamp) AS order_hour,
    count_if(is_delivered) AS delivered_orders,
    ROUND(MEDIAN(delivery_time_min), 1) AS p50,
    ROUND(PERCENTILE_CONT(0.9) within GROUP ( ORDER BY delivery_time_min), 1) AS p90
FROM
    {{ ref('fct_orders') }}
WHERE
    is_delivered
GROUP BY
    1,
    2
