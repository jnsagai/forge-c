# Driver demo pass 1: BLOCKED by the operator, not by the author

The scope check charged the author with writing `.claude/skills/hi-gates/scripts/forge_hi/__pycache__/*.pyc` during
its `fix-governance` call (05:03:25 to 05:03:53Z). Those files were written by a diagnostic command the operator
(Claude, running the demo) started in this project at that moment. The command imported `forge_hi` from the installed
skills; it was run without `-B` and before the fix 4279db11 was in the installed copy.

The conductor attributed the files to the active role, as designed: a snapshot taken before and after each role call
cannot tell who wrote a file. Lesson: never run Python against a live project without `-B` /
`PYTHONDONTWRITEBYTECODE`.

The governance package of this pass (`governance.redacted.json`: section titles from the manual replaced by their hash) also showed a package defect, fixed in 3ad63c38: use cases naming the driver's constraints (CON-IWDG-*) were reported as unknown references.
