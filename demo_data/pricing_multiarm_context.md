Pricing test with three arms: control (current prices), price_low (-10% list prices) and price_high (+15% list prices).
File: pricing_multiarm.csv, one row per user, randomised equally across the three arms over 21 days starting 2026-09-01.
Columns: user_id, variant, assignment_date, orders (number of orders), revenue (USD, includes a few very large B2B baskets).
Primary metric is revenue per user. We need to pick which price level to roll out. Orders per user matters too.
