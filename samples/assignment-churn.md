Assignment: Predicting Membership Cancellations for Pulsepoint Gyms
Context

Pulsepoint Gyms is a fictional fitness chain with 14 clubs in the Netherlands and about 41,000 members. Members pay through a monthly contract that can be cancelled with one month’s notice, or through a cheaper annual contract. Management has noticed that cancellations come in waves. One peak comes in January, when members decide not to renew after the holidays. A second peak comes in June, before summer. Pulsepoint currently sends every member the same “come back” e-mail after they have already cancelled, and that hardly works. The membership team wants an early-warning model that flags at-risk members while there is still time to act, for example through a free session with a personal trainer.

Pulsepoint has given you an anonymised dataset of 36,500 members, with monthly snapshots from January 2024 to June 2026. That makes 412,000 rows in total. The columns include snapshot_month, contract_type (monthly or annual), home_club, age_band, tenure_months, checkins_last_30d, checkin_change_vs_prev_30d, group_classes_last_30d, pt_sessions, freeze_requests and payment_failures. The target column churned is 1 if the member cancelled within 60 days after the snapshot, and 0 if they did not. Across all snapshots about 9% are churners, but the rate is much higher in some months. The same member appears many times, and this matters for how you split the data.

What the team delivers
A cleaned dataset and a reproducible Jupyter notebook that documents every preparation and feature-engineering step
At least two compared models (for example logistic regression and gradient boosting), trained and tested with a time-based split
An analysis of how churn and model performance differ by season and by club
A short report for Pulsepoint’s membership manager, at most 6 pages, with concrete and prioritised retention recommendations
A 10-minute presentation followed by 5 minutes of questions from the client and the teacher
Grading criteria
Business understanding (15%): The team turns the client’s problem into a clear prediction goal, including how far ahead the model must warn. It explains the trade-off between missing a churner and spending trainer time on a member who would have stayed anyway.
Data quality and preparation (20%): Missing values, impossible values and duplicate snapshots are found and handled with justified choices. Features such as check-in trends or “months until the contract ends” are motivated by how members actually behave.
Validation design (20%): The team sees that a random split leaks information, because the same members and the same months appear in both train and test. It uses a time-based split instead, and it tests whether the model still works in high-churn months.
Modelling and evaluation (25%): Models are compared with metrics that fit an imbalanced, seasonal problem, such as recall, precision and PR-AUC, not only accuracy. The team explains its choice of decision threshold and reports results per season or per club where that matters.
Communication and recommendations (20%): The report and presentation are clear to a non-technical manager. They explain which signals predict cancellation, they propose realistic actions with an estimated impact, and they are honest about the model’s limits.