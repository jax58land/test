#!/bin/bash
# えふぃぞー の設定（声・役割の文章）をやり直すとき用（Mac）。
cd "$(dirname "$0")" || exit 1
for p in /usr/local/bin /opt/homebrew/bin; do [ -x "$p/node" ] && export PATH="$p:$PATH"; done
[ -d node_modules ] || npm install --no-fund --no-audit
node setup.mjs
echo; read -r -p "Enter を押すと閉じます" _
