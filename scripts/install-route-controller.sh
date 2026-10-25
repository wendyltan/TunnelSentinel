#!/bin/zsh
# Install only the dedicated, least-privilege Shadowrocket group GUI adapter.
# A persistent Apple development signature is mandatory so macOS TCC approval
# is not invalidated by every new ad-hoc code hash.
set -euo pipefail
cd "${0:A:h:h}"

TARGET="$HOME/Applications/TunnelSentinelRouteController.app"
STAGING="$HOME/Applications/.TunnelSentinelRouteController.staging.app"
BACKUP="$HOME/Library/Application Support/OpenAILinkGuardian/backups/route-controller-before-stable-sign-20261025.app"

identity="${TUNNELSENTINEL_SIGNING_IDENTITY:-}"
if [[ -z "$identity" ]]; then
  identity="$(security find-identity -v -p codesigning | awk '/Apple Development:/ {print $2;exit}')"
fi
if [[ -z "$identity" ]]; then
  echo "ERROR: No stable code signing identity. Refusing ad-hoc replacement." >&2
  exit 41
fi
mkdir -p "$HOME/Applications" "${BACKUP:h}"
rm -rf "$STAGING"
mkdir -p "$STAGING/Contents/MacOS" "$STAGING/Contents/Resources"
/usr/bin/swiftc -O -framework AppKit -framework ApplicationServices \
  scripts/shadowrocket_group_editor.swift -o "$STAGING/Contents/MacOS/TunnelSentinelRouteController"
cat > "$STAGING/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>TunnelSentinel Route Controller</string>
<key>CFBundleDisplayName</key><string>TunnelSentinel Route Controller</string>
<key>CFBundleExecutable</key><string>TunnelSentinelRouteController</string>
<key>CFBundleIdentifier</key><string>com.wuwendi.tunnelsentinel.routecontroller</string>
<key>CFBundleVersion</key><string>2</string>
<key>CFBundleShortVersionString</key><string>0.2.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
/usr/bin/codesign --force --sign "$identity" --timestamp=none "$STAGING"
/usr/bin/codesign --verify --strict "$STAGING"

# Never clobber an active controller, so existing work isn't interrupted.
if pgrep -f '[T]unnelSentinelRouteController.*--set' >/dev/null; then
  echo "ERROR: route edit in progress, refusing update" >&2
  exit 42
fi
if [[ -e "$TARGET" ]]; then
  if [[ ! -e "$BACKUP" ]]; then
    /usr/bin/ditto "$TARGET" "$BACKUP"
  fi
  mv "$TARGET" "$TARGET.previous"
fi
mv "$STAGING" "$TARGET"
/usr/bin/codesign --verify --strict "$TARGET"
rm -rf "$TARGET.previous"
echo "Installed stable developer-signed TunnelSentinel Route Controller 0.2.0"
