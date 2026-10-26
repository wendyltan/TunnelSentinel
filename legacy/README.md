# Historical Shadowrocket automation (NOT INSTALLED)

These files are retained only for Git history and test/reference inspection.
Do not run `install-auto-failover.sh` or build this older standalone Swift editor.
Both have been replaced with a **single** signed `TunnelSentinel.app` and a
read-only Guardian by default. No corresponding legacy LaunchAgent should exist.

`scripts/codex_autofailover.py` remains where historical regression tests expect
it, but is NOT launched or installed by current `install.sh` or
`install-menubar.sh`. Enabling the monitor does not activate this old program.

Current routing controls are disabled without the explicit
`automatic_control_enabled=true` master gate. The current Shadowrocket group
still lacks trustworthy unattended active-policy confirmation; do not enable
AX route edits without further isolated acceptance testing.
