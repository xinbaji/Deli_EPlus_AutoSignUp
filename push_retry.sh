#!/bin/bash
# GitHub 直连时断时续：每分钟重试，通了自动推 beta + tag（最多 40 次）
cd "$(dirname "$0")"
for i in $(seq 1 40); do
  echo "[$(date +%H:%M:%S)] attempt $i: push beta"
  if git push origin beta > push_beta.log 2>&1; then
    echo "[$(date +%H:%M:%S)] beta pushed"
    for j in $(seq 1 10); do
      echo "[$(date +%H:%M:%S)] attempt $j: push tag v1.2.0"
      if git push origin v1.2.0 > push_tag.log 2>&1; then
        echo "[$(date +%H:%M:%S)] tag pushed — release workflow triggered"
        rm -f push_beta.log push_tag.log
        exit 0
      fi
      sleep 45
    done
    exit 1
  fi
  sleep 60
done
echo "GAVE UP after 40 attempts"
exit 1
