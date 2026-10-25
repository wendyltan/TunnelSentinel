#!/bin/zsh
# Backward-compatible entrypoint: a second Route Controller.app is deprecated.
set -euo pipefail
cd "${0:A:h:h}"
echo 'Route Controller has been integrated into TunnelSentinel.app (v1.6.0+).'
echo 'No standalone app will be created. Install/update the single app via: ./install-menubar.sh'
