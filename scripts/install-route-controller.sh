#!/bin/zsh
set -euo pipefail
cd "${0:A:h:h}"
TARGET="$HOME/Applications/TunnelSentinelRouteController.app"
mkdir -p "$TARGET/Contents/MacOS"
mkdir -p "$TARGET/Contents/Resources"
/usr/bin/swiftc -O -framework AppKit -framework ApplicationServices scripts/shadowrocket_group_editor.swift -o "$TARGET/Contents/MacOS/TunnelSentinelRouteController"
cat > "$TARGET/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>TunnelSentinel Route Controller</string>
<key>CFBundleDisplayName</key><string>TunnelSentinel Route Controller</string>
<key>CFBundleExecutable</key><string>TunnelSentinelRouteController</string>
<key>CFBundleIdentifier</key><string>com.wuwendi.tunnelsentinel.routecontroller</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundleShortVersionString</key><string>0.1.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
/usr/bin/codesign --force --sign - "$TARGET"
/usr/bin/codesign --verify --strict "$TARGET"
echo "Signed accessibility-gated native controller installed; NOT YET APPROVED OR ACTIVE"
