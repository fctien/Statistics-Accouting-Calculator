---
name: verify-bacalc
description: 一鍵驗證 BACalc（pytest、golden、MicroPython、JS、PWA 殼、突變測試）並產生 HTML log。使用者說「驗證」「跑測試」「verify」「commit 前」「改完程式」時使用。
---

# verify-bacalc：一鍵驗證

## 何時用

- 改完任何程式（`engine/`、`web/`、`tools/`、`tests/`）之後
- commit 之前、回報「完成」之前

## 怎麼跑

先確認 `git status` 乾淨（不乾淨會直接 exit 1）。再執行：

```
python tools/verify_all.py          # 完整驗證（含 mutate，最慢）
python tools/verify_all.py --quick  # 略過 mutate，log 會註明；日常迭代用，最後仍要跑完整版
```

會依序跑：git 乾淨檢查 → check_portable → pytest → build_web --check → check_shell →
JS 單元測試 → check_worker → test:mpy → test:mpy --self-test → mutate。
某項失敗後仍會跑完其餘項目，最後任一項失敗即 exit 1。

## 怎麼看 log

`logs/verify-YYYYMMDD-HHMM.html`：最上方是 commit、分支、版本、SHELL_HASH 與總結；
下表每項有指令、PASS/FAIL、耗時；FAIL 的項目附輸出末 60 行。

## 規則

- 失敗時先讀 log 找出是哪一項、哪一行，再修**程式**
- **絕不修改 golden 資料、放寬容差（tol）、刪除或改弱測試**來讓驗證通過；golden 對不上就回報使用者
- log 是 commit 的產物：驗證通過後，把 log 另外 commit 一次
- 回報時要給 log 路徑與結果（PASS/FAIL、是否 --quick）
- `--allow-dirty` 只用於示範故意弄壞程式，產生的 log 標示 DIRTY，不可當實驗紀錄
- UI 部分（畫面、離線、Service Worker 更新、Drive）不在自動驗證內，見 `e2e/checklist.md`
