#!/bin/bash
# Sobe o app do editor de crachá (se ainda não estiver rodando) e abre no navegador.
set -e
cd "$(dirname "$0")"

URL="http://127.0.0.1:8501"
LOG="/tmp/editor_cracha_streamlit.log"

if ! curl -s -o /dev/null "$URL"; then
    nohup "$HOME/.local/bin/streamlit" run app.py \
        --server.address 127.0.0.1 \
        --server.port 8501 \
        --server.headless true \
        > "$LOG" 2>&1 &
    disown

    for i in $(seq 1 20); do
        sleep 0.5
        if curl -s -o /dev/null "$URL"; then
            break
        fi
    done
fi

xdg-open "$URL"
