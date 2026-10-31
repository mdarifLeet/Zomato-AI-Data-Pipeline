SELECT
f_id,
food_name,
veg_or_non_veg
FROM {{ref('stg_food')}}