#!/bin/zsh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
out="$root/branding"
tmp="$(/usr/bin/mktemp -d)"
trap '/bin/rm -rf "$tmp"' EXIT
/usr/bin/swiftc -parse-as-library -O -framework AppKit \
  "$out/GenerateBranding.swift" -o "$tmp/brandgen"
"$tmp/brandgen" "$out"
iconset="$tmp/TunnelSentinel.iconset"
mkdir -p "$iconset"
for size in 16 32 128 256 512; do
  /usr/bin/sips -s format png -z "$size" "$size" "$out/AppIcon-1024.png" \
    --out "$iconset/icon_${size}x${size}.png" >/dev/null
  twice=$((size * 2))
  /usr/bin/sips -s format png -z "$twice" "$twice" "$out/AppIcon-1024.png" \
    --out "$iconset/icon_${size}x${size}@2x.png" >/dev/null
done
/usr/bin/iconutil -c icns "$iconset" -o "$out/AppIcon.icns"
/usr/bin/sips -s format png -z 256 256 "$out/AppIcon-1024.png" \
  --out "$out/ReadmeIcon.png" >/dev/null
echo "Brand assets ready: AppIcon.icns, MenuBarTemplate.png, ReadmeIcon.png"
