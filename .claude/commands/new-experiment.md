---
description: Start a new experiment run - intake Q&A for a CSV and a problem description
argument-hint: "[path/to/data.csv] [short description]"
---

Start a new experiment run following Phase 1 of CLAUDE.md.

Input from the user: $ARGUMENTS

1. If the CSV path or the description of the data and problem is missing, ask for both in one message
   (the user describes columns and context in plain English).
2. Create the run with `python -m abkit.state new <short-slug> --csv <path> --context-file <file with the description>`.
3. Load the experiment-intake skill, read the CSV header, and ask only the unanswered questions in one batch,
   including the statistical defaults table (keep or change?).
