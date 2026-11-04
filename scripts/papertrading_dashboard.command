#!/bin/zsh
cd "${0:A:h:h}" || exit 1
if ! tmux has-session -t quant-paper-web 2>/dev/null; then
  tmux new-session -d -s quant-paper-web 'python3 -u -m web.server'
fi
open http://127.0.0.1:8765/
print 'Локальная панель paper trading. Ctrl+B, затем D — отсоединиться от терминала, не останавливая панель.'
tmux attach -t quant-paper-web
