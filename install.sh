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
cp "$source_dir/workflow_health.py" "$install_dir/workflow_health.py"
chmod 700 "$install_dir/workflow_health.py"
cp "$source_dir/scripts/computer_use_observer.py" "$install_dir/computer_use_observer.py"
chmod 700 "$install_dir/computer_use_observer.py"
cp "$source_dir/scripts/clash_observer.py" "$install_dir/clash_observer.py"
chmod 700 "$install_dir/clash_observer.py"
cp "$source_dir/scripts/system_proxy_observer.py" "$install_dir/system_proxy_observer.py"
chmod 700 "$install_dir/system_proxy_observer.py"
cp "$source_dir/scripts/gpt_deep_probe.py" "$install_dir/gpt_deep_probe.py"
chmod 700 "$install_dir/gpt_deep_probe.py"
cp "$source_dir/scripts/codex_business_observer.py" "$install_dir/codex_business_observer.py"
chmod 700 "$install_dir/codex_business_observer.py"
cp "$source_dir/scripts/codex_stream_health.py" "$install_dir/codex_stream_health.py"
cp "$source_dir/scripts/codex_remote_control.py" "$install_dir/codex_remote_control.py"
chmod 700 "$install_dir/codex_stream_health.py" "$install_dir/codex_remote_control.py"
cp "$source_dir/scripts/clash_openai_profile.py" "$install_dir/clash_openai_profile.py"
cp "$source_dir/scripts/clash_failover.py" "$install_dir/clash_failover.py"
chmod 700 "$install_dir/clash_openai_profile.py" "$install_dir/clash_failover.py"
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
