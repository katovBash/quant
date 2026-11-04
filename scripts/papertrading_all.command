#!/bin/zsh
cd "${0:A:h:h}" || exit 1
if ! tmux has-session -t quant-paper-fleet 2>/dev/null; then
  print 'Виртуальный процесс не запущен. Запусти: python3 -u -m service.paper_fleet --poll-seconds 900'
  exit 1
fi
print 'Открываю живой журнал виртуальных счетов. Ctrl+B, затем D — отсоединиться, не останавливая процесс.'
tmux attach -t quant-paper-fleet
