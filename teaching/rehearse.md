# 課前演練紀錄（step0～step2，AI 版）

- 日期：2026-10-21
- 範圍：step0、step1、step2，AI Agent 版；每步各跑兩次：(a) 一句話下法 `bad_prompt`、(b) 四段式 `prompt`
- 結果已回寫 `teaching/prompts.py`：step0～step2 的 `bad_result` 改為「實測：」開頭，新坑加進 `pitfalls`（標「演練 2026-10-21」）；step3～step9 仍是「推測：」

## 重要限制：這是替身演練，不是獨立 AI 工作階段

原計畫每次用全新的 `claude -p`（headless Claude Code）工作階段跑，實際指令如下（每個資料夾各一次，Python `subprocess`，cwd 為該資料夾）：

```
HOME=<假家目錄> USERPROFILE=<假家目錄>
claude -p "<bad_prompt 或 prompt 原文>" --model sonnet --max-turns 15 --permission-mode acceptEdits
```

六次全部立即結束，輸出 `Not logged in · Please run /login`（exit 1）。假家目錄裡沒有登入資訊，依規定**不登入任何帳號**，因此改由實作者本人扮演學生與 AI：

- 每次都在 repo 外的全新暫存資料夾，以 `git archive` 取得起點 tag 的檔案，另外 `git init` 成獨立 repo
- 假家目錄 `.claude/CLAUDE.md` 放 `prompts.USER_CLAUDE_MD`，沒有碰 `C:/Users/User/.claude`
- AI 只依卡片的 Prompt 文字與資料夾內的檔案行事，產生的檔案與 【驗收】 指令都**真的執行**並記錄輸出
- **偏差**：扮演 AI 的實作者看過 BACalc 原始碼，一句話版本的行為（例如會不會先讀規格書）是替身的判斷，不代表 Claude 每次都這樣做；可重現的是「產出了什麼、驗收指令跑出什麼」
- `claude -p` 類的驗收指令因未登入無法執行，改為人工依產出的檔案判斷
- **每一格都只是單次替身執行**（每步每種 Prompt 各跑一次），沒有重複取樣；真正的 AI 每次結果可能不同，表中的「失敗／通過」只代表這一次

起點：step0 用 `step0` tag 刪掉 CLAUDE.md 與 DEVLOG.md（只剩規格書與 `tools/md2html.py`）；step1 用 `step0` tag；step2 用 `step1` tag

## step0：兩層 CLAUDE.md

| | (a) 一句話「幫我寫一個 CLAUDE.md」 | (b) 四段式 |
|---|---|---|
| 產出 | CLAUDE.md（概述／技術選擇／架構／常用指令／開發原則），內容照抄規格書：Pyodide、AST 白名單、金額用 decimal；沒有 DEVLOG.md | 五段式 CLAUDE.md＋只有標題的 DEVLOG.md；寫入 MicroPython 限制、只能 import math 與 json、禁止 eval；沒有重複使用者層級規則 |
| 驗收：三點複述 | 無法以 `claude -p` 執行（未登入） | 同左；替身複述：計算只放 engine、算不出來回錯誤、engine 只用 math 與 json |
| 驗收：「engine/ 可以 import decimal 嗎」 | 無法以 `claude -p` 執行；依檔案內容只會答「可以」（檔案寫金額用 decimal）→ **失敗** | 依檔案答「不行，MicroPython 沒有 decimal」→ 通過 |
| 驗收：五段對照 | `grep "^## 段名"`：常用指令有，其餘四段缺 → **失敗** | 五段都有 → 通過 |
| 驗收：`git show step0:CLAUDE.md` | `fatal: invalid object name 'step0'` → **失敗** | 同左 → **失敗**（新資料夾沒有 tag） |

差異：四段式把執行環境限制寫進規則；一句話版本忠實抄了規格書，連「AST 白名單」與「decimal」這兩個後來證明在 MicroPython 不可行的設計都抄進去

## step1：plan mode 規劃

| | (a) 一句話「幫我做一個 BA II Plus 計算機的網頁 App」 | (b) 四段式 |
|---|---|---|
| 產出 | 沒有寫任何檔案；在對話中給三行計畫（engine → web 用 Pyodide → 儲存）就問「要直接開始寫嗎」（使用者層級 CLAUDE.md 有「大改動先給計畫」） | `docs/spec-2026-10-21.md`（規格修訂：執行環境大小比較、可攜子集、bridge 格式）、`docs/plan-2026-10-21.md`，兩份都用 md2html 轉成 HTML |
| 執行環境大小 | 沒比較 | 實測 jsDelivr 傳輸大小：Pyodide 0.26.4（pyodide.asm.wasm 2,991,722＋python_stdlib.zip 2,306,344＋pyodide.asm.js 240,835 bytes）約 5.54 MB；MicroPython 1.26.0（micropython.wasm 190,996＋micropython.mjs 30,812 bytes）約 0.22 MB |
| 驗收：`python tools/md2html.py docs/plan-2026-10-20.md` | FileNotFoundError → **失敗** | 卡片原文 FileNotFoundError → **失敗**；換成自己的檔名 plan-2026-10-21.md → 通過 |
| 驗收：`grep -n -E "MVC\|突變\|golden"` | 找不到檔案 → **失敗** | 換成自己的檔名後 MVC、golden、突變都有 → 通過 |
| 驗收：`claude -p "列出…親自做的事"` | 無法執行（未登入） | 無法執行；計畫中有「需要使用者親自做或同意」四項 |

差異：一句話版本因使用者層級規則而停下來問，沒有造成損害，但也沒有任何可驗收的產出；四段式產出可檢查的檔案。作者自己的 step1 也是先 Pyodide、後改 MicroPython，演練實測的大小與 DEVLOG 記錄（約 5.3 MB 對 0.23 MB）同一量級

大小量法：`curl -s -o /dev/null -w "%{size_download}" --compressed <URL>`，URL 前綴 `https://cdn.jsdelivr.net/pyodide/v0.26.4/full/` 與 `https://cdn.jsdelivr.net/npm/@micropython/micropython-webassembly-pyscript@1.26.0/`（版本為演練時選的，不是 repo 鎖定的 1.29.0-6）

## step2：TDD TVM 引擎

| | (a) 一句話「用 Python 寫 TVM 計算，要有測試」 | (b) 四段式 |
|---|---|---|
| 產出 | `engine/tvm.py`（pmt、fv、pv、nper、rate）＋5 個測試，測試在程式之後寫、只驗自己算的值、沒有出處 | `engine/tvm.py`（solve）、`solver.py`（牛頓法＋二分法）、`result.py`、`tools/check_portable.py`、`tests/golden/excel.json`（4 筆，各附 Excel 公式）、`pytest.ini` |
| 驗收：`python -m pytest tests/test_tvm.py` | 崩潰：`ValueError: mutable default ... hydra ... OverrideDirname`（step1 沒有 pytest.ini）→ **失敗**；加 `-p no:hydra_pytest` 後 5 passed | 同樣先崩潰；建 pytest.ini 後 RED（ImportError）→ GREEN 第一次 1 failed 7 passed（I/Y=0 未收斂）→ 修正後 9 passed |
| 驗收：`python tools/check_portable.py engine` | 找不到檔案 → **失敗** | 通過（exit 0）；故意加 `import decimal` → exit 1 |
| 驗收：`python tools/golden_dump.py` | 找不到檔案 → **失敗** | 找不到檔案 → **失敗**（Prompt 沒要求這支程式） |
| 房貸 PMT | -1798.65（測試有驗） | -1798.6515754582326，display "-1798.65" |
| 錯誤情境 | PV 與 PMT 同號求 N 回 **-183.72**；現金流全同號求利率沒收斂仍回 **0.1507**（15.07%）；I/Y 真值 0 回 1.48e-8 | N 無解、I/Y 無解都回 `{"ok": false}`；I/Y 真值 0 回 0.0 |

差異：一句話版本重現了本專案最在意的問題：看起來正常的錯數字（負期數、未收斂的利率）；四段式的【限制】逼出錯誤處理，但也在演練中踩到新坑（I/Y=0 的相消誤差），靠「I/Y 為 0」這個測試才抓到

## 回寫到 prompts.py 的新坑

- step0：step0 tag 的規格書仍寫 Pyodide、AST 白名單、decimal，與 Prompt 的 MicroPython 限制矛盾
- step0：`claude -p` 驗收需要已登入
- step0：`git show step0:CLAUDE.md` 只能在 clone 本 repo 的資料夾執行
- step1：驗收指令寫死作者的檔名 plan-2026-10-20.md
- step1：「規格同意後再拆計畫」用 `claude -p` 一次跑完沒有機會同意，要用互動對話
- step2：step1 tag 沒有 pytest.ini，本機 hydra 外掛讓 pytest 崩潰
- step2：驗收的 `tools/golden_dump.py` 不在 Prompt 的【介面】
- step2：I/Y 為 0% 時的相消誤差讓二分法回「未收斂」

## 建議（未改動，留給作者決定）

- 驗收指令的檔名與 tag 依賴：step1 改成 `docs/plan-*.md`、step0 的 `git show` 標明要在 clone 的 repo 執行
- step2 的【介面】加上 `pytest.ini`（含 `-p no:hydra_pytest`）與 `tools/golden_dump.py`，或從驗收拿掉 golden_dump
- 正式課前若能登入，建議用真正的 `claude -p` 再跑一次，取代本替身結果
