import os
import asyncio
import argparse
import pandas as pd
import random
import sys
from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.async_api import async_playwright

class SunshineTool:
    """
    阳光高考网自动化助手 - 集成院校库抓取、招生章程AI分析、录取数据整理功能
    """
    def __init__(self, api_key=None):
        # 优先使用传入的key，其次寻找环境变量
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            print("[!] 错误: 未检测到 DEEPSEEK_API_KEY。请通过 --key 参数提供或设置环境变量。")
            sys.exit(1)
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    async def fetch_page(self, url):
        """使用 Playwright 绕过基础反爬并获取网页内容"""
        async with async_playwright() as p:
            # 启动浏览器，模拟真实环境
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()

            # 注入脚本隐藏自动化特征
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            print(f"[*] 正在请求: {url}")
            try:
                # 访问页面，等待网络空闲
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)

                # 针对多重挑战的处理：等待JS执行
                await asyncio.sleep(5)

                content = await page.content()
                if "验证" in content or "412" in content:
                    print("[!] 命中反爬防护，尝试二次等待...")
                    await asyncio.sleep(10)
                    content = await page.content()

                return content
            except Exception as e:
                print(f"[!] 请求失败: {e}")
                return None
            finally:
                await browser.close()

    async def crawl_colleges(self, pages=1):
        """
        功能 3.1: 院校库基础数据抓取
        """
        base_url = "https://gaokao.chsi.com.cn/sch/search.do?start="
        all_colleges = []

        for i in range(pages):
            start = i * 20
            url = f"{base_url}{start}"
            content = await self.fetch_page(url)

            if not content:
                continue

            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table', class_='ch-table')

            if not table:
                print(f"[!] 第 {i+1} 页未解析到表格数据，可能触发了高强度防火墙。")
                continue

            rows = table.find_all('tr')[1:] # 跳过表头
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

            print(f"[*] 已抓取第 {i+1} 页，共 {len(all_colleges)} 条数据")
            await asyncio.sleep(random.uniform(2, 5))

        if all_colleges:
            df = pd.DataFrame(all_colleges)
            df.to_excel("院校信息导出.xlsx", index=False)
            print(f"\n[+] 院校数据抓取完成！总计: {len(all_colleges)} 条")
            print("[+] 结果已保存至: 院校信息导出.xlsx")
        else:
            print("\n[!] 本次运行未获取到院校数据。")

    async def run_extract(self, url):
        """
        功能 3.2: 招生章程核心信息抽取 (使用 DeepSeek LLM)
        """
        print(f"[*] 正在获取招生章程文本: {url}")
        content = await self.fetch_page(url)

        if not content:
            print("[!] 无法获取网页内容")
            return

        soup = BeautifulSoup(content, 'html.parser')
        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()

        text = soup.get_text(separator='\n', strip=True)

        print("[*] 正在通过 DeepSeek 分析录取规则...")
        prompt = f"""
        你是一位资深高考志愿规划师。请分析下方提供的“高校招生章程”正文，并提取出对考生志愿填报至关重要的关键信息。
        要求：
        1. 必须包含：录取规则（分数优先/专业级差/志愿优先）、投档比例、退档条件。
        2. 必须包含：身体条件限制（如色盲、色弱、身高、视力要求）。
        3. 必须包含：单科成绩或语种要求。
        4. 如果有“非第一志愿”或“征集志愿”的特殊规定，请注明。

        招生章程文本：
        ---
        {text[:12000]}
        ---
        请使用 Markdown 格式输出分析报告，逻辑要清晰。
        """

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个严谨的高考数据分析助手，擅长政策文件解读。"},
                    {"role": "user", "content": prompt}
                ]
            )
            report = response.choices[0].message.content
            print("\n" + "="*20 + " 招生章程分析报告 " + "="*20)
            print(report)

            with open("招生章程分析报告.md", "w", encoding="utf-8") as f:
                f.write(report)
            print("\n[+] 报告已导出至: 招生章程分析报告.md")

        except Exception as e:
            print(f"[!] AI 分析失败: {e}")

    def process_scores(self, file_path):
        """
        功能 3.3: 历年分数/位次数据清洗与整理
        """
        print(f"[*] 正在处理数据文件: {file_path}")
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

            rename_dict = {
                '院校代码': 'code', '学校名称': 'univ_name',
                '最低录取位次': 'min_rank', '最低分': 'min_score'
            }
            df.rename(columns=rename_dict, inplace=True)
            df.dropna(subset=['univ_name'], inplace=True)

            if 'min_rank' in df.columns:
                df['min_rank'] = pd.to_numeric(df['min_rank'], errors='coerce')
                df = df.sort_values(by='min_rank')

            output_name = "处理后的录取数据.xlsx"
            df.to_excel(output_name, index=False)
            print(f"[+] 数据整理完成！已保存至: {output_name}")

        except Exception as e:
            print(f"[!] 数据处理失败: {e}")

async def main():
    parser = argparse.ArgumentParser(description="阳光高考网全能助手 (SunshineTool)")
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("--crawl", action="store_true", help="抓取院校库数据")
    group.add_argument("--extract", type=str, help="输入招生章程URL进行AI分析")
    group.add_argument("--process", type=str, help="输入本地数据文件路径进行清洗整理")

    parser.add_argument("--pages", type=int, default=1, help="抓取页数 (默认1页)")
    parser.add_argument("--key", type=str, help="指定 DeepSeek API Key (也可通过 DEEPSEEK_API_KEY 环境变量设置)")

    args = parser.parse_args()

    tool = SunshineTool(api_key=args.key)

    if args.crawl:
        await tool.crawl_colleges(pages=args.pages)
    elif args.extract:
        await tool.run_extract(args.extract)
    elif args.process:
        tool.process_scores(args.process)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] 程序已停止")
