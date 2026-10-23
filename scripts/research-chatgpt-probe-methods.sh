#!/bin/zsh
# Opt-in research only. NEVER switches nodes, opens app GUI, or logs secrets.
# Tests the existing macOS Shadowrocket-selected route through its local proxy.
set -u
PROXY="http://127.0.0.1:1082"
for url in     "https://chatgpt.com/cdn-cgi/trace"     "https://chatgpt.com/robots.txt"     "https://www.gstatic.com/generate_204"; do
  printf '%s\n' "$url"
  for method in HEAD GET; do
    if [[ "$method" = HEAD ]]; then
      code=$(/usr/bin/curl --silent --show-error -I -x "$PROXY"           --connect-timeout 3 --max-time 7 -o /dev/null           -w '%{http_code}' "$url" 2>/dev/null)
    else
      code=$(/usr/bin/curl --silent --show-error -x "$PROXY"           --connect-timeout 3 --max-time 7 -o /dev/null           -w '%{http_code}' "$url" 2>/dev/null)
    fi
    printf '  %-4s http=%s\n' "$method" "${code:-transport-error}"
  done
done
echo 'All results describe only the currently selected proxy route.'
