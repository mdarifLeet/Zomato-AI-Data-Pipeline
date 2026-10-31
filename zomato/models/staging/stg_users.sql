SELECT
    user_id :: NUMBER AS customer_id,
    NAME AS customer_name,
    LOWER(TRIM(email)) AS email,
    TRY_TO_NUMBER(age) AS age,
    gender,
    marital_status,
    occupation,
    monthly_income AS income_band,
    education,
    TRY_TO_NUMBER(family_size) AS family_size
FROM
    {{ source(
        'raw',
        'users'
    ) }}
WHERE
    TRY_TO_NUMBER(user_id) IS NOT NULL
