We ran an A/B test on the checkout page: the treatment replaces the multi-step checkout with a single "Pay now" button.
File: checkout_ab.csv, one row per user. Columns: user_id, variant (control / treatment), exposure_date (first day the user
saw checkout, 2026-09-01 to 2026-09-14), platform (iOS / Android / Web), country (US / UK / DE / IN), converted (1 if the user
completed a purchase within the test), revenue (USD revenue from that user during the test, 0 if no purchase).
Traffic was split 50/50 at user level. Primary metric is conversion; revenue per user is a guardrail - we don't want it to drop.
We'd like to know if we should ship it, and whether the effect differs by platform.
