#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")" && pwd)"
install_dir="$HOME/Library/Application Support/OpenAILinkGuardian"
agent_path="$HOME/Library/LaunchAgents/com.wuwendi.tunnelsentinel-menu.plist"
log_dir="$HOME/Library/Logs/OpenAILinkGuardian"
binary="$install_dir/TunnelSentinelMenu"
mkdir -p "$install_dir" "$log_dir" "$HOME/Library/LaunchAgents"
build_dir="$(/usr/bin/mktemp -d "$install_dir/.tunnelsentinel-build.XXXXXX")"
trap '/bin/rm -rf "$build_dir"' EXIT
/usr/bin/swiftc -parse-as-library -O -framework AppKit \
  "$project_dir/menubar/TunnelSentinelMenu.swift" -o "$build_dir/TunnelSentinelMenu"
chmod 755 "$build_dir/TunnelSentinelMenu"
/usr/bin/python3 - "$agent_path" "$binary" "$log_dir" <<'PY'
from pathlib import Path
import plistlib,sys,os
path,exe,logs=sys.argv[1:]
agent={
 "Label":"com.wuwendi.tunnelsentinel-menu",
 "ProgramArguments":[exe],
 "RunAtLoad":True,
 "ProcessType":"Interactive",
 "StandardOutPath":str(Path(logs)/"menubar.stdout.log"),
 "StandardErrorPath":str(Path(logs)/"menubar.stderr.log")
}
with open(path,"wb") as out: plistlib.dump(agent,out)
os.chmod(path,0o644)
PY
/usr/bin/plutil -lint "$agent_path"
/bin/launchctl bootout "gui/$UID/com.wuwendi.tunnelsentinel-menu" 2>/dev/null || true
/bin/mv -f "$build_dir/TunnelSentinelMenu" "$binary"
/bin/launchctl bootstrap "gui/$UID" "$agent_path"
echo "TunnelSentinel status menu installed; guardian itself not restarted or changed."
