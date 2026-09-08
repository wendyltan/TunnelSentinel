#!/bin/zsh
set -euo pipefail

source_dir="${0:A:h}"
install_dir="$HOME/Library/Application Support/OpenAILinkGuardian"
log_dir="$HOME/Library/Logs/OpenAILinkGuardian"
agent_path="$HOME/Library/LaunchAgents/com.wuwendi.openai-link-guardian.plist"
python_path="$(command -v python3)"

mkdir -p "$install_dir" "$log_dir" "$HOME/Library/LaunchAgents"
cp "$source_dir/openai_link_guardian.py" "$install_dir/openai_link_guardian.py"
chmod 700 "$install_dir/openai_link_guardian.py"
if [[ ! -f "$install_dir/config.json" ]]; then
  cp "$source_dir/config.json" "$install_dir/config.json"
  chmod 600 "$install_dir/config.json"
fi

sed \
  -e "s|__PYTHON__|$python_path|g" \
  -e "s|__INSTALL_DIR__|$install_dir|g" \
  -e "s|__LOG_DIR__|$log_dir|g" \
  "$source_dir/com.wuwendi.openai-link-guardian.plist.template" > "$agent_path"
plutil -lint "$agent_path"

launchctl bootout "gui/$UID" "$agent_path" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$agent_path"
launchctl kickstart -k "gui/$UID/com.wuwendi.openai-link-guardian"

echo "Installed OpenAI Link Guardian."
echo "Status: $install_dir/status.json"
echo "Log: $log_dir/guardian.log"
