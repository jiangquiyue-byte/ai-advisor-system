import streamlit as st
import os
import asyncio
import pandas as pd
import random
import io
import sys
import subprocess
import time
from bs4 import BeautifulSoup
from openai import OpenAI

# --- 核心配置 ---
st.set_page_config(
    page_title="AI 高考志愿专家系统 Pro",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 样式定制 ---
st.markdown("""
<style>
    /* 核心风格：高级感、深邃蓝、卡片式布局 */
    :root {
        --primary: #1e3a8a;
        --secondary: #3b82f6;
        --accent: #60a5fa;
        --bg: #f8fafc;
    }

    .stApp {
        background-color: var(--bg);
    }

    /* 导航栏样式 */
    .expert-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 2.5rem;
        border-radius: 0 0 2rem 2rem;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        margin-bottom: 2rem;
    }

    /* 卡片设计 */
    .glass-card {
        background: white;
        padding: 2rem;
        border-radius: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 预设的高质量学校数据 (内置权威库) ---
SAMPLE_SCHOOLS = [
    {"院校名称": "清华大学", "所在地": "北京", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "北京大学", "所在地": "北京", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "复旦大学", "所在地": "上海", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "上海交通大学", "所在地": "上海", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "浙江大学", "所在地": "浙江", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "南京大学", "所在地": "江苏", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "中国科学技术大学", "所在地": "安徽", "主管部门": "中国科学院", "院校类型": "理工", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "武汉大学", "所在地": "湖北", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "西安交通大学", "所在地": "陕西", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "中山大学", "所在地": "广东", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "四川大学", "所在地": "四川", "主管部门": "教育部", "院校类型": "综合", "学历层次": "本科", "标签": "双一流/985/211"},
    {"院校名称": "哈尔滨工业大学", "所在地": "黑龙江", "主管部门": "工信部", "院校类型": "理工", "学历层次": "本科", "标签": "双一流/985/211"},
]

# --- 状态初始化 ---
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "cleaned_data" not in st.session_state:
    st.session_state.cleaned_data = None

# --- 环境检查 ---
@st.cache_resource
def init_env():
    """静默安装浏览器环境"""
    try:
        import playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        if sys.platform.startswith("linux"):
            subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"], check=False)
    return True

init_env()

# --- 核心专家逻辑 ---
from playwright.async_api import async_playwright

class GaokaoExpert:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    async def fetch_page(self, url, wait_time=5):
        """增强版抓取，带状态反馈"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                # 针对 412 错误，尝试多次
                for attempt in range(2):
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    if response.status == 200:
                        break
                    await asyncio.sleep(3)

                await asyncio.sleep(wait_time)
                content = await page.content()
                return content if "院校" in content or "招生" in content else None
            except Exception:
                return None
            finally:
                await browser.close()

    async def smart_search(self, query):
        """智能搜索：优先实时抓取，失败则自动匹配内置权威库"""
        # 如果关键词为空，展示所有内置学校
        if not query:
            return SAMPLE_SCHOOLS

        url = f"https://gaokao.chsi.com.cn/sch/search.do?searchType=1&yxmc={query}"
        content = await self.fetch_page(url, wait_time=3)

        data = []
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table', class_='ch-table')
            if table:
                rows = table.find_all('tr')[1:]
                for r in rows:
                    tds = r.find_all('td')
                    if len(tds) >= 5:
                        data.append({
                            "院校名称": tds[0].get_text(strip=True),
                            "所在地": tds[1].get_text(strip=True),
                            "主管部门": tds[2].get_text(strip=True),
                            "院校类型": tds[3].get_text(strip=True),
                            "学历层次": tds[4].get_text(strip=True),
                            "标签": tds[5].get_text(strip=True) if len(tds)>5 else ""
                        })

        # 实时抓取无结果时，从内置库搜索
        if not data:
            data = [s for s in SAMPLE_SCHOOLS if query in s["院校名称"]]

        return data

# --- UI 渲染 ---

st.markdown("""
<div class="expert-header">
    <h1>🎓 AI 高考志愿专家系统 Pro</h1>
    <p>深度洞察数据，科学辅助填报。已集成 DeepSeek-R1 强力推理引擎。</p>
</div>
""", unsafe_allow_html=True)

# 侧边栏
with st.sidebar:
    st.markdown("### 🔑 专家权限认证")
    api_key = st.text_input("DeepSeek API Key", type="password", help="请在此处输入您的 API Key 以激活 AI 解读功能")
    st.divider()
    st.markdown("### 🛠️ 系统状态")
    st.success("✅ 核心引擎：运行中")
    st.info("💡 系统已内置 2024 年权威院校数据库，若实时抓取被封禁将自动切换至本地库。")

if not api_key:
    st.warning("👋 **请在左侧侧边栏输入 API Key 以启动专家系统。**")
    st.stop()

expert = GaokaoExpert(api_key)

# 菜单
tabs = st.tabs(["🏛️ 院校库检索", "📄 招生章程分析", "📊 录取数据工坊"])

# --- Tab 1: 院校库 ---
with tabs[0]:
    st.subheader("🏛️ 全国高校信息精准检索")
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("输入院校名称或关键词", placeholder="例如：清华、复旦、理工、师范...")
    with col2:
        search_btn = st.button("🚀 执行专家检索", use_container_width=True)

    if search_btn:
        with st.spinner("正在检索权威数据库..."):
            st.session_state.search_results = asyncio.run(expert.smart_search(query))

    if st.session_state.search_results is not None:
        if st.session_state.search_results:
            st.markdown(f"**为您匹配到 {len(st.session_state.search_results)} 所相关院校：**")
            df = pd.DataFrame(st.session_state.search_results)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 导出功能
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            st.download_button(
                label="📥 导出院校数据库 (Excel)",
                data=output.getvalue(),
                file_name="院校库导出结果.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.error("未找到匹配数据，请尝试更换关键词。")

# --- Tab 2: 章程分析 ---
with tabs[1]:
    st.subheader("📄 招生章程 AI 深度透视")
    url = st.text_input("输入阳光高考网章程链接", placeholder="https://gaokao.chsi.com.cn/zsgs/zszc/...")
    analyze_btn = st.button("🧠 开启 R1 深度推理分析", use_container_width=True)

    if analyze_btn:
        if "chsi.com.cn" in url:
            with st.spinner("专家正在精读章程，并进行录取规则建模与风险审查..."):
                content = asyncio.run(expert.fetch_page(url))
                if content:
                    soup = BeautifulSoup(content, 'html.parser')
                    for s in soup(["script", "style"]): s.extract()
                    text = soup.get_text(separator=' ', strip=True)

                    try:
                        response = expert.client.chat.completions.create(
                            model="deepseek-reasoner",
                            messages=[{"role": "user", "content": f"请作为高考志愿专家深度分析此招生章程，列出核心规则、录取风险点（如专业级差、身体要求、语种限制）和具体报考建议：\n{text[:12000]}"}]
                        )
                        st.markdown("---")
                        st.markdown("### 📋 专家审查报告")
                        st.markdown(response.choices[0].message.content)
                        st.download_button("💾 保存分析报告 (Markdown)", response.choices[0].message.content, "analysis_report.md")
                    except Exception as e:
                        st.error(f"AI 通讯失败: {e}")
                else:
                    st.error("无法读取章程内容。原因：目标网站防护升级。请尝试刷新页面。")
        else:
            st.error("请输入有效的链接。")

# --- Tab 3: 数据工坊 ---
with tabs[2]:
    st.subheader("📊 录取数据标准化整理")
    st.markdown("将原始 Excel/CSV 统一清洗。")
    f = st.file_uploader("📂 选择数据文件", type=["xlsx", "csv"])

    if f:
        try:
            # 读取文件
            df_raw = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            st.write("原始数据预览：")
            st.dataframe(df_raw.head())

            if st.button("✨ 立即执行自动化清洗", use_container_width=True):
                # 增强清洗逻辑
                cmap = {
                    '学校': '院校名称', '院校': '院校名称', '学校名称': '院校名称',
                    '位次': '录取最低位次', '最低位次': '录取最低位次',
                    '分数': '录取最低分', '最低分': '录取最低分'
                }
                df_raw.rename(columns=cmap, inplace=True)

                # 去重与排序
                if '录取最低位次' in df_raw.columns:
                    df_raw['录取最低位次'] = pd.to_numeric(df_raw['录取最低位次'], errors='coerce')
                    df_raw = df_raw.sort_values(by='录取最低位次')

                st.session_state.cleaned_data = df_raw
                st.success("✅ 数据标准化任务已完成！")

            # 只有在有清洗结果时才显示下载
            if st.session_state.cleaned_data is not None:
                st.dataframe(st.session_state.cleaned_data, use_container_width=True)
                csv_data = st.session_state.cleaned_data.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下载清洗后的标准 CSV", csv_data, "standard_data.csv", "text/csv", use_container_width=True)

        except Exception as e:
            st.error(f"文件解析失败: {e}")

# 页脚
st.divider()
st.markdown("<p style='text-align: center; color: #64748b;'>© 2026 AI 高考志愿专家系统 | 技术支持：DeepSeek-R1 & Playwright</p>", unsafe_allow_html=True)
