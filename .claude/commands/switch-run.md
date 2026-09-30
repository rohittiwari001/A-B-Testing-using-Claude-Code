---
description: Change the active run
argument-hint: "<run-id>"
---

Switch the active run to: $ARGUMENTS

Runs available:

!`python -m abkit.state list`

1. If the argument matches a run id (or uniquely matches part of one), run `python -m abkit.state switch <run-id>`.
2. Otherwise show the list and ask which run.
3. After switching, summarise the new active run's status and next step in two or three lines.
