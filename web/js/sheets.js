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
//   kind     number | percent | date | direction | select | bool | list | text | matrix
//            matrix＝二維數表（列以分號或換行分隔，例：10 20; 30 40；統計頁由表格提供）
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
export const KINDS = ["number", "percent", "date", "direction", "select", "bool", "list", "text", "matrix"];

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

// 進位轉換（base）共用的選項
const BASE_RADIX = [
  { value: 2, label: "二進位 2" }, { value: 8, label: "八進位 8" },
  { value: 10, label: "十進位 10" }, { value: 16, label: "十六進位 16" },
];
const BASE_WIDTH = [8, 16, 32, 64].map((v) => ({ value: v, label: `${v} 位元` }));

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
      {
        id: "predict", label: "預測", send: ["model", "A", "B", "XP", "YP"], solve: ["X", "Y"],
        // a、b 是迴歸求出的係數：過期（改了模型或資料）時不可拿來預測
        fresh: ["A", "B"], freshHint: "請先重新計算迴歸（按「迴歸」）再預測",
      },
    ],
  },

  describe: {
    title: "敘述統計 DESC", short: "敘述統計", route: "desc", engine: "stats",
    intro: "輸入資料（可加次數、可從 Excel 貼上），求集中趨勢、離散程度、四分位數與分配形狀",
    fields: [
      { id: "X", label: "X 資料", abbr: "X", unit: "", kind: "list", example: "2 4 4 4 5 5 7 9", help: "以空白或換行分隔的數字，例：2 4 4 4 5 5 7 9" },
      { id: "F", label: "次數", abbr: "FRQ", unit: "次", kind: "list", example: "1 1 1 1 1 1 1 1", help: "每個 X 出現的次數（選填），例：1 1 1 1 1 1 1 1" },
      { id: "n", label: "樣本數", abbr: "n", unit: "筆", kind: "number", example: "8", output: true, help: "資料筆數（含次數），例：8" },
      { id: "sum", label: "總和", abbr: "Σx", unit: "", kind: "number", example: "40", output: true, help: "所有資料的總和，例：40" },
      { id: "mean", label: "平均數", abbr: "x̄", unit: "", kind: "number", example: "5", output: true, help: "算術平均，例：5" },
      { id: "median", label: "中位數", abbr: "Med", unit: "", kind: "number", example: "4.5", output: true, help: "排序後位於中間的值，例：4.5" },
      { id: "min", label: "最小值", abbr: "Min", unit: "", kind: "number", example: "2", output: true, help: "最小的資料，例：2" },
      { id: "max", label: "最大值", abbr: "Max", unit: "", kind: "number", example: "9", output: true, help: "最大的資料，例：9" },
      { id: "range", label: "全距", abbr: "Range", unit: "", kind: "number", example: "7", output: true, help: "最大值 − 最小值，例：7" },
      { id: "var", label: "樣本變異數", abbr: "s²", unit: "", kind: "number", example: "4.57", output: true, help: "除以 n−1 的變異數（Excel VAR.S），例：4.57" },
      { id: "sx", label: "樣本標準差", abbr: "Sx", unit: "", kind: "number", example: "2.14", output: true, help: "除以 n−1 的標準差（Excel STDEV.S），例：2.14" },
      { id: "sigma_x", label: "母體標準差", abbr: "σx", unit: "", kind: "number", example: "2", output: true, help: "除以 n 的標準差（Excel STDEV.P），例：2" },
      { id: "cv", label: "變異係數", abbr: "CV", unit: "", kind: "number", example: "0.43", output: true, help: "Sx ÷ 平均數，例：0.43" },
      { id: "q1", label: "第一四分位數", abbr: "Q1", unit: "", kind: "number", example: "4", output: true, help: "依 Excel QUARTILE.INC（位置 (n−1)·p 線性內插）計算，例：4；與「半部中位數」法（如部分計算機）結果可能不同" },
      { id: "q3", label: "第三四分位數", abbr: "Q3", unit: "", kind: "number", example: "5.5", output: true, help: "依 Excel QUARTILE.INC（位置 (n−1)·p 線性內插）計算，例：5.5；與「半部中位數」法（如部分計算機）結果可能不同" },
      { id: "iqr", label: "四分位距", abbr: "IQR", unit: "", kind: "number", example: "1.5", output: true, help: "Q3 − Q1，例：1.5" },
      { id: "skew", label: "偏態", abbr: "Skew", unit: "", kind: "number", example: "0.82", output: true, help: "分配左右不對稱的程度（Excel SKEW），例：0.82（右偏）" },
      { id: "kurt", label: "峰態", abbr: "Kurt", unit: "", kind: "number", example: "0.94", output: true, help: "尾巴厚薄的程度（超額峰態，Excel KURT），例：0.94" },
    ],
    actions: [{ id: "describe", label: "計算", primary: true, send: ["X", "F"] }],
  },

  dist: {
    title: "機率分配 DIST", short: "機率分配", route: "dist", engine: "dist",
    intro: "選分配與功能：pdf／pmf（機率密度／機率）、cdf（累積機率）、inv（給機率反查臨界值）",
    fields: [
      {
        id: "DIST", label: "分配", abbr: "DIST", unit: "", kind: "select", example: "normal", initial: "normal",
        options: [
          { value: "normal", label: "常態 Normal(μ, σ)" },
          { value: "t", label: "t 分配 t(df)" },
          { value: "chi2", label: "卡方 χ²(df)" },
          { value: "binom", label: "二項 Binomial(n, p)" },
          { value: "poisson", label: "Poisson(λ)" },
        ],
        help: "機率分配的種類，例：考試成績近似常態 → 常態",
      },
      {
        id: "FUNC", label: "功能", abbr: "FUNC", unit: "", kind: "select", example: "cdf", initial: "cdf",
        options: [
          { value: "pdf", label: "pdf／pmf：密度或 P(X = k)" },
          { value: "cdf", label: "cdf：累積機率 P(X ≤ x)" },
          { value: "inv", label: "inv：給機率反查臨界值" },
        ],
        help: "要算什麼，例：P(Z ≤ 1.96) 選 cdf；找 97.5% 分位數選 inv",
      },
      { id: "MU", label: "平均數", abbr: "μ", unit: "", kind: "number", example: "0", initial: "0", help: "常態分配的平均數，例：標準常態 μ = 0" },
      { id: "SIGMA", label: "標準差", abbr: "σ", unit: "", kind: "number", example: "1", initial: "1", positive: true, help: "常態分配的標準差（> 0），例：標準常態 σ = 1" },
      { id: "DF", label: "自由度", abbr: "df", unit: "", kind: "number", example: "5", positive: true, help: "t 或卡方的自由度（可非整數），例：樣本 6 筆的 t → df = 5" },
      { id: "N", label: "試驗次數", abbr: "n", unit: "次", kind: "number", example: "10", integer: true, help: "二項分配的試驗次數，例：丟 10 次硬幣 → 10" },
      { id: "P", label: "成功機率", abbr: "p", unit: "", kind: "number", example: "0.3", help: "每次試驗成功的機率（0～1），例：0.3" },
      { id: "LAMBDA", label: "平均次數", abbr: "λ", unit: "", kind: "number", example: "2", positive: true, help: "Poisson 單位時間平均發生次數，例：每小時平均 2 位客人 → 2" },
      { id: "X", label: "x 值", abbr: "x", unit: "", kind: "number", example: "1.96", help: "要算密度或累積機率的位置，例：1.96" },
      { id: "K", label: "次數", abbr: "k", unit: "次", kind: "number", example: "3", integer: true, help: "離散分配的次數（整數 ≥ 0），例：10 次中成功 3 次 → 3" },
      { id: "PROB", label: "機率", abbr: "p", unit: "", kind: "number", example: "0.975", help: "反查用的機率（0～1，不含兩端）；左尾、右尾、雙尾臨界值分別使 P(X ≤ x)、P(X > x)、雙尾機率等於 p，例：0.975" },
    ],
    // 動作＝分配（bridge action）；畫面只顯示一個「計算」鈕，依「分配」選單決定送哪一個
    actions: [
      { id: "normal", label: "計算", primary: true, send: ["FUNC", "MU", "SIGMA", "X", "PROB"] },
      { id: "t", label: "計算 t", send: ["FUNC", "DF", "X", "PROB"] },
      { id: "chi2", label: "計算 χ²", send: ["FUNC", "DF", "X", "PROB"] },
      { id: "binom", label: "計算二項", send: ["FUNC", "N", "P", "K"] },
      { id: "poisson", label: "計算 Poisson", send: ["FUNC", "LAMBDA", "K"] },
    ],
  },

  infer: {
    title: "信賴區間與檢定 INFER", short: "信賴區間與檢定", route: "infer", engine: "infer",
    intro: "選類型 → 輸入資料或摘要值 → 得到區間或檢定統計量、p 值與結論",
    fields: [
      {
        id: "TYPE", label: "類型", abbr: "TYPE", unit: "", kind: "select", example: "ci_mean_z", initial: "ci_mean_z",
        options: [
          { value: "ci_mean_z", label: "平均數信賴區間（σ 已知，z）" },
          { value: "ci_mean_t", label: "平均數信賴區間（σ 未知，t）" },
          { value: "ci_prop", label: "比例信賴區間" },
          { value: "t1", label: "單樣本 t 檢定" },
          { value: "t2", label: "兩樣本 t 檢定（合併／Welch）" },
          { value: "tpaired", label: "成對 t 檢定" },
          { value: "chi_gof", label: "卡方適合度檢定" },
          { value: "chi_ind", label: "卡方獨立性檢定" },
        ],
        help: "要做哪一種推論，例：比較兩班平均成績 → 兩樣本 t 檢定",
      },
      {
        id: "CI_INPUT", label: "資料形式", abbr: "INPUT", unit: "", kind: "select", example: "data", initial: "data",
        options: [{ value: "data", label: "原始資料（表格）" }, { value: "summary", label: "摘要值（x̄、Sx、n）" }],
        help: "用原始資料或已算好的摘要值，例：只知道平均 50、標準差 12 → 摘要值",
      },
      {
        id: "GOF_EXP", label: "期望", abbr: "EXP", unit: "", kind: "select", example: "uniform", initial: "uniform",
        options: [
          { value: "uniform", label: "各類別均等" },
          { value: "exp", label: "自訂期望次數" },
          { value: "probs", label: "自訂機率" },
        ],
        help: "各類別的期望，例：骰子公平 → 均等；已知比例 2:1:1 → 自訂機率 0.5 0.25 0.25",
      },
      { id: "MEAN", label: "樣本平均", abbr: "x̄", unit: "", kind: "number", example: "50", help: "樣本平均數，例：50" },
      { id: "SIGMA", label: "母體標準差", abbr: "σ", unit: "", kind: "number", example: "10", positive: true, help: "已知的母體標準差，例：10" },
      { id: "SX", label: "樣本標準差", abbr: "Sx", unit: "", kind: "number", example: "12", positive: true, help: "樣本標準差（除以 n−1），例：12" },
      { id: "XC", key: "X", label: "成功數", abbr: "x", unit: "", kind: "number", example: "12", integer: true, help: "樣本中具有該特性的個數，例：30 人中 12 人贊成 → 12" },
      { id: "N", label: "樣本數", abbr: "n", unit: "筆", kind: "number", example: "30", integer: true, help: "樣本大小，例：30" },
      { id: "MU0", label: "假設平均", abbr: "μ0", unit: "", kind: "number", example: "25", help: "虛無假設的母體平均，例：H0：μ = 25" },
      { id: "EQUAL_VAR", label: "假設變異數相等（合併 pooled）", abbr: "POOLED", unit: "", kind: "bool", example: "否", help: "勾選＝合併變異數（Excel T.TEST type 2）；不勾＝Welch（type 3），例：不確定時不勾" },
      {
        id: "H1", label: "對立假設", abbr: "H1", unit: "", kind: "select", example: "two", initial: "two",
        options: [
          { value: "two", label: "雙尾 ≠" },
          { value: "less", label: "左尾 <" },
          { value: "greater", label: "右尾 >" },
        ],
        help: "對立假設的方向，例：新方法是否「提高」成績 → 右尾 >",
      },
      { id: "CONF", label: "信賴水準", abbr: "CONF", unit: "", kind: "number", example: "0.95", initial: "0.95", help: "0～1 之間，例：95% 信賴區間 → 0.95" },
      { id: "ALPHA", label: "顯著水準", abbr: "α", unit: "", kind: "number", example: "0.05", initial: "0.05", help: "拒絕 H0 的門檻（0～1），例：0.05" },
      // 以下由表格提供（畫面不顯示這些欄位；欄位定義讓 bridge 鍵對照表測試能以 example 實測）
      { id: "XS", key: "X", label: "X 資料", abbr: "X", unit: "", kind: "list", example: "23 25 28 30 27 26", help: "樣本資料（表格），例：23 25 28 30 27 26" },
      { id: "YS", key: "Y", label: "Y 資料", abbr: "Y", unit: "", kind: "list", example: "20 22 21 25 23 19", help: "第二組或成對的資料（表格），例：20 22 21 25 23 19" },
      { id: "OBS", label: "觀察次數", abbr: "OBS", unit: "", kind: "list", example: "18 22 20", help: "各類別的觀察次數（表格），例：18 22 20" },
      { id: "EXP", label: "期望次數", abbr: "EXP", unit: "", kind: "list", example: "20 20 20", help: "各類別的期望次數（表格），例：20 20 20" },
      { id: "PROBS", label: "期望機率", abbr: "PROBS", unit: "", kind: "list", example: "0.5 0.25 0.25", help: "各類別的機率（表格），例：0.5 0.25 0.25" },
      { id: "TABLE", label: "列聯表", abbr: "TABLE", unit: "", kind: "matrix", example: "10 20; 30 40", help: "r × c 觀察次數（表格），例：10 20; 30 40" },
    ],
    // 動作＝類型（bridge action）；畫面只顯示一個「計算」鈕，依「類型」選單決定送哪一個
    actions: [
      { id: "ci_mean_z", label: "計算", primary: true, send: ["MEAN", "SIGMA", "N", "CONF"] },
      { id: "ci_mean_t", label: "計算 CI t", send: ["XS", "MEAN", "SX", "N", "CONF"] },
      { id: "ci_prop", label: "計算比例 CI", send: ["XC", "N", "CONF"] },
      { id: "t1", label: "單樣本 t", send: ["XS", "MU0", "ALPHA"] },
      { id: "t2", label: "兩樣本 t", send: ["XS", "YS", "EQUAL_VAR", "ALPHA"] },
      { id: "tpaired", label: "成對 t", send: ["XS", "YS", "ALPHA"] },
      { id: "chi_gof", label: "適合度", send: ["OBS", "EXP", "PROBS", "ALPHA"] },
      { id: "chi_ind", label: "獨立性", send: ["TABLE", "ALPHA"] },
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
    title: "科學計算機 CALC", short: "科學計算機", route: "calc", engine: "calc",
    intro: "輸入算式計算；支援 + − × ÷ ^ ( ) % √ ∛ sin cos tan log ln π e 與 ANS，角度可切換 DEG／RAD",
    fields: [
      { id: "EXPR", label: "算式", abbr: "EXPR", unit: "", kind: "text", example: "2+3×4", alias: ["expr"], help: "要計算的算式，例：2+3×4（AOS 結果 14）" },
      { id: "ANS", label: "上次答案", abbr: "ANS", unit: "", kind: "number", example: "14", help: "算式中 ANS 代表的數值，例：上一題答案 14" },
      { id: "value", label: "結果", abbr: "=", unit: "", kind: "number", example: "14", output: true, help: "算式的計算結果，例：14" },
    ],
    actions: [{ id: "eval", label: "＝ 計算", primary: true }],
  },

  units: {
    title: "單位換算 UNITS", short: "單位換算", route: "units", engine: "units",
    intro: "選類別與單位，輸入數值即時換算；⇄ 交換單位",
    fields: [
      { id: "VALUE", label: "數值", abbr: "VAL", unit: "", kind: "number", example: "1", help: "要換算的數值，例：1 英里輸入 1" },
      { id: "FROM", label: "從單位", abbr: "FROM", unit: "", kind: "text", example: "mi", help: "原本的單位 id，例：英里 mi" },
      { id: "TO", label: "到單位", abbr: "TO", unit: "", kind: "text", example: "km", help: "要換成的單位 id（同一類別），例：公里 km" },
      { id: "value", label: "結果", abbr: "=", unit: "", kind: "number", example: "1.61", output: true, help: "換算結果（依小數位數設定），例：1 mi = 1.61 km（2 位小數）" },
    ],
    actions: [
      { id: "convert", label: "換算", primary: true, send: ["VALUE", "FROM", "TO"] },
      { id: "list", label: "單位清單", send: [] },
    ],
  },

  base: {
    title: "進位轉換 BASE", short: "進位轉換", route: "base", engine: "base",
    intro: "BIN／OCT／DEC／HEX 四欄同步；可選位寬與有號／無號，並做位元運算",
    fields: [
      { id: "TEXT", label: "輸入值", abbr: "TEXT", unit: "", kind: "text", example: "255", help: "以 FROM 進位寫的整數，例：十進位 255" },
      { id: "FROM", label: "輸入進位", abbr: "FROM", unit: "", kind: "select", example: "10", options: BASE_RADIX, help: "輸入值的進位，例：十進位 10" },
      { id: "WIDTH", label: "位寬", abbr: "WIDTH", unit: "位元", kind: "select", example: "8", options: BASE_WIDTH, help: "整數的位元數，例：8 位元無號為 0～255" },
      { id: "SIGNED", label: "有號數", abbr: "SIGNED", unit: "", kind: "bool", example: "否", help: "勾選＝二補數有號數，例：8 位元有號為 −128～127" },
      { id: "BIN", label: "二進位", abbr: "BIN", unit: "", kind: "text", example: "11111111", output: true, help: "二進位結果，例：255 → 11111111" },
      { id: "OCT", label: "八進位", abbr: "OCT", unit: "", kind: "text", example: "377", output: true, help: "八進位結果，例：255 → 377" },
      { id: "DEC", label: "十進位", abbr: "DEC", unit: "", kind: "text", example: "255", output: true, help: "十進位結果，例：255" },
      { id: "HEX", label: "十六進位", abbr: "HEX", unit: "", kind: "text", example: "FF", output: true, help: "十六進位結果，例：255 → FF" },
    ],
    actions: [{ id: "convert", label: "轉換", primary: true }],
  },

  "base-bitwise": {
    title: "位元運算 BITWISE", short: "位元運算", route: "base-bitwise", engine: "base",
    embeddedIn: "base", // 內嵌在進位轉換畫面（views/base.js），導覽不單獨列出
    intro: "A、B 依目前進位解讀，做 AND OR XOR NOT SHL SHR SAR",
    fields: [
      {
        id: "OP", label: "運算", abbr: "OP", unit: "", kind: "select", example: "AND",
        options: ["AND", "OR", "XOR", "NOT", "SHL", "SHR", "SAR"].map((v) => ({ value: v, label: v })),
        help: "位元運算，例：12 AND 10 = 8",
      },
      { id: "A", label: "運算元 A", abbr: "A", unit: "", kind: "text", example: "12", help: "依目前進位寫的整數，例：十進位 12" },
      { id: "B", label: "運算元 B", abbr: "B", unit: "", kind: "text", example: "10", help: "第二個運算元或位移量，例：十進位 10（NOT 不需要）" },
      { id: "FROM", label: "目前進位", abbr: "FROM", unit: "", kind: "select", example: "10", options: BASE_RADIX, help: "A、B 的進位，例：十進位 10" },
      { id: "WIDTH", label: "位寬", abbr: "WIDTH", unit: "位元", kind: "select", example: "8", options: BASE_WIDTH, help: "整數的位元數，例：8 位元" },
      { id: "SIGNED", label: "有號數", abbr: "SIGNED", unit: "", kind: "bool", example: "否", help: "勾選＝二補數有號數，例：SAR 只能用於有號數" },
      { id: "BIN", label: "二進位", abbr: "BIN", unit: "", kind: "text", example: "00001000", output: true, help: "結果的二進位，例：12 AND 10 → 00001000" },
      { id: "OCT", label: "八進位", abbr: "OCT", unit: "", kind: "text", example: "010", output: true, help: "結果的八進位，例：12 AND 10 → 010" },
      { id: "DEC", label: "十進位", abbr: "DEC", unit: "", kind: "text", example: "8", output: true, help: "結果的十進位，例：12 AND 10 → 8" },
      { id: "HEX", label: "十六進位", abbr: "HEX", unit: "", kind: "text", example: "08", output: true, help: "結果的十六進位，例：12 AND 10 → 08" },
    ],
    actions: [{ id: "bitwise", label: "運算", primary: true }],
  },

  settings: {
    title: "設定 FORMAT", short: "設定", route: "settings", engine: null,
    intro: "顯示格式、運算順序與角度單位；只存在這台裝置",
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
        id: "dateFmt", label: "日期顯示格式", abbr: "DATE", unit: "", kind: "select", example: "us", initial: "us",
        options: [{ value: "us", label: "mm/dd/yyyy（美式）" }, { value: "eu", label: "dd.mm.yyyy（歐式）" }],
        help: "日期的顯示方式，例：美式 12/31/2026、歐式 31.12.2026；日期輸入欄位不受影響",
      },
      {
        id: "mode", label: "運算順序", abbr: "AOS/Chn", unit: "", kind: "select", example: "AOS", initial: "AOS",
        options: [{ value: "AOS", label: "代數順序 AOS" }, { value: "CHAIN", label: "依序 Chain" }],
        help: "計算機的運算順序，例：2+3×4 在 AOS 為 14、Chain 為 20",
      },
      {
        id: "angle", label: "角度單位", abbr: "DEG/RAD", unit: "", kind: "select", example: "DEG", initial: "DEG",
        options: [{ value: "DEG", label: "度 DEG" }, { value: "RAD", label: "弧度 RAD" }],
        help: "三角函數的角度單位，例：DEG 時 sin(30) = 0.5、RAD 時 sin(π/6) = 0.5",
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

/**
 * 稅率預設值：鏡射（mirror）engine/business.py 的 TAX_PRESETS（bridge 沒有對應路由）。
 * tests/test_web_sheets.py 會比對兩邊完全相同；改稅率請兩邊一起改並更新 checked（查證日期）。
 */
export const TAX_PRESETS = {
  "營業稅": {
    rate: 5,
    source_url: "https://www.etax.nat.gov.tw/etwmain/tax-info/innotative-tax-e-reference/filing/business-tax/wMDMRl7",
    checked: "2026-10-20",
  },
  "二代健保補充保費": {
    rate: 2.11,
    source_url: "https://www.mohw.gov.tw/cp-4624-57420-1.html",
    checked: "2026-10-20",
  },
};

/** 全部工作表（順序僅供測試與資料遍歷；導覽結構見 pages.js）。 */
export const SHEET_ORDER = [
  "tvm", "amort", "cashflow", "iconv", "bond", "depr", "stats", "describe", "dist", "infer",
  "business-profit", "business-breakeven", "business-pct", "tax", "date",
  "calc", "units", "base", "base-bitwise", "settings",
];

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

/**
 * 過期（stale）把關：動作的 fresh 欄位中有過期的（舊的計算結果）就回傳
 * {message, fields}，呼叫端不送出計算；沒有問題回傳 null。staleIds 為目前過期的欄位 id。
 */
export function staleBlock(sheetId, actionId, staleIds) {
  const action = (SHEETS[sheetId]?.actions || []).find((a) => a.id === actionId);
  if (!action || !action.fresh) return null;
  const bad = action.fresh.filter((id) => (staleIds || []).includes(id));
  if (bad.length === 0) return null;
  const fm = fieldMap(sheetId);
  const names = bad.map((id) => `${fm[id].label} ${fm[id].abbr}`).join("、");
  return { message: `${names} 是舊的計算結果，${action.freshHint}`, fields: bad };
}

/**
 * 成功計算後仍維持過期的欄位：只有「這次動作送出的欄位（sentIds）∪ 這次回應求出／填入的欄位
 * （filledIds）」解除過期。送出的欄位是這次計算實際用到的值；沒送出也沒填入的（例：one_var
 * 不送 A、B）維持過期，STAT 預測的 staleBlock 才擋得住舊係數。
 */
export function staleAfterSuccess(staleIds, filledIds, sentIds = []) {
  const clear = new Set([...(filledIds || []), ...(sentIds || [])]);
  return (staleIds || []).filter((id) => !clear.has(id));
}

/** 使用者編輯某欄位後仍維持過期的欄位：被編輯的欄位是使用者自己的值，不再是舊結果。 */
export function staleAfterEdit(staleIds, editedId) {
  return (staleIds || []).filter((id) => id !== editedId);
}

/** 主要動作（Enter 觸發）。 */
export function primaryAction(sheetId) {
  return SHEETS[sheetId].actions.find((a) => a.primary);
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
