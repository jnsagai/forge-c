# DA-013: Explicit local LINE service rendering and boot fencing

Status: proposed implementation; DA-T046/050 live acceptance remains open.

The generic service renderer does not select the existing LINE templates. Manually rendered LINE units lack
the generic host preflight and explicit durable Intent binding. This increment adds `services render-line`,
which renders only the existing local conductor, external watchdog and timer templates. It never installs,
enables or starts them. The generic render/install commands and unsigned legacy OBSERVE startup stay unchanged.

Deployment requires explicit absolute simple paths for durable Intent, launch layout, watchdog archive,
dependencies and interpreter. Intent and host watchdog paths must resolve outside the application volume.
The operator still verifies source/archive/dependency/interpreter pins using the existing package tooling;
rendering is not qualification or authority. The conductor uses the existing host-volume preflight, notify
watchdog, restart/burst settings and control-plane CPU/IO/memory/task reserves. The fixed local unit is bound
to both existing LINE and operations environment selectors so the operational recipe cannot target the generic
conductor accidentally. LLVM PATH selection remains the normal renderer's selection.

Configured local startup checks the existing private durable Intent before Fabro lookup or state observation.
RUNNING, PAUSED and DRAINING permit model-free controller startup; independent work admission retains its fresh
authorization/Intent/budget/lease checks. STOPPED, missing, corrupt or otherwise UNKNOWN Intent exits 77.
`RestartPreventExitStatus=77` suppresses automatic retries while retaining a failed unit. An `ExecCondition`
skip would leave inactive/success, which the existing deliberate-OS-stop-aware recovery correctly refuses.
After fresh authorized Intent resume, the existing enabled-failed-unit recipe can recover the failed service
subject to CRE preauthorization, cooldown and serialized epoch/effect fencing. An explicit OS stop, disable
or mask remains deliberate and is not automatically undone. No reset-failed, policy, signature or grant change
is introduced.

CONTROL tests distinguish render validation and public startup behavior from real service semantics. Disposable
local transient tests may exercise the public OBSERVE command with private Intent/state and an empty recorded
Fabro view; those establish only local systemd behavior. They do not establish actual Omniverse reboot/mount,
dependency recovery, owner shutdown settlement, repair competence, or 24/72/168-hour endurance. No feature task
checkbox is closed by this source increment.
