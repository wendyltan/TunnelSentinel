#!/bin/zsh
# Backward-compatible entrypoint: auto route edits now belong to the native
# TunnelSentinel app; never create a second Python or GUI LaunchAgent.
set -euo pipefail
cd "${0:A:h:h}"
echo 'Codex auto-failover now runs inside TunnelSentinel.app (v1.6.0+).'
echo 'No independent auto-failover daemon will be installed.'
echo 'Install/update the single app via: ./install-menubar.sh'
