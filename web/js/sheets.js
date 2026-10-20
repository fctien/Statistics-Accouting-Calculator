// View 資料：各工作表的欄位定義（field definitions）；只有資料、沒有版面（版面在 Task 22～24）。
// 欄位 id（或 key）必須與 engine/bridge.py 模組說明的「輸入鍵對照表」完全相同，
// tests/test_web_sheets.py 會用每個欄位的 example 實際呼叫 bridge 驗證。
//
// 欄位屬性：
//   id       DOM 與表單內的唯一名稱；送給引擎的鍵為 key ?? id
//   key      （選用）引擎鍵與 id 不同時使用（STAT 預測的 X'／Y' 與資料清單 X／Y 同名）
//   out      （選用）引擎回傳值的鍵與 id 不同時使用（例：STAT 回傳 a、b 填入 A、B）
//   alias    （選用）引擎錯誤 field 的其他寫法（例：現金流錯誤 field 為 "CF"）
//   label    繁中名稱；abbr 英文／TI 縮寫；unit 單位（可空字串）
//   help     一行說明，含具體例子；example 輸入範例（也用作 placeholder）
//   kind     number | percent | date | direction | select | bool | list | text
//            direction＝金額＋「收到 ↓／付出 ↑」切換（收到為正、付出為負）
//            percent＝百分數（5 或 5% 都代表 5）；text＝自由文字（算式、星期等）
//   options  select 的選項 [{value, label}]
//   output   true＝只顯示引擎結果、不送出（唯讀）
//   initial  （選用）表單初始值（畫面上看得到，清除時恢復），direction 欄位可另給 initialDirection
//   positive / integer / min   即時驗證（input.js collect）
//   pairs    list 欄位每行為「金額 x 次數」
//
// 動作屬性：id（bridge action）、label、primary（Enter）、send（只送這些欄位）、
//   solve（留一格空白的可求解引擎鍵；全部有值時，上次求出的欄位再當未知數，見 input.resolveBlanks）

/** 合法的 kind（text 用於算式與文字輸出）。 */
export const KINDS = ["number", "percent", "date", "direction", "select", "bool", "list", "text"];

const BASIS = [
  { value: "ACT", label: "實際天數 ACT" },
  { value: "360", label: "30/360" },
];

// TVM 與 AMORT 共用的欄位
const TVM_FIELDS = [
  {
    id: "N", label: "期數", abbr: "N", unit: "期", kind: "number", example: "360",
    help: "總共付款幾期，例：30 年房貸每月繳 → 30 × 12 = 360",
  },
  {
    id: "IY", label: "年利率", abbr: "I/Y", unit: "%", kind: "percent", example: "6",
    help: "名目年利率（百分數），例：年息 6% 輸入 6 或 6%",
  },
  {
    id: "PV", label: "現值", abbr: "PV", unit: "元", kind: "direction", example: "100000",
    initialDirection: "in",
    help: "現在的金額，例：向銀行借 100,000 元 → 收到 100000",
  },
  {
    id: "PMT", label: "每期付款", abbr: "PMT", unit: "元", kind: "direction", example: "599.55",
    initialDirection: "out",
    help: "每期固定收付的金額，例：每月繳房貸 599.55 元 → 付出 599.55",
  },
  {
    id: "FV", label: "終值", abbr: "FV", unit: "元", kind: "direction", example: "0",
    initialDirection: "out",
    help: "最後一期結束時的金額，例：貸款還清 → 0",
  },
  {
    id: "PY", label: "每年付款次數", abbr: "P/Y", unit: "次／年", kind: "number", example: "12",
    initial: "12", positive: true,
    help: "一年付款幾次，例：每月繳 → 12；每年繳 → 1",
  },
  {
    id: "CY", label: "每年複利次數", abbr: "C/Y", unit: "次／年", kind: "number", example: "12",
    initial: "12", positive: true,
    help: "一年計息幾次，通常與 P/Y 相同，例：按月複利 → 12",
  },
  {
    id: "BGN", label: "期初付款", abbr: "BGN", unit: "", kind: "bool", example: "否",
    help: "勾選＝每期期初付款（BGN），不勾＝期末（END），例：房租通常期初付",
  },
];

/** 依 id 取出 TVM 欄位（AMORT 沿用）。 */
function tvmField(id) {
  return TVM_FIELDS.find((f) => f.id === id);
}

export const SHEETS = {
  tvm: {
    title: "貨幣時間價值 TVM", short: "TVM", route: "tvm", engine: "tvm",
    intro: "五個變數 N、I/Y、PV、PMT、FV 留一格空白，按「計算」就求出那一格",
    fields: TVM_FIELDS,
    actions: [{ id: "solve", label: "計算", primary: true, solve: ["N", "IY", "PV", "PMT", "FV"] }],
  },

  amort: {
    title: "攤還 AMORT", short: "攤還", route: "amort", engine: "amort",
    intro: "沿用 TVM 的貸款條件，計算第 P1～P2 期的本金、利息與餘額",
    fields: [
      ...TVM_FIELDS.map((f) => (f.id === "PMT" ? { ...f, help: "每期付款，例：先在 TVM 求出 PMT = 599.55（付出）" } : f)),
      {
        id: "P1", label: "起始期", abbr: "P1", unit: "期", kind: "number", example: "1",
        initial: "1", integer: true, positive: true,
        help: "攤還區間的第一期，例：第一年 → P1 = 1",
      },
      {
        id: "P2", label: "結束期", abbr: "P2", unit: "期", kind: "number", example: "12",
        initial: "12", integer: true, positive: true,
        help: "攤還區間的最後一期，例：第一年 → P2 = 12",
      },
      {
        id: "BAL", label: "期末餘額", abbr: "BAL", unit: "元", kind: "number", example: "98771.99",
        output: true, help: "P2 期結束後尚未償還的本金，例：第 12 期後餘額 98,771.99",
      },
      {
        id: "PRN", label: "已還本金", abbr: "PRN", unit: "元", kind: "number", example: "-1228.01",
        output: true, help: "P1～P2 期合計償還的本金（付出為負），例：-1,228.01",
      },
      {
        id: "INT", label: "已付利息", abbr: "INT", unit: "元", kind: "number", example: "-5966.59",
        output: true, help: "P1～P2 期合計支付的利息（付出為負），例：-5,966.59",
      },
    ],
    actions: [
      { id: "range", label: "計算區間", primary: true },
      { id: "schedule", label: "完整攤還表", send: ["N", "IY", "PV", "PMT", "FV", "PY", "CY", "BGN"] },
    ],
  },

  cashflow: {
    title: "現金流 CF", short: "現金流", route: "cf", engine: "cashflow",
    intro: "輸入期初現金流與之後各期現金流，計算 NPV、IRR 等指標",
    fields: [
      {
        id: "CF0", label: "期初現金流", abbr: "CF0", unit: "元", kind: "direction", example: "1000",
        initialDirection: "out", alias: ["CF"],
        help: "第 0 期的現金流，例：期初投資 1,000 元 → 付出 1000",
      },
      {
        id: "flows", label: "各期現金流", abbr: "C01…Cnn / F01…Fnn", unit: "元", kind: "list",
        pairs: true, example: "400 x 2; 500",
        help: "每行一筆「金額 x 次數」，付出寫負數，例：400 x 2; 500 表示 400、400、500",
      },
      {
        id: "I", label: "折現率", abbr: "I", unit: "%", kind: "percent", example: "10",
        help: "每期折現率（百分數），NPV、NFV、DPB 需要，例：資金成本 10% 輸入 10",
      },
      {
        id: "RI", label: "再投資率", abbr: "RI", unit: "%", kind: "percent", example: "8",
        help: "MIRR 用的再投資報酬率，例：再投資年報酬 8% 輸入 8",
      },
      { id: "NPV", label: "淨現值", abbr: "NPV", unit: "元", kind: "number", example: "69.87", output: true, help: "以折現率 I 折算的現值合計，例：69.87 > 0 代表值得投資" },
      { id: "IRR", label: "內部報酬率", abbr: "IRR", unit: "%", kind: "percent", example: "13.78", output: true, help: "使 NPV = 0 的折現率，例：13.78 代表 13.78%" },
      { id: "NFV", label: "淨終值", abbr: "NFV", unit: "元", kind: "number", example: "93.00", output: true, help: "NPV 換算到最後一期的價值，例：93.00" },
      { id: "MIRR", label: "修正內部報酬率", abbr: "MIRR", unit: "%", kind: "percent", example: "11.83", output: true, help: "考慮再投資率 RI 的報酬率，例：11.83 代表 11.83%" },
      { id: "PB", label: "回收期", abbr: "PB", unit: "期", kind: "number", example: "2.4", output: true, help: "累計現金流回到 0 所需期數（期內內插），例：2.4 期" },
      { id: "DPB", label: "折現回收期", abbr: "DPB", unit: "期", kind: "number", example: "2.81", output: true, help: "以折現後現金流計算的回收期，例：2.81 期" },
    ],
    actions: [
      { id: "npv", label: "NPV", primary: true },
      { id: "irr", label: "IRR" },
      { id: "nfv", label: "NFV" },
      { id: "mirr", label: "MIRR" },
      { id: "pb", label: "PB" },
      { id: "dpb", label: "DPB" },
    ],
  },

  iconv: {
    title: "利率換算 ICONV", short: "利率換算", route: "iconv", engine: "iconv",
    intro: "名目年利率 NOM 與有效年利率 EFF 互相換算",
    fields: [
      {
        id: "NOM", label: "名目年利率", abbr: "NOM", unit: "%", kind: "percent", example: "6",
        help: "銀行公告的年利率，例：年息 6%、按月複利 → NOM = 6",
      },
      {
        id: "EFF", label: "有效年利率", abbr: "EFF", unit: "%", kind: "percent", example: "6.17",
        help: "考慮複利後實際一年的報酬率，例：6% 按月複利 → EFF ≈ 6.17",
      },
      {
        id: "CY", label: "每年複利次數", abbr: "C/Y", unit: "次／年", kind: "number", example: "12",
        initial: "12", positive: true, help: "一年計息幾次，例：按月 → 12；按季 → 4",
      },
    ],
    actions: [
      { id: "to_eff", label: "NOM → EFF", primary: true, send: ["NOM", "CY"] },
      { id: "to_nom", label: "EFF → NOM", send: ["EFF", "CY"] },
    ],
  },

  stats: {
    title: "統計 STAT", short: "統計", route: "stat", engine: "stats",
    intro: "輸入資料計算單變數統計或迴歸，並可用迴歸式預測",
    fields: [
      {
        id: "X", label: "X 資料", abbr: "X", unit: "", kind: "list", example: "1 2 3 4 5",
        help: "以空白或換行分隔的數字，例：1 2 3 4 5",
      },
      {
        id: "F", label: "次數", abbr: "FRQ", unit: "次", kind: "list", example: "1 1 1 1 1",
        help: "每個 X 出現的次數（選填，單變數用），例：1 1 1 1 1",
      },
      {
        id: "Y", label: "Y 資料", abbr: "Y", unit: "", kind: "list", example: "2 4 5 4 5",
        help: "與 X 成對的數字（迴歸用），例：2 4 5 4 5",
      },
      {
        id: "model", label: "迴歸模型", abbr: "LIN/Ln/EXP/PWR", unit: "", kind: "select", example: "LIN",
        initial: "LIN",
        options: [
          { value: "LIN", label: "線性 LIN：y = a + bx" },
          { value: "LN", label: "對數 Ln：y = a + b ln x" },
          { value: "EXP", label: "指數 EXP：y = a·bˣ" },
          { value: "PWR", label: "乘冪 PWR：y = a·xᵇ" },
        ],
        help: "迴歸式的形式，例：資料大致成直線 → LIN",
      },
      {
        id: "A", label: "截距", abbr: "a", unit: "", kind: "number", example: "2.2", out: "a",
        help: "迴歸係數 a（計算迴歸後自動填入），例：2.2",
      },
      {
        id: "B", label: "斜率", abbr: "b", unit: "", kind: "number", example: "0.6", out: "b",
        help: "迴歸係數 b（計算迴歸後自動填入），例：0.6",
      },
      {
        id: "XP", key: "X", out: "x", label: "預測用 X", abbr: "X'", unit: "", kind: "number", example: "6",
        help: "已知 X 求 Y'（與 Y' 擇一填寫），例：X' = 6",
      },
      {
        id: "YP", key: "Y", out: "y", label: "預測用 Y", abbr: "Y'", unit: "", kind: "number", example: "5.8",
        help: "已知 Y 求 X'（與 X' 擇一填寫），例：Y' = 5.8",
      },
      { id: "n", label: "樣本數", abbr: "n", unit: "筆", kind: "number", example: "5", output: true, help: "資料筆數（含次數），例：5" },
      { id: "mean_x", label: "X 平均", abbr: "x̄", unit: "", kind: "number", example: "3", output: true, help: "X 的算術平均，例：3" },
      { id: "sx", label: "X 樣本標準差", abbr: "Sx", unit: "", kind: "number", example: "1.58", output: true, help: "除以 n−1 的標準差，例：1.58" },
      { id: "sigma_x", label: "X 母體標準差", abbr: "σx", unit: "", kind: "number", example: "1.41", output: true, help: "除以 n 的標準差，例：1.41" },
      { id: "mean_y", label: "Y 平均", abbr: "ȳ", unit: "", kind: "number", example: "4", output: true, help: "Y 的算術平均，例：4" },
      { id: "sy", label: "Y 樣本標準差", abbr: "Sy", unit: "", kind: "number", example: "1.22", output: true, help: "除以 n−1 的標準差，例：1.22" },
      { id: "sigma_y", label: "Y 母體標準差", abbr: "σy", unit: "", kind: "number", example: "1.10", output: true, help: "除以 n 的標準差，例：1.10" },
      { id: "r", label: "相關係數", abbr: "r", unit: "", kind: "number", example: "0.77", output: true, help: "介於 −1 與 1，越接近 ±1 線性關係越強，例：0.77" },
      { id: "sum_x", label: "X 總和", abbr: "Σx", unit: "", kind: "number", example: "15", output: true, help: "X 的總和，例：15" },
      { id: "sum_x2", label: "X 平方和", abbr: "Σx²", unit: "", kind: "number", example: "55", output: true, help: "X² 的總和，例：55" },
      { id: "sum_y", label: "Y 總和", abbr: "Σy", unit: "", kind: "number", example: "20", output: true, help: "Y 的總和，例：20" },
      { id: "sum_y2", label: "Y 平方和", abbr: "Σy²", unit: "", kind: "number", example: "86", output: true, help: "Y² 的總和，例：86" },
      { id: "sum_xy", label: "XY 乘積和", abbr: "Σxy", unit: "", kind: "number", example: "66", output: true, help: "X×Y 的總和，例：66" },
    ],
    actions: [
      { id: "one_var", label: "單變數 1-V", primary: true, send: ["X", "F"] },
      { id: "two_var", label: "迴歸", send: ["X", "Y", "model"] },
      { id: "predict", label: "預測", send: ["model", "A", "B", "XP", "YP"], solve: ["X", "Y"] },
    ],
  },

  bond: {
    title: "債券 BOND", short: "債券", route: "bond", engine: "bond",
    intro: "已知殖利率求價格，或已知價格求殖利率（每 100 元面額）",
    fields: [
      { id: "SDT", label: "交割日", abbr: "SDT", unit: "", kind: "date", example: "2026-06-12", help: "買進債券的交割日期，例：2026-06-12" },
      { id: "RDT", label: "到期日", abbr: "RDT", unit: "", kind: "date", example: "2034-12-31", help: "債券到期（贖回）日期，例：2034-12-31" },
      { id: "CPN", label: "票面利率", abbr: "CPN", unit: "%", kind: "percent", example: "7", help: "每年票息占面額的百分比，例：年息 7% 輸入 7" },
      { id: "RV", label: "贖回價值", abbr: "RV", unit: "每 100 元", kind: "number", example: "100", initial: "100", positive: true, help: "到期時每 100 元面額的贖回金額，例：平價贖回 → 100" },
      { id: "basis", label: "天數基準", abbr: "ACT/360", unit: "", kind: "select", example: "ACT", initial: "ACT", options: BASIS, help: "計息天數的算法，例：美國公債用 ACT，公司債多用 30/360" },
      {
        id: "freq", label: "付息頻率", abbr: "2/Y・1/Y", unit: "次／年", kind: "select", example: "2", initial: "2",
        options: [{ value: 2, label: "每年兩次 2/Y" }, { value: 1, label: "每年一次 1/Y" }],
        help: "一年付幾次票息，例：半年付息 → 2/Y",
      },
      { id: "YLD", label: "殖利率", abbr: "YLD", unit: "%", kind: "percent", example: "8", help: "到期殖利率（百分數），求價格時輸入，例：8" },
      { id: "PRI", label: "價格", abbr: "PRI", unit: "每 100 元", kind: "number", example: "93.89", help: "每 100 元面額的淨價，求殖利率時輸入，例：93.89" },
      { id: "AI", label: "應計利息", abbr: "AI", unit: "每 100 元", kind: "number", example: "3.15", output: true, help: "上次付息日到交割日累積的利息，例：3.15" },
    ],
    actions: [
      { id: "price", label: "求價格 PRI", primary: true, send: ["SDT", "RDT", "CPN", "RV", "basis", "freq", "YLD"] },
      { id: "yield", label: "求殖利率 YLD", send: ["SDT", "RDT", "CPN", "RV", "basis", "freq", "PRI"] },
    ],
  },

  depr: {
    title: "折舊 DEPR", short: "折舊", route: "depr", engine: "depr",
    intro: "依折舊方法計算某一年的折舊，或列出完整折舊表",
    fields: [
      {
        id: "method", label: "折舊方法", abbr: "SL/SYD/DB/DBX", unit: "", kind: "select", example: "SL", initial: "SL",
        options: [
          { value: "SL", label: "直線法 SL" },
          { value: "SYD", label: "年數合計法 SYD" },
          { value: "DB", label: "定率遞減法 DB" },
          { value: "DBX", label: "遞減轉直線 DBX" },
        ],
        help: "折舊的計算方式，例：每年折舊金額相同 → 直線法 SL",
      },
      { id: "CST", label: "成本", abbr: "CST", unit: "元", kind: "number", example: "1000000", min: 0, help: "資產取得成本，例：機器 1,000,000 元" },
      { id: "SAL", label: "殘值", abbr: "SAL", unit: "元", kind: "number", example: "100000", min: 0, help: "使用年限結束時的估計價值，例：100,000 元" },
      { id: "LIF", label: "耐用年限", abbr: "LIF", unit: "年", kind: "number", example: "5", positive: true, help: "預計使用幾年，例：5 年" },
      { id: "M01", label: "起始月份", abbr: "M01", unit: "月", kind: "number", example: "1", initial: "1", help: "第一年從幾月開始折舊，例：1 月購入 → 1" },
      { id: "DB", label: "遞減率", abbr: "DB%", unit: "%", kind: "percent", example: "200", initial: "200", positive: true, help: "定率遞減法的倍率（百分數），例：倍數餘額遞減 → 200" },
      { id: "YR", label: "年度", abbr: "YR", unit: "年", kind: "number", example: "1", initial: "1", integer: true, positive: true, help: "要看第幾年的折舊，例：第 1 年 → 1" },
      { id: "DEP", label: "本年折舊", abbr: "DEP", unit: "元", kind: "number", example: "180000", output: true, help: "該年度的折舊金額，例：180,000" },
      { id: "RBV", label: "剩餘帳面價值", abbr: "RBV", unit: "元", kind: "number", example: "820000", output: true, help: "成本減累計折舊，例：820,000" },
      { id: "RDV", label: "剩餘可折舊價值", abbr: "RDV", unit: "元", kind: "number", example: "720000", output: true, help: "帳面價值減殘值，例：720,000" },
    ],
    actions: [
      { id: "year", label: "計算該年", primary: true },
      { id: "schedule", label: "完整折舊表", send: ["method", "CST", "SAL", "LIF", "M01", "DB"] },
    ],
  },

  "business-profit": {
    title: "毛利與加成 PROFIT", short: "毛利", route: "profit", engine: "business", group: "商業",
    intro: "成本、售價、毛利率、加成率留空白求解",
    fields: [
      { id: "CST", label: "成本", abbr: "CST", unit: "元", kind: "number", example: "80", help: "商品成本，例：進貨 80 元" },
      { id: "SEL", label: "售價", abbr: "SEL", unit: "元", kind: "number", example: "100", help: "商品售價，例：賣 100 元" },
      { id: "MAR", label: "毛利率", abbr: "MAR", unit: "%", kind: "percent", example: "20", help: "毛利占售價的百分比，例：(100 − 80) ÷ 100 = 20" },
      { id: "MU", label: "加成率", abbr: "MU", unit: "%", kind: "percent", example: "25", help: "毛利占成本的百分比，例：(100 − 80) ÷ 80 = 25" },
    ],
    actions: [{ id: "profit", label: "計算", primary: true, solve: ["CST", "SEL", "MAR", "MU"] }],
  },

  "business-breakeven": {
    title: "損益兩平 BRKEVN", short: "損益兩平", route: "brkevn", engine: "business", group: "商業",
    intro: "固定成本、變動成本、售價、利潤、數量留一格空白求解",
    fields: [
      { id: "FC", label: "固定成本", abbr: "FC", unit: "元", kind: "number", example: "10000", help: "不隨數量變動的成本，例：月租 10,000 元" },
      { id: "VC", label: "單位變動成本", abbr: "VC", unit: "元／件", kind: "number", example: "6", help: "每多做一件增加的成本，例：材料 6 元" },
      { id: "P", label: "單價", abbr: "P", unit: "元／件", kind: "number", example: "10", help: "每件售價，例：10 元" },
      { id: "PFT", label: "利潤", abbr: "PFT", unit: "元", kind: "number", example: "0", help: "目標利潤，例：損益兩平 → 0" },
      { id: "Q", label: "數量", abbr: "Q", unit: "件", kind: "number", example: "2500", help: "銷售數量，例：(10000 + 0) ÷ (10 − 6) = 2,500 件" },
    ],
    actions: [{ id: "breakeven", label: "計算", primary: true, solve: ["FC", "VC", "P", "PFT", "Q"] }],
  },

  "business-pct": {
    title: "百分比變動 Δ%", short: "Δ%", route: "pct", engine: "business", group: "商業",
    intro: "舊值、新值、變動率、期數留一格空白求解；期數大於 1 為複利成長",
    fields: [
      { id: "OLD", label: "舊值", abbr: "OLD", unit: "", kind: "number", example: "100", help: "變動前的數值，例：去年營收 100" },
      { id: "NEW", label: "新值", abbr: "NEW", unit: "", kind: "number", example: "121", help: "變動後的數值，例：今年營收 121" },
      { id: "PCT", label: "每期變動率", abbr: "%CH", unit: "%", kind: "percent", example: "10", help: "每期成長的百分比，例：兩年從 100 到 121 → 每年 10" },
      { id: "PD", label: "期數", abbr: "#PD", unit: "期", kind: "number", example: "2", initial: "1", help: "經過幾期，例：兩年 → 2；單純比較兩數 → 1" },
    ],
    actions: [{ id: "pct_change", label: "計算", primary: true, solve: ["OLD", "NEW", "PCT", "PD"] }],
  },

  tax: {
    title: "稅額 TAX", short: "稅額", route: "tax", engine: "business", group: "商業",
    intro: "由未稅或含稅金額計算稅額（以「分」整數計算，四捨五入到分）",
    fields: [
      { id: "AMOUNT", label: "金額", abbr: "AMT", unit: "元", kind: "number", example: "1000", help: "未稅或含稅金額（依下方計算方式），例：1,000 元" },
      { id: "RATE", label: "稅率", abbr: "RATE", unit: "%", kind: "percent", example: "5", initial: "5", help: "稅率（百分數），例：營業稅 5%" },
      {
        id: "MODE", label: "計算方式", abbr: "MODE", unit: "", kind: "select", example: "exclusive", initial: "exclusive",
        options: [
          { value: "exclusive", label: "外加：金額為未稅價" },
          { value: "inclusive", label: "內含：金額為含稅價" },
        ],
        help: "金額是否已含稅，例：報價 1,000 未稅 → 外加",
      },
      { id: "net", label: "未稅金額", abbr: "NET", unit: "元", kind: "number", example: "1000", output: true, help: "不含稅的金額，例：1,000.00" },
      { id: "tax", label: "稅額", abbr: "TAX", unit: "元", kind: "number", example: "50", output: true, help: "應繳稅額，例：1,000 × 5% = 50.00" },
      { id: "gross", label: "含稅金額", abbr: "GROSS", unit: "元", kind: "number", example: "1050", output: true, help: "未稅金額加稅額，例：1,050.00" },
    ],
    actions: [{ id: "tax", label: "計算", primary: true }],
  },

  date: {
    title: "日期 DATE", short: "日期", route: "date", engine: "date", group: "商業",
    intro: "兩個日期與相差天數留一格空白求解",
    fields: [
      { id: "DT1", label: "起始日", abbr: "DT1", unit: "", kind: "date", example: "2026-01-01", help: "開始日期，例：2026-01-01" },
      { id: "DT2", label: "結束日", abbr: "DT2", unit: "", kind: "date", example: "2026-12-31", help: "結束日期，例：2026-12-31" },
      { id: "DBD", label: "相差天數", abbr: "DBD", unit: "天", kind: "number", example: "364", help: "兩日期之間的天數，例：2026-01-01 到 2026-12-31 → 364" },
      { id: "basis", label: "天數基準", abbr: "ACT/360", unit: "", kind: "select", example: "ACT", initial: "ACT", options: BASIS, help: "實際天數或每月 30 天，例：一般用 ACT" },
      { id: "weekday1", label: "起始日星期", abbr: "DOW1", unit: "", kind: "text", example: "星期四", output: true, help: "起始日是星期幾，例：星期四" },
      { id: "weekday2", label: "結束日星期", abbr: "DOW2", unit: "", kind: "text", example: "星期四", output: true, help: "結束日是星期幾，例：星期四" },
    ],
    actions: [{ id: "solve", label: "計算", primary: true, solve: ["DT1", "DT2", "DBD"] }],
  },

  calc: {
    title: "計算機 CALC", short: "計算機", route: "calc", engine: "calc",
    intro: "輸入算式計算；支援 + − × ÷ ^ ( ) % √ 與 ANS",
    fields: [
      { id: "EXPR", label: "算式", abbr: "EXPR", unit: "", kind: "text", example: "2+3×4", alias: ["expr"], help: "要計算的算式，例：2+3×4（AOS 結果 14）" },
      { id: "ANS", label: "上次答案", abbr: "ANS", unit: "", kind: "number", example: "14", help: "算式中 ANS 代表的數值，例：上一題答案 14" },
      { id: "value", label: "結果", abbr: "=", unit: "", kind: "number", example: "14", output: true, help: "算式的計算結果，例：14" },
    ],
    actions: [{ id: "eval", label: "＝ 計算", primary: true }],
  },

  settings: {
    title: "設定 FORMAT", short: "設定", route: "settings", engine: null,
    intro: "顯示格式與運算順序；只存在這台裝置",
    fields: [
      {
        id: "decimals", label: "小數位數", abbr: "DEC", unit: "位", kind: "select", example: "2", initial: "2",
        options: [
          ...Array.from({ length: 10 }, (_, i) => ({ value: i, label: String(i) })),
          { value: null, label: "浮動 F" },
        ],
        help: "結果顯示幾位小數，例：2 → 599.55；浮動 → 599.5505252",
      },
      {
        id: "sep", label: "千分位格式", abbr: "SEP", unit: "", kind: "select", example: "us", initial: "us",
        options: [{ value: "us", label: "1,000.00（美式）" }, { value: "eu", label: "1.000,00（歐式）" }],
        help: "千分位與小數點符號，例：美式 1,234.56、歐式 1.234,56",
      },
      {
        id: "mode", label: "運算順序", abbr: "AOS/Chn", unit: "", kind: "select", example: "AOS", initial: "AOS",
        options: [{ value: "AOS", label: "代數順序 AOS" }, { value: "CHAIN", label: "依序 Chain" }],
        help: "計算機的運算順序，例：2+3×4 在 AOS 為 14、Chain 為 20",
      },
      {
        id: "theme", label: "外觀", abbr: "THEME", unit: "", kind: "select", example: "auto", initial: "auto",
        options: [{ value: "auto", label: "跟隨系統" }, { value: "light", label: "淺色" }, { value: "dark", label: "深色" }],
        help: "淺色或深色畫面，例：晚上使用選深色",
      },
    ],
    actions: [{ id: "save", label: "套用", primary: true }],
  },
};

/** 側邊選單的順序（全部工作表）。 */
export const SHEET_ORDER = [
  "tvm", "amort", "cashflow", "iconv", "bond", "depr", "stats",
  "business-profit", "business-breakeven", "business-pct", "tax", "date",
  "calc", "settings",
];

/** 手機底部分頁列的 5 個主要工作表（其餘放「更多」）。 */
export const PRIMARY_SHEETS = ["tvm", "cashflow", "amort", "bond", "calc"];

/** {欄位 id: 欄位定義}。 */
export function fieldMap(sheetId) {
  const out = {};
  for (const f of SHEETS[sheetId].fields) out[f.id] = f;
  return out;
}

/** 動作要送出的欄位（action.send 指定；否則為全部非輸出欄位）。 */
export function sendFields(sheetId, actionId) {
  const sheet = SHEETS[sheetId];
  const action = sheet.actions.find((a) => a.id === actionId) || sheet.actions[0];
  if (action.send) {
    const fm = fieldMap(sheetId);
    return action.send.map((id) => fm[id]);
  }
  return sheet.fields.filter((f) => !f.output);
}

/** 主要動作（Enter 觸發）。 */
export function primaryAction(sheetId) {
  return SHEETS[sheetId].actions.find((a) => a.primary);
}

/** 由 hash 路由找工作表 id；找不到回傳 null。 */
export function sheetByRoute(route) {
  return SHEET_ORDER.find((id) => SHEETS[id].route === route) || null;
}

/** 在欄位清單中依序找：引擎鍵（key ?? id）→ 回傳鍵 out → id → 別名 → 不分大小寫。 */
function matchIn(fields, key) {
  const low = String(key).toLowerCase();
  return fields.find((f) => (f.key || f.id) === key)
    || fields.find((f) => f.out === key)
    || fields.find((f) => f.id === key)
    || fields.find((f) => (f.alias || []).includes(key))
    || fields.find((f) => f.id.toLowerCase() === low || (f.key || "").toLowerCase() === low)
    || null;
}

/**
 * 由引擎回傳的鍵（值的鍵或錯誤的 field）找欄位定義；找不到回傳 null。
 * 給了 actionId 時先在該動作送出的欄位中找（例：STAT 預測的錯誤 field "X" 是 X' 欄，
 * 不是資料清單 X），找不到再全域找（回傳鍵 out／id 優先，例：迴歸的 a、b 對到 A、B 欄）。
 */
export function fieldForKey(sheetId, key, actionId) {
  if (key === null || key === undefined || key === "" || !SHEETS[sheetId]) return null;
  if (actionId && SHEETS[sheetId].actions.some((x) => x.id === actionId)) {
    const hit = matchIn(sendFields(sheetId, actionId), key);
    if (hit) return hit;
  }
  const all = SHEETS[sheetId].fields;
  const low = String(key).toLowerCase();
  return all.find((f) => (f.out || f.id) === key)
    || all.find((f) => f.id === key || f.key === key)
    || all.find((f) => (f.alias || []).includes(key))
    || all.find((f) => f.id.toLowerCase() === low)
    || null;
}
