import streamlit as st
import os
import asyncio
import pandas as pd
import random
import io
import sys
import subprocess
from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.async_api import async_playwright

# --- 环境自动配置 ---
def install_playwright_browsers():
    """在 Streamlit Cloud 等环境中自动安装 Playwright 浏览器"""
    try:
        # 检查是否已安装 chromium
        from playwright.async_api import async_playwright
        return True
    except ImportError:
        pass

    with st.spinner("首次运行，正在初始化浏览器环境（约需 1-2 分钟）..."):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            return True
        except Exception as e:
            st.error(f"浏览器环境安装失败: {e}")
            return False

# --- 核心逻辑类 ---
class SunshineTool:
    def __init__(self, api_key):
        self.api_key = api_key
        # DeepSeek API 配置
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    async def fetch_page(self, url):
        """使用 Playwright 获取内容，处理 WAF 挑战"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            # 隐藏自动化特征
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(5) # 等待挑战通过
                return await page.content()
            except Exception as e:
                st.error(f"请求失败: {e}")
                return None
            finally:
                await browser.close()

    async def crawl_colleges(self, pages=1):
        base_url = "https://gaokao.chsi.com.cn/sch/search.do?start="
        all_colleges = []
        progress_bar = st.progress(0)

        for i in range(pages):
            start = i * 20
            url = f"{base_url}{start}"
            content = await self.fetch_page(url)
            if content:
                soup = BeautifulSoup(content, 'html.parser')
                table = soup.find('table', class_='ch-table')
                if table:
                    rows = table.find_all('tr')[1:]
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 5:
                            all_colleges.append({
                                "院校名称": cols[0].get_text(strip=True),
                                "所在地": cols[1].get_text(strip=True),
                                "主管部门": cols[2].get_text(strip=True),
                                "院校类型": cols[3].get_text(strip=True),
                                "学历层次": cols[4].get_text(strip=True),
                                "特征标签": cols[5].get_text(strip=True) if len(cols) > 5 else ""
                            })
                progress_bar.progress((i + 1) / pages)
                await asyncio.sleep(random.uniform(2, 4))
        return all_colleges

    async def analyze_rules(self, url, model_name="deepseek-reasoner"):
        """利用 DeepSeek-R1 (reasoner) 深度分析章程"""
        content = await self.fetch_page(url)
        if not content: return "无法获取网页内容，请检查链接是否正确。"

        soup = BeautifulSoup(content, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        text = soup.get_text(separator='\n', strip=True)

        prompt = f"""
        你是一位资深高考志愿规划师。请分析下方“高校招生章程”正文，并提取出核心关键信息。
        要求：
        1. 必须包含：录取规则（分数优先/专业级差/志愿优先）、投档比例、退档条件。
        2. 必须包含：身体条件限制（如色盲、色弱、身高、视力要求）。
        3. 必须包含：单科成绩或语种要求。
        4. 必须包含：非第一志愿或征集志愿的特殊规定。

        文本：
        ---
        {text[:12000]}
        ---
        请使用 Markdown 格式输出分析报告。
        """

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI 分析失败: {e} (请检查 API Key 余额或模型权限)"

# --- Streamlit UI 界面 ---
st.set_page_config(page_title="阳光高考助手 - 网页版", layout="wide", page_icon="☀️")

# 侧边栏：初始化与配置
with st.sidebar:
    st.title("☀️ 阳光高考助手")
    st.subheader("⚙️ 配置中心")
    api_key = st.text_input("DeepSeek API Key", type="password", help="请从 DeepSeek 官网获取 API Key")
    model_option = st.selectbox("选择 AI 模型", ["deepseek-reasoner (R1)", "deepseek-chat (V3)"], index=0)
    selected_model = "deepseek-reasoner" if "R1" in model_option else "deepseek-chat"

    st.divider()
    st.markdown("### 🛠️ 环境检测")
    env_ok = install_playwright_browsers()
    if env_ok:
        st.success("浏览器引擎已就绪")
    else:
        st.error("浏览器引擎缺失")

st.header("全国高校志愿填报自动化工具")
st.info("💡 本工具集成院校抓取、章程 AI 解读、数据清洗功能。请先在左侧输入 API Key。")

if not api_key:
    st.warning("👈 请先在侧边栏输入 DeepSeek API Key。")
    st.stop()

tool = SunshineTool(api_key)

tab1, tab2, tab3 = st.tabs(["🏛️ 院校库抓取", "📄 章程 AI 分析", "📊 录取数据整理"])

# --- Tab 1: 院校库 ---
with tab1:
    st.subheader("全国高校信息一键抓取")
    col1, col2 = st.columns([1, 3])
    with col1:
        pages = st.number_input("抓取页数 (每页20条)", min_value=1, max_value=50, value=1)
        start_crawl = st.button("🚀 开始抓取", use_container_width=True)

    if start_crawl:
        with st.spinner("正在请求阳光高考网并解析数据..."):
            # 在 Streamlit 中运行异步代码的推荐方式
            data = asyncio.run(tool.crawl_colleges(pages))
            if data:
                df = pd.DataFrame(data)
                st.success(f"成功抓取 {len(df)} 条院校数据")
                st.dataframe(df, use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    label="📥 点击下载 Excel 报告",
                    data=output.getvalue(),
                    file_name="阳光高考院校库导出.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.error("抓取失败。原因可能是网站防火墙限制，请稍后重试或尝试增加延迟。")

# --- Tab 2: 章程分析 ---
with tab2:
    st.subheader("AI 深度解读招生章程 (DeepSeek-R1)")
    url = st.text_input("输入阳光高考网招生章程链接 (URL)", placeholder="例如：https://gaokao.chsi.com.cn/zsgs/zszc/listVerifiableZszc--method-getById,id-12345.dhtml")
    analyze_btn = st.button("🧠 开始深度分析", use_container_width=True)

    if analyze_btn:
        if url and "gaokao.chsi.com.cn" in url:
            with st.spinner(f"正在使用 {model_option} 分析规则，请稍候..."):
                report = asyncio.run(tool.analyze_rules(url, selected_model))
                st.markdown("---")
                st.markdown(report)

                st.download_button(
                    label="💾 导出 Markdown 报告",
                    data=report,
                    file_name="招生章程分析报告.md",
                    mime="text/markdown"
                )
        else:
            st.error("请输入有效的阳光高考网招生章程链接。")

# --- Tab 3: 数据整理 ---
with tab3:
    st.subheader("本地数据清洗助手")
    st.markdown("将各省考试院下载的原始 Excel/CSV 统一清洗为标准格式。")
    uploaded_file = st.file_uploader("上传原始数据文件", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.write("原始数据展示 (前5行)：")
            st.dataframe(df.head())

            if st.button("✨ 立即开始清洗", use_container_width=True):
                # 清洗逻辑增强：自动匹配常见列名
                col_map = {
                    '学校名称': 'univ_name', '院校名称': 'univ_name',
                    '最低位次': 'min_rank', '投档位次': 'min_rank',
                    '最低分': 'min_score', '投档分': 'min_score'
                }
                df.rename(columns=col_map, inplace=True)

                # 去重与排序
                if 'univ_name' in df.columns:
                    df.dropna(subset=['univ_name'], inplace=True)
                if 'min_rank' in df.columns:
                    df['min_rank'] = pd.to_numeric(df['min_rank'], errors='coerce')
                    df = df.sort_values(by='min_rank')

                st.success("清洗完成！列名已标准化，数据已按位次排序。")
                st.dataframe(df)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                st.download_button(
                    label="📥 下载清洗后的标准 Excel",
                    data=output.getvalue(),
                    file_name="cleaned_scores.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception as e:
            st.error(f"文件解析失败: {e}")
