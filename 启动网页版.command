#!/bin/zsh
cd -- "${0:A:h}" || exit 1

port=5176
url="http://127.0.0.1:$port/"
page=$(/usr/bin/curl --noproxy '*' --fail --silent --max-time 1 "$url")
if [[ $page == *'<title>肥鱼跑酷 · 海滨算力站</title>'* && $page == *'id="summon-cut-in"'* ]]; then
  exec open "$url"
fi

if ! command -v npm >/dev/null; then
  node_installations=("$HOME"/.local/node-*/bin/npm(N))
  if (( ${#node_installations} )); then
    export PATH="${node_installations[-1]:h}:$PATH"
  fi
fi
if ! command -v npm >/dev/null || [[ ! -x node_modules/.bin/vite ]]; then
  print -u2 '找不到 Node.js 或游戏依赖。请先按 README.md 安装，再双击启动。'
  exit 1
fi

print '正在启动肥鱼跑酷，浏览器会自动打开。玩的时候请保持这个窗口开启。'
exec npm run dev -- --port "$port" --strictPort --open
