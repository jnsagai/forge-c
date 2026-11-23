# Safety Supervisor: use of the IWDG driver

**Fictional demo decision**, written by Claude for the linked-project demo (T052).

| ID | Decision |
|---|---|
| CON-SUP-148 | The supervisor configures, starts and refreshes the independent watchdog only through the services of the IWDG driver project (`../f023-drv-1`, driver interface requirements `DRV-IWDG-*`). Software requirements that rely on one of those services cite the `DRV-IWDG-*` items they use. |
