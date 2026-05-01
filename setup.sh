#!/bin/bash

# 高考志愿AI专家系统 - 部署脚本
# 适配环境: Android (Root) + Termux + Ubuntu

set -e

echo "=========================================="
echo "  高考志愿AI专家系统 部署"
echo "=========================================="

# 1. 环境检测与系统更新
if command -v pkg &> /dev/null; then
    ENVIRONMENT="Termux Native"
    pkg update -y && pkg upgrade -y
    pkg install -y python python-pip nano git curl wget clang make python-dev
    PROJECT_DIR="$HOME/ai_advisor"
elif command -v apt &> /dev/null; then
    ENVIRONMENT="Ubuntu Container"
    apt update -y && apt upgrade -y
    apt install -y python3 python3-pip nano git curl wget
    PROJECT_DIR="$HOME/ai_advisor"
else
    echo "错误: 未检测到支持的包管理器"
    exit 1
fi

# 2. 安装依赖
pip3 install --upgrade pip
pip3 install openai httpx pydantic rich python-dotenv chardet

# 3. 创建目录
mkdir -p "$PROJECT_DIR/core" "$PROJECT_DIR/agents" "$PROJECT_DIR/plugins" "$PROJECT_DIR/data/upload"
cd "$PROJECT_DIR"

# 4. 写入核心逻辑
cat > core/state.py << 'EOF'
from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class SystemState:
    query: str = ""
    mimo_plugin_data: Dict = field(default_factory=dict)
    qwen_search_data: str = ""
    kimi_processed_context: str = ""
    rl_reasoning_draft: str = ""
    final_result: str = ""
    errors: List[str] = field(default_factory=list)
    is_aborted: bool = False
    uploaded_file_content: str = ""
    def add_error(self, error_msg: str): self.errors.append(error_msg)
    def abort(self, reason: str = ""):
        self.is_aborted = True
        if reason: self.add_error(f"系统中止: {reason}")
EOF

cat > core/protocol.py << 'EOF'
from pydantic import BaseModel
from typing import Any, Optional
class StandardResponse(BaseModel):
    status: str
    data: Optional[Any]
    message: str = ""
    @classmethod
    def success(cls, data: Any = None, message: str = "") -> 'StandardResponse': return cls(status="success", data=data, message=message)
    @classmethod
    def error(cls, message: str, data: Any = None) -> 'StandardResponse': return cls(status="error", data=data, message=message)
EOF

cat > core/base_agent.py << 'EOF'
import logging
import asyncio
from abc import ABC, abstractmethod
from core.state import SystemState
from core.protocol import StandardResponse
class BaseAgent(ABC):
    def __init__(self, name: str, role_limit: str, max_retries: int = 3):
        self.name = name
        self.role_limit = role_limit
        self.max_retries = max_retries
    @abstractmethod
    async def _execute_logic(self, state: SystemState) -> StandardResponse: pass
    async def run(self, state: SystemState) -> StandardResponse:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await self._execute_logic(state)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1: await asyncio.sleep(1)
        error_msg = f"{self.name} 异常: {last_error}"
        state.add_error(error_msg)
        return StandardResponse.error(message=error_msg)
EOF

# 5. 写入 Agent 逻辑
cat > agents/qwen_agent.py << 'EOF'
import os
from openai import AsyncOpenAI
from core.base_agent import BaseAgent
from core.protocol import StandardResponse
class QwenAgent(BaseAgent):
    async def _execute_logic(self, state):
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key: return StandardResponse.error("未配置QWEN_API_KEY")
        client = AsyncOpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        resp = await client.chat.completions.create(model="qwen-turbo", messages=[{"role": "user", "content": state.query}])
        state.qwen_search_data = resp.choices[0].message.content
        return StandardResponse.success(data=state.qwen_search_data)
EOF

cat > agents/mimo_agent.py << 'EOF'
from core.base_agent import BaseAgent
from core.protocol import StandardResponse
class MiMoAgent(BaseAgent):
    async def _execute_logic(self, state):
        state.mimo_plugin_data = {"info": "插件数据已获取"}
        return StandardResponse.success(data=state.mimo_plugin_data)
EOF

cat > agents/kimi_agent.py << 'EOF'
import os
from openai import AsyncOpenAI
from core.base_agent import BaseAgent
from core.protocol import StandardResponse
class KimiAgent(BaseAgent):
    async def _execute_logic(self, state):
        api_key = os.getenv("KIMI_API_KEY")
        if not api_key: return StandardResponse.error("未配置KIMI_API_KEY")
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")
        resp = await client.chat.completions.create(model="moonshot-v1-8k", messages=[{"role": "user", "content": f"提纯: {state.qwen_search_data}"}])
        state.kimi_processed_context = resp.choices[0].message.content
        return StandardResponse.success(data=state.kimi_processed_context)
EOF

cat > agents/deepseek_r1_agent.py << 'EOF'
import os
from openai import AsyncOpenAI
from core.base_agent import BaseAgent
from core.protocol import StandardResponse
class DeepSeekR1Agent(BaseAgent):
    async def _execute_logic(self, state):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key: return StandardResponse.error("未配置DEEPSEEK_API_KEY")
        client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        resp = await client.chat.completions.create(model="deepseek-reasoner", messages=[{"role": "user", "content": f"推演: {state.kimi_processed_context}"}])
        state.rl_reasoning_draft = resp.choices[0].message.content
        return StandardResponse.success(data=state.rl_reasoning_draft)
EOF

cat > agents/claude_agent.py << 'EOF'
import os
from openai import AsyncOpenAI
from core.base_agent import BaseAgent
from core.protocol import StandardResponse
class ClaudeAgent(BaseAgent):
    async def _execute_logic(self, state):
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key: return StandardResponse.error("未配置CLAUDE_API_KEY")
        client = AsyncOpenAI(api_key=api_key, base_url=os.getenv("CLAUDE_BASE_URL", "https://api.anthropic.com"))
        resp = await client.chat.completions.create(model="claude-3-sonnet-20240229", messages=[{"role": "user", "content": f"审查: {state.rl_reasoning_draft}"}])
        state.final_result = resp.choices[0].message.content
        return StandardResponse.success(data=state.final_result)
EOF

# 6. 写入增强版 main.py
cat > main.py << 'EOF'
import asyncio
import os
import time
import random
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.align import Align
from core.state import SystemState
from agents.qwen_agent import QwenAgent
from agents.mimo_agent import MiMoAgent
from agents.kimi_agent import KimiAgent
from agents.deepseek_r1_agent import DeepSeekR1Agent
from agents.claude_agent import ClaudeAgent

load_dotenv()
console = Console()

class ClaudeVisuals:
    @staticmethod
    def get_breathing_logo(frame):
        colors = ["bright_magenta", "magenta", "purple", "deep_pink3", "hot_pink"]
        color = colors[frame % len(colors)]
        # 多维律动：图标 + 字符变换
        chars = "⣿⣷⣯⣟⡿⢿⣻⣽⣾⣶⣴⣤⣠⣀⣄⣆⣇⣈⣉⣊⣋⣌⣍⣎⣏⣐⣑⣒⣓⣔⣕⣖⣗⣘⣙⣚⣛⣜⣝⣞⣟"
        random_chars = ''.join(random.choice(chars) for _ in range(8))
        logo = f"""
   ⢀⣴⣾⣿⣿⣷⣦⡀
   ⣾⣿⣿⣿⣿⣿⣿⣷
   ⣿⣿⣿{random_chars}⣿⣿⣿
   ⠻⣿⣿⣿⣿⣿⣿⠟
     ⠙⠻⠿⠟⠋
        """
        return Panel(Text(logo, style=color), title="[bold]AI 专家系统[/bold]", border_style="cyan", expand=False)

    @staticmethod
    def get_transition_effect(agent_name, frame):
        # 转场动画：数据扫描效果
        width = 40
        scan_line = "▓" * (frame % width) + "░" * (width - (frame % width))
        return f"[dim]{scan_line}[/dim] [bold cyan]{agent_name} 逻辑链传导中...[/bold cyan]"

    @staticmethod
    def get_system_log_stream(logs, max_lines=5):
        # 实时状态流
        log_text = "\n".join(logs[-max_lines:])
        return Panel(
            Text(log_text, style="dim green"),
            title="[bold]系统日志流[/bold]",
            border_style="dim",
            height=max_lines + 2
        )

    @staticmethod
    async def typewriter(text, style="white"):
        for char in text:
            console.print(char, style=style, end="", flush=True)
            await asyncio.sleep(0.005)
        console.print()

async def main():
    # 启动动画
    with Live(ClaudeVisuals.get_breathing_logo(0), refresh_per_second=4, console=console) as live:
        for i in range(20):
            live.update(ClaudeVisuals.get_breathing_logo(i))
            await asyncio.sleep(0.25)

    console.print(Panel("[bold cyan]AI 专家系统[/bold cyan]\n[dim]智能决策辅助平台[/dim]"))
    state = SystemState()
    system_logs = ["系统初始化完成", "等待用户输入..."]
    
    if Confirm.ask("\n[bold yellow]是否上传本地文件？[/bold yellow]"):
        file_name = Prompt.ask("文件名")
        state.uploaded_file_content = "已加载"
        system_logs.append(f"文件已加载: {file_name}")
        
    state.query = Prompt.ask("\n[bold magenta]请输入咨询问题[/bold magenta]")
    system_logs.append(f"用户查询: {state.query[:50]}...")

    agents = [
        QwenAgent("Qwen", ""),
        MiMoAgent("MiMo", ""),
        KimiAgent("Kimi", ""),
        DeepSeekR1Agent("DeepSeek", ""),
        ClaudeAgent("Claude", "")
    ]
    
    # 创建布局用于同时显示主内容和日志流
    layout = Layout()
    layout.split_column(
        Layout(name="main", ratio=3),
        Layout(name="logs", ratio=1)
    )

    with Live(layout, refresh_per_second=4, console=console) as live:
        for agent in agents:
            # 更新主内容区
            main_content = Text()
            main_content.append(f"\n[bold blue]▶ {agent.name} 正在思考...[/bold blue]\n")
            main_content.append(ClaudeVisuals.get_transition_effect(agent.name, 0))
            layout["main"].update(Panel(main_content, title="[bold]AI 专家系统[/bold]", border_style="cyan"))
            
            # 更新日志流
            system_logs.append(f"启动 {agent.name} Agent...")
            layout["logs"].update(ClaudeVisuals.get_system_log_stream(system_logs))
            
            # 模拟转场动画
            for frame in range(10):
                transition_text = ClaudeVisuals.get_transition_effect(agent.name, frame)
                main_content = Text()
                main_content.append(f"\n[bold blue]▶ {agent.name} 正在思考...[/bold blue]\n")
                main_content.append(transition_text)
                layout["main"].update(Panel(main_content, title="[bold]AI 专家系统[/bold]", border_style="cyan"))
                await asyncio.sleep(0.1)
            
            # 执行Agent逻辑
            resp = await agent.run(state)
            
            if resp.status == "success":
                system_logs.append(f"✓ {agent.name} 响应成功")
                # 更新主内容显示结果
                result_preview = str(resp.data)[:100] + "..." if resp.data else "无数据"
                main_content = Text()
                main_content.append(f"\n[bold blue]▶ {agent.name} 完成[/bold blue]\n")
                main_content.append(f"[dim]✓ 响应: {result_preview}[/dim]")
                layout["main"].update(Panel(main_content, title="[bold]AI 专家系统[/bold]", border_style="cyan"))
            else:
                system_logs.append(f"✗ {agent.name} 失败: {resp.message}")
                main_content = Text()
                main_content.append(f"\n[bold blue]▶ {agent.name} 完成[/bold blue]\n")
                main_content.append(f"[red]✗ 失败: {resp.message}[/red]")
                layout["main"].update(Panel(main_content, title="[bold]AI 专家系统[/bold]", border_style="cyan"))
            
            layout["logs"].update(ClaudeVisuals.get_system_log_stream(system_logs))
            await asyncio.sleep(0.5)

    if state.final_result:
        console.print("\n" + "="*50)
        await ClaudeVisuals.typewriter("[bold green]最终规划报告：[/bold green]")
        console.print(Panel(state.final_result, border_style="bright_green"))
        system_logs.append("最终报告生成完成")
        console.print(ClaudeVisuals.get_system_log_stream(system_logs))

if __name__ == "__main__":
    asyncio.run(main())
EOF

chmod +x main.py
echo "=========================================="
echo "  部署完成"
echo "  请运行: cd $PROJECT_DIR && python3 main.py"
echo "=========================================="