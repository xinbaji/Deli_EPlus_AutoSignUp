#!/bin/bash
cd "$(dirname "$0")"
push_ok() { "$@" 2>push_err.log; code=$?; if [ $code -eq 0 ]; then return 0; fi; return 1; }
for i in $(seq 1 40); do
  echo "[$(date +%H:%M:%S)] attempt $i: push beta"
  if push_ok git push origin beta; then
    echo "beta pushed"
    for j in $(seq 1 40); do
      echo "[$(date +%H:%M:%S)] attempt $j: push tag v1.2.1"
      if push_ok git push origin v1.2.1; then
        echo "TAG PUSHED — release workflow triggered"
        rm -f push_err.log
        exit 0
      fi
      sleep 60
    done
    exit 1
  fi
  sleep 60
done
exit 1
