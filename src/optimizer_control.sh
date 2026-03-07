#!/bin/bash
case "" in
  start)
    echo "Starting Alii Optimizer..."
    nohup python3 /home/avalii/Alii/alii_optimizer.py > /home/avalii/Alii/optimizer.log 2>&1 &
    echo 3633503 > /home/avalii/Alii/optimizer.pid
    echo "Started with PID "
    ;;
  stop)
    if [ -f /home/avalii/Alii/optimizer.pid ]; then
      kill  2>/dev/null
      rm /home/avalii/Alii/optimizer.pid
      echo "Optimizer stopped"
    else
      echo "Not running"
    fi
    ;;
  status)
    if [ -f /home/avalii/Alii/optimizer.pid ] && ps -p  > /dev/null 2>&1; then
      echo "Running (PID: )"
      [ -f /home/avalii/Alii/optimizer_state.json ] && cat /home/avalii/Alii/optimizer_state.json
    else
      echo "Not running"
    fi
    ;;
  test)
    echo "Running test cycle..."
    timeout 15 python3 /home/avalii/Alii/alii_optimizer.py
    echo "Check logs: tail /home/avalii/Alii/optimizer.log"
    ;;
  *)
    echo "Usage: -bash {start|stop|status|test}"
    ;;
esac
