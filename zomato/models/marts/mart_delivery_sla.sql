SELECT
    city,
    EXTRACT(HOUR FROM CAST(order_timestamp AS TIMESTAMP)) AS order_hour,
    SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered_orders,
    ROUND(
        CAST(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_time_min) AS DECIMAL(10, 2)),
        1
    ) AS p50,
    ROUND(
        CAST(PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY delivery_time_min) AS DECIMAL(10, 2)),
        1
    ) AS p90
FROM {{ ref('fct_orders') }}
WHERE is_delivered
GROUP BY 1, 2
