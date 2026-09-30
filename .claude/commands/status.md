---
description: Show the active run's phase, gates and plan progress
---

Current state:

!`python -m abkit.state status || echo "No active run. Runs available:" && python -m abkit.state list`

Summarise this for the user in a few lines: run id, phase, which gates are open, plan progress, and the next step.
If there is no active run, list the runs and say how to start or switch.
