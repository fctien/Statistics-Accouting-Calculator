# Google Drive 同步：申請 OAuth Client ID 說明

BACalc 的 Google Drive 同步是**選用功能，預設關閉**。要用它，你必須自己在 Google Cloud Console 建立一組 OAuth 用戶端 ID（Client ID）。
這份說明帶你一步一步做；每一步都附官方文件連結。查證日：2026-10-20。Google 的畫面名稱偶爾會改，若你看到的與下文不同，以官方文件為準。

## 先了解三件事

1. **BACalc 只要求一種權限**：`https://www.googleapis.com/auth/drive.appdata`，官方說明為「View and manage the app's own configuration data in your Google Drive」，只能讀寫 App 專屬的隱藏資料夾（appDataFolder），看不到你 Drive 裡其他檔案。
   - 官方權限範圍清單把它歸類為**非敏感（non-sensitive）**：[Choose Google Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
   - 因此不需要 Google 的敏感權限審查。（這是依上面官方頁面的分類；若 Google 日後調整分類，以官方頁面為準。）
2. **不需要 Client Secret**：Web 應用程式使用 Google Identity Services（GIS）的 token 模式，Client ID 不是機密，可以放在設定頁。
3. **存取權杖只放在記憶體**：BACalc 不會把權杖存到任何地方，關閉頁面就失效。

## 步驟 1：建立 Google Cloud 專案

1. 用你自己的 Google 帳號登入 [Google Cloud Console](https://console.cloud.google.com/)。
2. 依官方說明：開啟選單，進入 **IAM & Admin > Create a Project**，輸入專案名稱（例如 `BACalc Sync`），按 **Create**。
3. 官方文件：[Create a Google Cloud project](https://developers.google.com/workspace/guides/create-project)

## 步驟 2：啟用 Google Drive API

1. 依官方說明：**Menu > APIs & Services > Library > Google Workspace > Drive API > Enable**。
2. 也可以直接用官方的啟用連結（記得先確認右上角選的是剛建立的專案）：[啟用 Drive API](https://console.cloud.google.com/apis/enableflow;apiid=drive.googleapis.com)
3. 官方文件：[Enable Google Workspace APIs](https://developers.google.com/workspace/guides/enable-apis)
4. 沒做這一步會出現 403「尚未啟用 Drive API」，BACalc 會在畫面上用中文提示。

## 步驟 3：設定 OAuth 同意畫面（Google Auth platform）

依官方文件，在 Google Cloud Console 進入 **Menu > Google Auth platform > Branding**，然後：

1. **App Information**：填 App name（例如 `BACalc`）與 User support email，按 Next。
2. **Audience**：選 **External**（個人 Gmail 帳號沒有 Workspace 組織時只能選這個），按 Next。
3. **Contact Information**：填你的 email，按 Next。
4. **Finish**：勾選同意 Google API Services User Data Policy，按 Continue，再按 Create。
5. 進入 **Audience > Test users > Add users**，**把你自己的 Google 帳號 email 加進測試使用者**，按 Save。
6. 進入 **Data Access > Add or Remove Scopes**，勾選 `.../auth/drive.appdata`（Drive API 底下，描述為 View and manage the app's own configuration data in your Google Drive），按 Save。
   - 若清單中找不到，可以在 **Manually add scopes** 貼上 `https://www.googleapis.com/auth/drive.appdata`。這個「Manually add scopes」欄位名稱我**不確定**目前是否一字不差，請以你畫面為準。
7. 官方文件：[Configure the OAuth consent screen and choose scopes](https://developers.google.com/workspace/guides/configure-oauth-consent)

### 測試模式（Testing）與測試使用者

- 剛建立的 External 應用程式處於**測試（Testing）**狀態，只有列在 Test users 的帳號能授權，其他人會看到被拒絕的畫面。自己用的話，**留在測試模式即可，不需要送出 Google 審查或發布**。
- 登入時 Google 可能顯示「Google 尚未驗證這個應用程式」的警告，這是測試模式的正常現象；因為這是你自己建立的 App，確認後按「進階」繼續即可。（警告文字的確切字樣我**不確定**，請以畫面為準。）
- 測試模式下授權的有效期限與測試使用者上限，官方的同意畫面文件沒有在上述頁面說明，我**不確定**確切數字。BACalc 使用的是短效的存取權杖，過期時只需要再按一次「連結 Google Drive」。

## 步驟 4：建立 Web 應用程式的 OAuth 用戶端 ID

依官方文件：

1. 進入 **Menu > Google Auth platform > Clients**，按 **Create Client**。
2. **Application type** 選 **Web application**。
3. **Name** 隨意填（只在 Console 內顯示），例如 `BACalc Web`。
4. 在 **Authorized JavaScript origins** 按 **Add URI**，加入下面兩個（**只要來源 origin，不含路徑，結尾不要加斜線**）：
   - `http://localhost:8765`（本機測試用）
   - `https://fctien.github.io`（GitHub Pages 部署用；實際網址是 `https://fctien.github.io/Statistics-Accouting-Calculator/`，路徑區分大小寫，但授權來源只填到 `.io`）
5. **不需要**填 Authorized redirect URIs（token 模式用彈出視窗，不用導向）。
6. 按 **Create**。畫面會顯示 **Client ID**，格式像 `123456789-abcdefg.apps.googleusercontent.com`。Web 應用程式用戶端沒有 client secret，**不要**複製或保存 secret。
7. 官方文件：[Create access credentials（Web application 用戶端）](https://developers.google.com/workspace/guides/create-credentials)
8. 設定改了之後可能要等幾分鐘才生效；官方說法我沒有查到確切時間，**不確定**。

## 步驟 5：把 Client ID 填進 BACalc

1. 開啟 BACalc，進入「設定」，找到「Google Drive 同步（選用）」區。
2. 貼上 Client ID，按 **儲存**。Client ID 只存在這台裝置的 IndexedDB，不會寫死在程式裡，也不會上傳到雲端。
3. 按 **連結 Google Drive**。此時 BACalc 才第一次載入 Google 的登入程式庫（[Google Identity Services](https://developers.google.com/identity/oauth2/web/guides/use-token-model)，token 模式），跳出授權視窗；選你的帳號並同意「管理 App 自己的設定資料」權限。離線時按鈕會停用。
4. 之後可以：
   - **上傳到雲端**：把目前的情境、紙帶、記憶、設定存成 `bacalc-backup.json`
   - **從雲端下載**：先驗證檔案格式，再選**合併**或**取代**（取代會先確認）
   - 如果雲端比上次同步新、而你本機也改過，BACalc **不會自動覆蓋**，會顯示雙方時間讓你選擇
5. 備份檔存放在 Google Drive 的 App 專屬隱藏資料夾（appDataFolder），在 Drive 網頁上**看不到**，這是正常的。官方說明：[Store application-specific data](https://developers.google.com/workspace/drive/api/guides/appdata)。官方文件指出：使用者也可以手動刪除這個資料夾，App 從使用者的 My Drive 解除安裝時資料夾會被刪除；刪除的具體操作畫面我不確定。

## 如何撤銷（revoke）存取

1. **在 BACalc 內**：按 **中斷連結**。BACalc 會呼叫 Google 官方的 `google.accounts.oauth2.revoke` 撤銷這次授權的權杖（[官方說明](https://developers.google.com/identity/oauth2/web/guides/use-token-model)），並清掉記憶體中的權杖。
2. **在 Google 帳戶**：依官方說明前往 [myaccount.google.com/linkedapps](https://myaccount.google.com/linkedapps)，選擇 BACalc（你建立的 App 名稱），在「Access to your Google Account」下選 **See details > Remove access > Confirm**。官方文件：[Remove a third-party app's access](https://support.google.com/accounts/answer/13533235)。
3. **徹底清除**：撤銷後，雲端的 `bacalc-backup.json` 是否一併刪除我**不確定**；若要確保刪除，請在撤銷前先於 BACalc 內確認不再需要雲端備份；Drive 端刪除隱藏資料的操作位置我不確定，請查 Drive 說明。
4. 在 BACalc 設定頁清空 Client ID 並按「儲存」，即可關閉同步功能。

## 常見問題

| 畫面訊息 | 原因 | 處理 |
|---|---|---|
| Error 400: origin_mismatch 或「redirect_uri」相關錯誤 | 網址的 origin 沒有列在 Authorized JavaScript origins | 回步驟 4 補上目前使用的 origin（協定、主機、埠號都要完全一致） |
| access_denied／「應用程式尚未完成驗證」 | 你的帳號不在 Test users | 回步驟 3 第 5 點加入 |
| 403 尚未啟用 Drive API | 步驟 2 沒做，或選錯專案 | 在同一個專案啟用 Drive API |
| 按鈕灰色 | 沒有 Client ID，或目前離線 | 填入 Client ID；連上網路 |
| 授權視窗被擋 | 瀏覽器擋彈出視窗 | 允許此網站的彈出視窗後再按一次 |

## 隱私說明

- 沒有填 Client ID 並按下按鈕之前，BACalc 不會連到 Google；Google 的登入程式庫**不在離線快取（precache）內**，只在你按「連結 Google Drive」時才載入。
- Service Worker 只處理同源（same-origin）請求，不快取任何 Google 的回應。
- 上傳的內容就是匯出 JSON 的內容（情境、紙帶、記憶、設定），但**不含**你的 Client ID。
- 本說明的 Google 官方連結清單：
  - [Google Cloud Console](https://console.cloud.google.com/)
  - [Create a Google Cloud project](https://developers.google.com/workspace/guides/create-project)
  - [Enable Google Workspace APIs](https://developers.google.com/workspace/guides/enable-apis)
  - [Configure OAuth consent](https://developers.google.com/workspace/guides/configure-oauth-consent)
  - [Create access credentials](https://developers.google.com/workspace/guides/create-credentials)
  - [Google Identity Services：token 模式](https://developers.google.com/identity/oauth2/web/guides/use-token-model)
  - [Drive API 權限範圍](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
  - [Drive appDataFolder](https://developers.google.com/workspace/drive/api/guides/appdata)
