SELECT
    order_date,
    city,
    COUNT(*) AS orders,
    SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END) AS delivered_orders,
    ROUND(
        COALESCE(
            SUM(CASE WHEN order_status = 'Cancelled' THEN 1.0 ELSE 0.0 END) / NULLIF(COUNT(*), 0),
            0
        ),
        4
    ) AS cancel_rate,
    SUM(CASE WHEN is_delivered THEN sales_amount ELSE 0 END) AS gmv,
    ROUND(
        COALESCE(
            SUM(CASE WHEN is_delivered THEN sales_amount ELSE 0.0 END)
            / NULLIF(SUM(CASE WHEN is_delivered THEN 1 ELSE 0 END), 0),
            0
        ),
        2
    ) AS aov
FROM {{ ref('fct_orders') }}
GROUP BY 1, 2
