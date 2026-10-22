#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")" && pwd)"
install_dir="$HOME/Library/Application Support/OpenAILinkGuardian"
applications_dir="$HOME/Applications"
app="$applications_dir/TunnelSentinel.app"
agent_path="$HOME/Library/LaunchAgents/com.wuwendi.tunnelsentinel-menu.plist"
log_dir="$HOME/Library/Logs/OpenAILinkGuardian"
launch_label="com.wuwendi.tunnelsentinel-menu"
launch_target="gui/$UID/$launch_label"

mkdir -p "$install_dir" "$log_dir" "$HOME/Library/LaunchAgents" "$applications_dir"
build_dir="$(/usr/bin/mktemp -d "$install_dir/.tunnelsentinel-brand-build.XXXXXX")"
trap '/bin/rm -rf "$build_dir"' EXIT
staged_app="$build_dir/TunnelSentinel.app"
mkdir -p "$staged_app/Contents/MacOS" "$staged_app/Contents/Resources"

/usr/bin/swiftc -parse-as-library -O -framework AppKit \
    "$project_dir/menubar/TunnelSentinelMenu.swift" -o "$staged_app/Contents/MacOS/TunnelSentinelMenu"
/bin/cp "$project_dir/branding/AppIcon.icns" "$staged_app/Contents/Resources/AppIcon.icns"
/bin/cp "$project_dir/branding/MenuBarTemplate.png" "$staged_app/Contents/Resources/MenuBarTemplate.png"

/usr/bin/python3 - "$staged_app/Contents/Info.plist" "$build_dir/agent.plist" \
    "$app/Contents/MacOS/TunnelSentinelMenu" "$log_dir" <<'PY'
from pathlib import Path
import plistlib,sys
info_path,agent_path,exe,log_dir=sys.argv[1:]
info={
 "CFBundleDevelopmentRegion":"zh_CN",
 "CFBundleExecutable":"TunnelSentinelMenu",
 "CFBundleIdentifier":"com.wuwendi.TunnelSentinel",
 "CFBundleInfoDictionaryVersion":"6.0",
 "CFBundleName":"TunnelSentinel",
 "CFBundleDisplayName":"TunnelSentinel",
 "CFBundlePackageType":"APPL",
 "CFBundleShortVersionString":"1.4.1",
 "CFBundleVersion":"4",
 "CFBundleIconFile":"AppIcon",
 "LSMinimumSystemVersion":"13.0",
 "LSUIElement":True,
 "NSHighResolutionCapable":True
}
with open(info_path,"wb") as f: plistlib.dump(info,f)
agent={
 "Label":"com.wuwendi.tunnelsentinel-menu",
 "ProgramArguments":[exe],
 "RunAtLoad":True,
 "ProcessType":"Interactive",
 "StandardOutPath":str(Path(log_dir)/"menubar.stdout.log"),
 "StandardErrorPath":str(Path(log_dir)/"menubar.stderr.log")
}
with open(agent_path,"wb") as f: plistlib.dump(agent,f)
PY
/usr/bin/plutil -lint "$staged_app/Contents/Info.plist" "$build_dir/agent.plist"
/usr/bin/codesign --force --sign - "$staged_app"
/usr/bin/codesign --verify --verbose=2 "$staged_app"

# Preserve the old LaunchAgent/binary and any prior app before touching live state.
backup_dir="$install_dir/backups/branding-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
/bin/cp -p "$agent_path" "$backup_dir/old-agent.plist" 2>/dev/null || true
/bin/cp -p "$install_dir/TunnelSentinelMenu" "$backup_dir/old-menu-binary" 2>/dev/null || true
/bin/launchctl bootout "$launch_target" 2>/dev/null || true
if [[ -d "$app" ]]; then
    /bin/mv "$app" "$backup_dir/prior-TunnelSentinel.app"
fi
/bin/mv "$staged_app" "$app"
/bin/cp "$build_dir/agent.plist" "$agent_path"
/bin/chmod 644 "$agent_path"
if ! /bin/launchctl bootstrap "gui/$UID" "$agent_path"; then
    echo "New menu failed to register. Restoring prior LaunchAgent." >&2
    /bin/mv "$app" "$backup_dir/failed-TunnelSentinel.app"
    if [[ -d "$backup_dir/prior-TunnelSentinel.app" ]]; then
        /bin/mv "$backup_dir/prior-TunnelSentinel.app" "$app"
    fi
    if [[ -f "$backup_dir/old-agent.plist" ]]; then
        /bin/cp "$backup_dir/old-agent.plist" "$agent_path"
        /bin/launchctl bootstrap "gui/$UID" "$agent_path" || true
    fi
    exit 1
fi
echo "TunnelSentinel.app installed: $app"
echo "Old menu recovery files: $backup_dir"
echo "Background guardian, Shadowrocket and ChatGPT were not restarted."
