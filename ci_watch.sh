#!/bin/bash
# GitHub 连接时断时续：长周期自动重试推送 + 盯新 CI 运行到出结果（最多 2 小时）
cd "$(dirname "$0")"
BASELINE_RUN=33980434795

push_ok() { "$@" 2>push_err.log; code=$?; if [ $code -eq 0 ]; then return 0; fi; echo "  retry($code): $(tail -1 push_err.log | cut -c1-90)"; return 1; }

echo "[A] 推送 beta 与重打 tag（每 3 分钟一次，最多 40 次）..."
for i in $(seq 1 40); do
  if push_ok git push origin beta; then break; fi
  sleep 180
done
for i in $(seq 1 40); do
  if push_ok git push origin :refs/tags/v1.2.0; then break; fi
  sleep 180
done
git tag -d v1.2.0 >/dev/null 2>&1
git tag -a v1.2.0 -m "v1.2.0：pywebview Fluent 2 前端 + 签到加固提速 + 自动更新（多源回退）"
for i in $(seq 1 40); do
  if push_ok git push origin v1.2.0; then break; fi
  sleep 180
done
rm -f push_err.log

echo "[B] 等 v1.2.0 的新 CI 运行出现（基线 $BASELINE_RUN）..."
new_run=""
for i in $(seq 1 30); do
  new_run=$(curl -s --max-time 30 "https://api.github.com/repos/xinbaji/Deli_EPlus_AutoSignUp/actions/runs?per_page=1" 2>/dev/null | python -c "
import json, sys
try:
    r = json.load(sys.stdin)['workflow_runs'][0]
    print(r['id'] if int(r['id']) > int('$BASELINE_RUN') else '')
except Exception:
    print('')
")
  if [ -n "$new_run" ]; then break; fi
  sleep 60
done
if [ -z "$new_run" ]; then echo "未检测到新运行"; exit 1; fi
echo "新运行: $new_run"

echo "[C] 盯 CI..."
for i in $(seq 1 60); do
  status=$(curl -s --max-time 30 "https://api.github.com/repos/xinbaji/Deli_EPlus_AutoSignUp/actions/runs/$new_run" 2>/dev/null | python -c "
import json, sys
try:
    r = json.load(sys.stdin)
    print(r['status'], r.get('conclusion') or '-')
except Exception:
    print('unknown -')
")
  echo "[$(date +%H:%M:%S)] CI: $status"
  case "$status" in
    "completed success")
      echo "CI SUCCESS"
      curl -s --max-time 30 "https://api.github.com/repos/xinbaji/Deli_EPlus_AutoSignUp/releases" | python -c "
import json, sys
for r in json.load(sys.stdin)[:1]:
    print('release:', r['tag_name'], [a['name'] for a in r.get('assets', [])])
"
      exit 0
      ;;
    "completed failure")
      echo "CI FAILED — 注解："
      jobid=$(curl -s --max-time 30 "https://api.github.com/repos/xinbaji/Deli_EPlus_AutoSignUp/actions/runs/$new_run/jobs" | python -c "import json,sys; print(json.load(sys.stdin)['jobs'][0]['id'])")
      curl -s --max-time 30 "https://api.github.com/repos/xinbaji/Deli_EPlus_AutoSignUp/check-runs/$jobid/annotations" | python -c "
import json, sys
for a in json.load(sys.stdin):
    m = a.get('message','')
    if 'Node.js' not in m and m:
        print('[ANN]', m[:300])
"
      exit 1
      ;;
  esac
  sleep 45
done
echo "CI 监控超时"
exit 1
