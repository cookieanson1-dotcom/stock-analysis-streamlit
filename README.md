# 智能股票分析系统（Streamlit）

基于 Streamlit、yfinance、Plotly、Prophet 的股票概览、行情、预测与 CEO 信息面板。

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

可选：在项目下创建 `.streamlit/secrets.toml`（已被 `.gitignore` 忽略）以启用 NewsAPI 新闻：

```toml
NEWS_API_KEY = "你的_newsapi_密钥"
```

## 部署到 Streamlit Community Cloud（手机浏览器访问）

1. 在 [GitHub](https://github.com) 新建仓库（例如 `stock-analysis-streamlit`），**不要**勾选自动添加 README（或勾选均可，以你习惯为准）。
2. 将本仓库推送到 GitHub：

   ```bash
   cd stock-analysis-streamlit
   git init
   git add .
   git commit -m "Initial commit: Streamlit stock analysis app"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/<仓库名>.git
   git push -u origin main
   ```

3. 打开 [Streamlit Community Cloud](https://streamlit.io/cloud)，用 GitHub 登录，**New app** → 选择该仓库 → **Main file path** 填 `app.py` → Deploy。
4. 首次构建可能较慢（含 Prophet）。部署成功后，控制台会给出 `https://xxx.streamlit.app` 链接，手机用浏览器打开即可。
5. （可选）在 Cloud 里打开该应用 → **Settings → Secrets**，添加：

   ```toml
   NEWS_API_KEY = "你的_newsapi_密钥"
   ```

   保存后应用会重启；不配密钥时 CEO 新闻仍为空，其余功能可用。

## 说明

- 行情与公司信息来自 yfinance（非官方接口），偶发失败可重试。
- Prophet 预测仅供学习参考，不构成投资建议。
