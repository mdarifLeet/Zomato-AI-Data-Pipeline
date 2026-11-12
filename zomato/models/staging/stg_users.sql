SELECT
    {{ try_int('user_id') }} AS customer_id,
    name AS customer_name,
    LOWER(TRIM(CAST(email AS VARCHAR))) AS email,
    {{ try_int('age') }} AS age,
    gender,
    marital_status,
    occupation,
    monthly_income AS income_band,
    education,
    {{ try_int('family_size') }} AS family_size
FROM {{ source('raw', 'users') }}
WHERE {{ try_int('user_id') }} IS NOT NULL
