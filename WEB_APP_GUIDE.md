# ☀️ 阳光高考自动化助手 (Web 版)

这是一个集成院校数据抓取、招生章程 AI 分析、录取数据整理的一站式高考志愿辅助工具。基于 Streamlit 构建，可直接部署在 Web 端。

## 🌟 主要功能
1.  **🏛️ 院校库抓取**：自动获取阳光高考网最新高校名单及基础信息，支持导出 Excel。
2.  **📄 章程 AI 分析**：利用 DeepSeek-R1 模型深度解读各高校招生章程，自动提取录取规则、身体限制、单科要求等核心风险点。
3.  **📊 录取数据整理**：一键清洗本地历年录取位次数据，统一格式，便于分析。

## 🚀 部署教程 (Streamlit Cloud)

本应用可以免费部署在 [Streamlit Cloud](https://streamlit.io/cloud) 上。

### 1. 准备工作
- 将本项目的所有文件（包括 `streamlit_app.py`, `requirements.txt`, `packages.txt`）上传到您的 GitHub 公开仓库。

### 2. 配置 `packages.txt` (关键)
由于应用需要使用 Playwright 驱动浏览器，Streamlit Cloud 环境需要安装额外的 Linux 依赖。请确保仓库中包含 `packages.txt` 文件，内容如下：
```text
libnss3
libnspr4
libatk1.0-0
libatk-bridge2.0-0
libcups2
libdrm2
libdbus-1-3
libxcb1
libxkbcommon0
libx11-6
libxcomposite1
libxdamage1
libxext6
libxfixes3
libxrandr2
libgbm1
libpango-1.0-0
libcairo2
libasound2
```

### 3. 在 Streamlit Cloud 部署
1.  登录 [Streamlit Cloud](https://share.streamlit.io/)。
2.  点击 **"New app"**。
3.  选择对应的 GitHub 仓库、分支，并将 **Main file path** 设置为 `streamlit_app.py`。
4.  点击 **"Deploy!"** 即可。

## 🛠️ 本地运行
如果您想在本地运行：
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器
playwright install chromium

# 3. 启动应用
streamlit run streamlit_app.py
```

## 🔐 安全说明
- 您的 **DeepSeek API Key** 将仅在浏览器会话中处理，不会被服务器永久存储。
- 本工具仅限个人填报志愿参考使用，请务必遵守阳光高考网的相关使用协议。
