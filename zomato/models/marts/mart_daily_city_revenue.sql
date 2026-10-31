SELECT
    order_date,
    city,
    COUNT(*) AS orders,
    count_if(is_delivered) AS delivered_orders,
    ROUND(div0(count_if(order_status = 'Cancelled'), COUNT(*)), 4) AS cancel_rate,
    SUM(IFF(is_delivered, sales_amount, 0)) AS gmv,
    ROUND(
        div0(SUM(IFF(is_delivered, sales_amount, 0)), count_if(is_delivered)),
        2) AS aov
        FROM
            {{ ref('fct_orders') }}
        GROUP BY 1,2
