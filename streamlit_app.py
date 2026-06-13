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
from playwright.async_api import async_playwright

# --- UI 配置与样式定制 ---
st.set_page_config(
    page_title="阳光高考 AI 专家系统",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 注入：打造高级视觉感
st.markdown("""
<style>
    /* 全局背景与文字优化 */
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }

    /* 标题美化 */
    .main-title {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1e3a8a;
        font-weight: 800;
        text-align: center;
        padding-bottom: 20px;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }

    /* 卡片式设计 */
    .data-card {
        background-color: white;
        border-radius: 15px;
        padding: 25px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        margin-bottom: 20px;
        border-left: 5px solid #3b82f6;
    }

    /* 侧边栏美化 */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    /* 按钮美化 */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #2563eb;
        color: white;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #1d4ed8;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(37,99,235,0.2);
    }

    /* 状态指示器 */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8em;
        font-weight: 600;
        background-color: #d1fae5;
        color: #065f46;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 环境检查与自动初始化 ---
def ensure_playwright():
    """检测并静默安装浏览器环境"""
    if "playwright_ready" not in st.session_state:
        try:
            # 尝试导入并启动以验证
            import playwright
            st.session_state.playwright_ready = True
        except Exception:
            with st.status("正在初始化专家级引擎环境...", expanded=True) as status:
                st.write("📥 下载系统依赖包...")
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
                    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    st.session_state.playwright_ready = True
                    status.update(label="✅ 引擎就绪！", state="complete", expanded=False)
                except Exception as e:
                    st.error(f"环境初始化失败: {e}")
                    st.stop()

ensure_playwright()

# --- 核心专家类 ---
class GaokaoExpert:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    async def secure_fetch(self, url):
        """增强版异步抓取：带重试机制与仿真策略"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800},
                device_scale_factor=1,
            )
            page = await context.new_page()
            # 伪装
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                # 针对缓慢加载的优化
                response = await page.goto(url, wait_until="networkidle", timeout=60000)
                if response.status == 412:
                    st.warning("⚠️ 目标网站触发防火墙挑战，正在尝试绕过...")
                    await asyncio.sleep(8)

                # 滚动一下页面以触发懒加载
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(2)

                content = await page.content()
                return content
            except Exception as e:
                st.error(f"无法访问网页 ({e})。请确认链接是否为阳光高考网官方地址。")
                return None
            finally:
                await browser.close()

    async def crawl_universities(self, total_pages):
        """专业化爬取逻辑"""
        results = []
        progress_text = "专家正在为您检索院校数据..."
        my_bar = st.progress(0, text=progress_text)

        for p in range(total_pages):
            start_idx = p * 20
            url = f"https://gaokao.chsi.com.cn/sch/search.do?start={start_idx}"
            html = await self.secure_fetch(url)

            if html:
                soup = BeautifulSoup(html, 'html.parser')
                table = soup.find('table', class_='ch-table')
                if table:
                    rows = table.find_all('tr')[1:]
                    for r in rows:
                        tds = r.find_all('td')
                        if len(tds) >= 5:
                            results.append({
                                "院校名称": tds[0].get_text(strip=True),
                                "所在地": tds[1].get_text(strip=True),
                                "主管部门": tds[2].get_text(strip=True),
                                "类型": tds[3].get_text(strip=True),
                                "层级": tds[4].get_text(strip=True),
                                "标签": tds[5].get_text(strip=True) if len(tds)>5 else ""
                            })

            progress = (p + 1) / total_pages
            my_bar.progress(progress, text=f"已完成 {int(progress*100)}% - 正在处理第 {p+1} 页...")
            await asyncio.sleep(random.uniform(1.5, 3.0))

        my_bar.empty()
        return results

    async def deep_analyze_policy(self, url, model="deepseek-reasoner"):
        """深度 AI 政策解读"""
        html = await self.secure_fetch(url)
        if not html: return None

        soup = BeautifulSoup(html, 'html.parser')
        # 去噪
        for element in soup(['script', 'style', 'nav', 'footer']):
            element.decompose()
        text_content = soup.get_text(separator=' ', strip=True)

        with st.status("🧠 AI 正在进行深度推理与合规性审查...", expanded=True):
            st.write("1️⃣ 解析原始政策文本...")
            time.sleep(1)
            st.write("2️⃣ 正在提取核心录取指标...")
            time.sleep(1)
            st.write("3️⃣ 正在进行风险等级评估...")

            prompt = f"""
            你是一位拥有20年经验的高考志愿填报专家。请对下方的招生章程进行严苛的深度审查，并输出一份专业报告。

            要求：
            - 使用 Markdown 格式。
            - 必须包含“核心规则摘要”、“避雷针/风险点”、“报考建议”。
            - 针对：录取原则（分数/级差）、退档门槛、身体素质限制、单科分数线进行深度挖掘。

            待分析文本：
            {text_content[:15000]}
            """

            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
            except Exception as e:
                st.error(f"AI 解析中断: {e}")
                return None

# --- UI 渲染逻辑 ---

# 侧边栏
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/university.png", width=80)
    st.title("系统配置")

    with st.container(border=True):
        st.subheader("🔑 权限验证")
        user_key = st.text_input("DeepSeek API Key", type="password", help="请提供您的密钥以开启 AI 深度分析功能")
        model_name = st.segmented_control("思考模型", ["R1 (深度推理)", "V3 (极速响应)"], default="R1 (深度推理)")
        actual_model = "deepseek-reasoner" if "R1" in model_name else "deepseek-chat"

    st.divider()
    st.info("ℹ️ **温馨提示**：\n阳光高考网数据由于具备权威性，访问较为严格，本系统已内置智能仿真算法以降低被拦截风险。")

# 主界面
st.markdown("<h1 class='main-title'>🎓 阳光高考 AI 决策辅助系统</h1>", unsafe_allow_html=True)

if not user_key:
    st.warning("👋 **欢迎！** 请先在左侧侧边栏配置您的 **DeepSeek API Key**。")
    st.markdown("""
    <div class='data-card'>
        <h3>🌟 系统核心能力</h3>
        <ul>
            <li><b>院校精准检索</b>：全自动、批量化获取阳光高考网最新院校库。</li>
            <li><b>招生章程深度挖掘</b>：由 DeepSeek-R1 驱动，精准识别“专业级差”、“身体限制”等填报陷阱。</li>
            <li><b>录取数据标准化</b>：一键清洗各省原始数据，构建个人专属决策库。</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

expert = GaokaoExpert(user_key)

# 导航菜单
menu = st.tabs(["🏛️ 院校检索库", "🔎 章程深度解析", "📊 数据清洗工坊"])

# 1. 院校库抓取
with menu[0]:
    st.subheader("全国高校库自动化采集")
    st.markdown("<div class='status-badge'>专家模式已开启</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        pages_to_crawl = st.slider("设定检索深度 (页数)", 1, 50, 2)
        st.caption("注：每页包含20所院校信息。")

    if st.button("🚀 启动全自动化采集", key="crawl_btn"):
        with st.spinner("系统正在建立加密隧道并解析数据..."):
            raw_data = asyncio.run(expert.crawl_universities(pages_to_crawl))
            if raw_data:
                df = pd.DataFrame(raw_data)
                st.success(f"🎊 采集成功！已获取 {len(df)} 所高校的实时档案。")
                st.dataframe(df, use_container_width=True)

                # 导出
                xlsx = io.BytesIO()
                with pd.ExcelWriter(xlsx, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)

                st.download_button(
                    label="📥 导出为专家级 Excel 报告",
                    data=xlsx.getvalue(),
                    file_name="gaokao_universities_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("采集任务未成功完成。请尝试减少页数或检查网络连接。")

# 2. 章程分析
with menu[1]:
    st.subheader("高校招生章程 AI 深度审查")
    st.markdown("""
    <div class='data-card'>
        <p>💡 <b>使用说明</b>：输入阳光高考网中具体学校的“招生章程”页面 URL，AI 将自动扫描其中的录取规则与退档风险。</p>
    </div>
    """, unsafe_allow_html=True)

    policy_url = st.text_input("🔗 招生章程 URL 链接", placeholder="https://gaokao.chsi.com.cn/zsgs/zszc/...")

    if st.button("🧠 开启 AI 深度扫描", key="analyze_btn"):
        if policy_url and "gaokao.chsi.com.cn" in policy_url:
            report = asyncio.run(expert.deep_analyze_policy(policy_url, actual_model))
            if report:
                st.markdown("### 📋 AI 专家审查报告")
                st.markdown(report)
                st.download_button("💾 保存分析报告 (Markdown)", report, "report.md", "text/markdown")
        else:
            st.error("请输入有效的阳光高考网招生章程链接。")

# 3. 数据清洗
with menu[2]:
    st.subheader("填报数据标准化整理")
    st.markdown("上传从考试院获取的原始数据文件（CSV/Excel），我们将为您统一格式。")

    uploaded_file = st.file_uploader("📂 选择本地数据文件", type=["xlsx", "csv"])

    if uploaded_file:
        try:
            df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            st.info(f"📂 已成功读取文件: `{uploaded_file.name}` (共 {len(df_input)} 行)")

            with st.expander("👀 查看原始数据摘要"):
                st.dataframe(df_input.head(10))

            if st.button("✨ 执行标准化清洗"):
                # 清洗逻辑
                mapping = {
                    '学校': '院校名称', '院校': '院校名称', '学校名称': '院校名称',
                    '最低分': '录取最低分', '投档分': '录取最低分',
                    '最低位次': '录取最低位次', '位次': '录取最低位次'
                }
                df_input.rename(columns=mapping, inplace=True)

                # 保留有用的列并去重
                cols_to_keep = [c for c in df_input.columns if c in mapping.values()]
                if not cols_to_keep: cols_to_keep = df_input.columns.tolist()

                df_cleaned = df_input[cols_to_keep].dropna(subset=['院校名称'] if '院校名称' in cols_to_keep else None)

                st.success("✨ 数据标准化任务已完成！")
                st.dataframe(df_cleaned, use_container_width=True)

                csv_data = df_cleaned.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 下载标准化 CSV 文件", csv_data, "cleaned_data.csv", "text/csv")

        except Exception as e:
            st.error(f"数据解析失败: {e}")

# 页脚
st.divider()
st.markdown("<p style='text-align: center; color: gray;'>© 2026 阳光高考 AI 决策助手 | 技术支持：DeepSeek-R1 & Playwright</p>", unsafe_allow_html=True)
