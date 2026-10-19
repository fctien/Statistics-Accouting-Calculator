# BACalc 開發歷程（DEVLOG）

只追加不改寫；失敗的嘗試也要寫明原因。

---

## 2026-10-19　規劃與規格書

**需求**
- 仿 BA II Plus／Professional 的會計計算 App，Python＋PWA，手機與電腦可用
- 功能：記憶與累加、商業與稅務、統計、利率轉換、現金流、分期攤還、TVM、顯示與位數設定；輸入要更人性化
- 資料存本機，可自行設定 Google Drive 或雲端上傳；每項功能都要自我測試
- 做成教學案例：CLAUDE.md → Prompt → PPT＋Prompt 卡，step by step

**做法**
- 用 brainstorming 流程：先說明理解 → 提三種架構（Pyodide／FastAPI／JS 重寫）→ 使用者選定 → 寫規格書
- 使用者決定：Pyodide 離線、放在 `Tien Research\BACalc`、JSON 匯出入＋Google Drive、教材 AI Agent 與 EMBA 兩版
- 參考既有 MoneyBook PWA 的規則（不產生錯數字、sw.js 快取清單、版本號同步）

**產出**
- `docs/spec-2026-10-19.md`、`docs/spec-2026-10-19.html`
- `CLAUDE.md`、`DEVLOG.md`、`tools/md2html.py`、`.gitignore`

**驗證**
- 規格自我檢查：無 TBD、章節間一致、範圍可拆成 M1–M6
- `tools/md2html.py` 實際轉出 HTML 並檢查表格有渲染

**問題與修正**
- 第一次用 AskUserQuestion 時使用者只回了資料夾路徑，其餘三題重新詢問後才確定

**待辦**
- 等使用者審閱規格書 → 寫實作計畫（writing-plans）→ 再次確認後開始 M1
