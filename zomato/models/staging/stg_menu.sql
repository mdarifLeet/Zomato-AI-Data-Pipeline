SELECT
menu_id,
TRY_TO_NUMBER(r_id) AS restaurant_id,
f_id,
cuisine,
TRY_TO_DECIMAL(price,10,2) as price
FROM {{source('raw','menu') }}
WHERE TRY_TO_NUMBER(r_id) IS NOT NULL AND TRY_TO_DECIMAL(price,10,2)>0