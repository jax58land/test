#!/bin/bash
# えふぃぞー 起動用（Mac）。ダブルクリックで開く。
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:4321"
pause() { echo; read -r -p "Enter を押すと閉じます" _; }

echo "=== えふぃぞー ==="

# 1. Node.js があるか
if ! command -v node >/dev/null 2>&1; then
  for p in /usr/local/bin /opt/homebrew/bin; do [ -x "$p/node" ] && export PATH="$p:$PATH"; done
fi
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js が見つかりません。"
  echo "開いたページから「LTS」をダウンロードして入れてから、もう一度ダブルクリックしてください。"
  open "https://nodejs.org/ja/download"
  pause; exit 1
fi

# 2. すでに動いていれば、画面を開くだけ
if curl -s -o /dev/null "$URL/api/health"; then
  echo "すでに動いています。画面を開きます。"
  open -a "Google Chrome" "$URL" 2>/dev/null || open "$URL"
  exit 0
fi

# 3. 必要な部品がなければ入れる
if [ ! -f node_modules/@elevenlabs/client/dist/lib.iife.js ]; then
  echo "必要な部品を入れています（初回だけ・1分ほど）..."
  npm install --no-fund --no-audit || { echo "部品を入れられませんでした。ネット接続を確認してください。"; pause; exit 1; }
fi

# 4. Agent ID がまだなら、自動セットアップ
AGENT=$(node -e 'try{process.stdout.write(require("./config.json").agentId||"")}catch{}')
if [ -z "$AGENT" ]; then
  echo
  echo "まだ Agent ID がありません。自動セットアップを始めます。"
  echo "（APIキーがまだない人は Ctrl+C で抜けて、README の手順でキーを作ってください）"
  node setup.mjs || { pause; exit 1; }
fi

# 5. Chrome があるか
if ! open -Ra "Google Chrome" 2>/dev/null; then
  echo "Google Chrome が見つかりません。Chrome を入れてから、もう一度ダブルクリックしてください。"
  pause; exit 1
fi

# 6. サーバーを起動して、Chrome で開く（このウィンドウを閉じるとサーバーも止まる）
node server.mjs &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT INT TERM HUP
for _ in $(seq 1 50); do curl -s -o /dev/null "$URL/api/health" && break; sleep 0.1; done
open -a "Google Chrome" "$URL"
echo
echo "止めるとき：画面で「待受をオフ」を押してから、このウィンドウを閉じる。"
wait $SERVER
