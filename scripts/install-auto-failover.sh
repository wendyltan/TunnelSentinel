#!/bin/zsh
# Does not enable or launch route edits; safe to run while Codex is active.
set -euo pipefail
cd "${0:A:h:h}"
ROOT="$HOME/Library/Application Support/OpenAILinkGuardian"
LABEL="com.wuwendi.tunnelsentinel-autofailover"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$ROOT" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/OpenAILinkGuardian"
chmod 700 "$ROOT"
for module in codex_autofailover.py codex_stream_health.py; do
  cp "scripts/$module" "$ROOT/$module.next"
  chmod 700 "$ROOT/$module.next"
  mv "$ROOT/$module.next" "$ROOT/$module"
done
/usr/bin/python3 - <<'PY'
from pathlib import Path
import json
p=Path.home()/"Library/Application Support/OpenAILinkGuardian/config.json"
values=json.loads(p.read_text())
# Never silently arm a brand-new GUI controller.
if "codex_auto_failover_enabled" not in values:
    values["codex_auto_failover_enabled"]=False
    q=p.with_name("config.auto-failover.tmp")
    q.write_text(json.dumps(values,indent=2,ensure_ascii=False)+"\n")
    q.chmod(0o600);q.replace(p)
assert values["codex_auto_failover_enabled"] is False, "Installer refuses to modify an already armed live system"
print("Auto-failover remains OFF until Accessibility authorization and probe pass.")
PY
/usr/bin/python3 - <<'PY'
from pathlib import Path
import plistlib
base=Path.home()
p=base/"Library/LaunchAgents/com.wuwendi.tunnelsentinel-autofailover.plist"
info={
 "Label":"com.wuwendi.tunnelsentinel-autofailover",
 "ProgramArguments":["/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",str(base/"Library/Application Support/OpenAILinkGuardian/codex_autofailover.py"),"--run-if-enabled"],
 "RunAtLoad":True,
 "StartInterval":45,
 "StandardOutPath":str(base/"Library/Logs/OpenAILinkGuardian/autofailover.log"),
 "StandardErrorPath":str(base/"Library/Logs/OpenAILinkGuardian/autofailover-error.log"),
 "ProcessType":"Background",
}
p.write_bytes(plistlib.dumps(info))
p.chmod(0o600)
PY
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "gui/$(id -u)/$LABEL"
fi
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo 'Installed disabled 45s autopilot LaunchAgent; Shadowrocket/Codex untouched'
