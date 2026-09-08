#!/bin/zsh
set -euo pipefail

agent_path="$HOME/Library/LaunchAgents/com.wuwendi.openai-link-guardian.plist"
if [[ -f "$agent_path" ]]; then
  launchctl bootout "gui/$UID" "$agent_path" 2>/dev/null || true
  rm "$agent_path"
fi
echo "LaunchAgent removed. Runtime data remains in ~/Library/Application Support/OpenAILinkGuardian."
