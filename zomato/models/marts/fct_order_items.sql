{{ config(
    materialized = 'incremental',
    unique_key = 'order_item_id',
    incremental_strategy = 'merge',
    on_schema_change = 'append_new_columns'
) }}

SELECT
    oi.order_item_id,
    oi.order_id,
    oi.restaurant_id,
    oi.f_id,
    o.order_timestamp AS order_ts,
    o.order_date,
    o.city,
    oi.price,
    oi.quantity,
    oi.line_amount
FROM
    {{ ref('stg_order_items') }}
    oi
    INNER JOIN {{ ref('stg_orders') }}
    o USING (order_id)

{% if is_incremental() %}
WHERE
    o.order_timestamp > (
        SELECT
            COALESCE(MAX(order_ts), '1900-01-01' :: TIMESTAMP)
        FROM
            {{ this }})
        {% endif %}
