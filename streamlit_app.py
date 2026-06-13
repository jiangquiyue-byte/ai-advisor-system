import streamlit as st
import os
import asyncio
import pandas as pd
import random
import io
import sys
import subprocess
import time
import logging
from bs4 import BeautifulSoup
from openai import OpenAI

# --- 核心配置 ---
st.set_page_config(
    page_title="AI 高考志愿专家系统",
    page_icon="🎯",
    layout="wide"
)

# --- 样式定制 ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: #fdfdfd;
    }

    /* 顶部横幅 */
    .hero-section {
        background: linear-gradient(90deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 3rem 2rem;
        border-radius: 1rem;
        margin-bottom: 2rem;
        text-align: center;
    }

    /* 模块卡片 */
    .module-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    .module-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    /* 字体与颜色 */
    h1, h2, h3 { color: #1e293b; }
    .highlight { color: #2563eb; font-weight: 700; }

    /* 侧边栏优化 */
    [data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# --- 环境自修复模块 ---
def check_environment():
    """彻底解决 Playwright 报错的初始化逻辑"""
    if "env_ready" not in st.session_state:
        st.session_state.env_ready = False

    if not st.session_state.env_ready:
        with st.status("🛠️ 系统引擎初始化中...", expanded=True) as status:
            try:
                # 尝试导入，失败则安装
                import playwright
                st.write("✅ 核心库已加载")
            except ImportError:
                st.write("📦 正在安装核心库...")
                subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)

            # 检查浏览器是否已安装
            # 在 Streamlit Cloud，我们需要确保这个命令执行成功
            st.write("🌐 正在配置浏览器环境（请稍候）...")
            try:
                # 使用 -m playwright install 确保环境隔离性
                subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                # 针对 Linux 环境安装依赖 (如果是本地运行通常不需要，但云端需要)
                if sys.platform.startswith("linux"):
                    st.write("🐧 正在补齐系统依赖...")
                    subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], check=False)

                st.session_state.env_ready = True
                status.update(label="🚀 系统引擎已就绪！", state="complete", expanded=False)
            except Exception as e:
                st.error(f"环境初始化失败: {e}")
                st.info("提示：如果您在本地运行，请在终端执行 `playwright install` 后再启动。")
                st.stop()

# 调用环境检查
check_environment()

# 现在安全导入 Playwright
from playwright.async_api import async_playwright

# --- 业务逻辑类 ---
class GaokaoEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    async def fetch_with_stealth(self, url):
        """高强度仿生爬虫逻辑"""
        async with async_playwright() as p:
            # 模拟随机指纹
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                accept_downloads=True
            )
            page = await context.new_page()

            # 注入 Anti-Bot 绕过脚本
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)

            try:
                st.write(f"🔍 正在建立加密访问请求...")
                # 针对 412 状态码的重试策略
                max_retries = 3
                for attempt in range(max_retries):
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    if response.status == 412:
                        st.warning(f"⚠️ 正在绕过第 {attempt+1} 重安全墙...")
                        await asyncio.sleep(random.uniform(5, 10))
                        continue
                    break

                # 等待动态内容加载
                await asyncio.sleep(4)
                # 模拟人类滚动
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                await asyncio.sleep(2)

                content = await page.content()
                return content
            except Exception as e:
                st.error(f"访问中断: {str(e)}")
                return None
            finally:
                await browser.close()

    async def crawl_list(self, pages):
        """院校库抓取"""
        all_data = []
        progress_bar = st.progress(0, text="专家引擎正在扫描全国高校库...")

        for i in range(pages):
            start = i * 20
            url = f"https://gaokao.chsi.com.cn/sch/search.do?start={start}"
            html = await self.fetch_with_stealth(url)

            if html:
                soup = BeautifulSoup(html, 'html.parser')
                table = soup.find('table', class_='ch-table')
                if table:
                    rows = table.find_all('tr')[1:]
                    for r in rows:
                        tds = r.find_all('td')
                        if len(tds) >= 5:
                            all_data.append({
                                "院校": tds[0].get_text(strip=True),
                                "省份": tds[1].get_text(strip=True),
                                "主管部门": tds[2].get_text(strip=True),
                                "类型": tds[3].get_text(strip=True),
                                "层次": tds[4].get_text(strip=True),
                                "标签": tds[5].get_text(strip=True) if len(tds)>5 else ""
                            })

            progress_bar.progress((i + 1) / pages, text=f"已获取 {len(all_data)} 所院校，正在处理第 {i+1} 页...")
            await asyncio.sleep(random.uniform(2, 5))

        progress_bar.empty()
        return all_data

    async def analyze_report(self, url, model="deepseek-reasoner"):
        """AI 深度报告"""
        html = await self.fetch_with_stealth(url)
        if not html: return None

        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        with st.status("🔮 DeepSeek-R1 正在进行逻辑建模与风险评估...") as status:
            st.write("📑 正在结构化招生政策内容...")

            prompt = f"""
            你是一个专业的高考政策分析AI。请从下方文本中提取招生章程的核心规则：
            1. 录取原则（分数优先、级差等）。
            2. 身体限制（身高、视力、色觉等）。
            3. 退档风险（专业调剂规定、比例等）。
            4. 报考建议。
            请用清晰的 Markdown 格式输出。

            文本：{text[:15000]}
            """

            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                status.update(label="✅ 分析报告已生成！", state="complete")
                return response.choices[0].message.content
            except Exception as e:
                st.error(f"AI 通讯失败: {e}")
                return None

# --- UI 渲染 ---
st.markdown("""
    <div class="hero-section">
        <h1>🎯 AI 高考志愿全能专家系统</h1>
        <p>集成权威数据抓取、DeepSeek-R1 深度政策解读、录取数据标准化整理</p>
    </div>
""", unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.markdown("### 🛠️ 系统配置")
    api_key = st.text_input("DeepSeek API Key", type="password", help="在此输入您的密钥以启用 AI 功能")

    st.divider()
    st.markdown("### 📊 系统状态")
    if st.session_state.get("env_ready"):
        st.success("✅ 运行环境：就绪")
    else:
        st.error("❌ 运行环境：初始化中")

    st.divider()
    st.caption("版本: v2.5 (Pro) | 基于 Streamlit & Playwright")

if not api_key:
    st.info("👋 **欢迎！** 请在侧边栏输入 **DeepSeek API Key** 以开始使用专家系统。")
    st.stop()

engine = GaokaoEngine(api_key)

# 功能标签页
tab1, tab2, tab3 = st.tabs(["🏛️ 院校库批量扫描", "🔎 招生章程深度透视", "🧹 数据清洗工坊"])

# 1. 院校库
with tab1:
    st.markdown("### 🏛️ 全国高校档案采集")
    c1, c2 = st.columns([1, 2])
    with c1:
        num_pages = st.number_input("检索广度 (页数)", 1, 100, 2)
        start_btn = st.button("🚀 启动自动化采集", use_container_width=True)

    if start_btn:
        results = asyncio.run(engine.crawl_list(num_pages))
        if results:
            df = pd.DataFrame(results)
            st.success(f"成功扫描到 {len(df)} 所高校数据！")
            st.dataframe(df, use_container_width=True)

            # 导出 Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 导出院校数据库 (Excel)", output.getvalue(), "gaokao_univ_data.xlsx", "application/vnd.ms-excel", use_container_width=True)
        else:
            st.error("由于目标站点防火墙限制，本次请求未成功。建议稍后重试或使用较少的页数。")

# 2. 章程分析
with tab2:
    st.markdown("### 🔎 招生章程风险分析")
    st.markdown("AI 将深度阅读章程，为您识别“退档风险”和“硬性门槛”。")
    policy_url = st.text_input("🔗 招生章程链接", placeholder="https://gaokao.chsi.com.cn/zsgs/zszc/...")

    if st.button("🧠 开启 AI 深度解读", use_container_width=True):
        if "gaokao.chsi.com.cn" in policy_url:
            report = asyncio.run(engine.analyze_report(policy_url))
            if report:
                st.markdown("---")
                st.markdown(report)
        else:
            st.error("请输入有效的阳光高考网链接。")

# 3. 数据清洗
with tab3:
    st.markdown("### 🧹 录取位次数据整理")
    st.markdown("上传考试院原始文件，自动标准化学校名称与位次字段。")
    u_file = st.file_uploader("📂 选择原始数据文件 (Excel/CSV)", type=['xlsx', 'csv'])

    if u_file:
        df_raw = pd.read_csv(u_file) if u_file.name.endswith('.csv') else pd.read_excel(u_file)
        st.dataframe(df_raw.head())

        if st.button("✨ 立即执行标准化", use_container_width=True):
            # 清洗字典
            cmap = {'院校': 'univ', '学校': 'univ', '学校名称': 'univ', '最低位次': 'rank', '投档位次': 'rank', '最低分': 'score'}
            df_raw.rename(columns=cmap, inplace=True)

            # 过滤关键列
            keep = [c for c in df_raw.columns if c in cmap.values()]
            if not keep: keep = df_raw.columns
            df_final = df_raw[keep].dropna()

            st.success("数据清洗完成！")
            st.dataframe(df_final, use_container_width=True)
            st.download_button("📥 下载清洗后的数据", df_final.to_csv(index=False), "cleaned_gaokao_data.csv", "text/csv", use_container_width=True)

# 页脚
st.divider()
st.markdown("<p style='text-align: center; color: #64748b;'>基于阳光高考数据源 | 本工具由 AI 驱动，仅供填报参考</p>", unsafe_allow_html=True)
