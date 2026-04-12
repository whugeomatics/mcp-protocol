# MCP Weather Demo（MCP Host 与 MCP Server 交互学习项目）

## 项目介绍

这个工程用于学习和掌握 **MCP Host 与 MCP Server 之间的交互协议流程**。

项目核心思路：

- `weather.py` 提供一个 MCP Server（基于 FastMCP）
- `mcp_logger.py` 作为“透明中转代理”插入在 Host 和真实 Server 之间
- 所有 Host ↔ Server 的通信内容都会被记录到日志，便于学习协议交互细节

整个交互过程的日志记录在：

- `mcp_traffic.log`

> 参考示例（官方文档）：
> https://modelcontextprotocol.io/docs/develop/build-server

---

## 项目结构

```text
mcp-protocol/
├── weather.py         # MCP weather server，提供天气查询工具
├── mcp_logger.py      # MCP 通信中转与日志记录代理
├── mcp_traffic.log    # 运行后生成/追加的通信日志
└── requirement.txt    # 依赖列表
```

---

## 交互流程说明

为了学习 MCP Host 和 MCP Server 的交互过程，在 MCP Server 的启动命令中，不是直接执行：

```bash
uv --directory /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather run weather.py
```

而是改为先经过 `mcp_logger.py`：

```bash
python3 /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/mcp_logger.py \
  uv --directory /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather run weather.py
```

这样 `mcp_logger.py` 会负责：

1. 接收 MCP Host 发给 Server 的 stdin 消息
2. 转发给真实 MCP Server
3. 接收 Server 返回给 Host 的 stdout 消息
4. 全量记录双向消息（含时间戳）到 `mcp_traffic.log`

---

## MCP 配置示例

在 MCP Host 侧可按如下方式配置：

```json
{
  "mcpServers": {
    "weather": {
      "disabled": false,
      "timeout": 60,
      "type": "stdio",
      "command": "python3",
      "args": [
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/mcp_logger.py",
        "uv",
        "--directory",
        "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather",
        "run",
        "weather.py"
      ]
    }
  }
}
```

> 重点：在 `uv run weather.py` 前增加 `mcp_logger.py` 做数据中转和日志记录。

---

## 依赖安装

项目依赖见 `requirements.txt`，请先安装。

### 1) 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2) 安装 Python 依赖

可选择以下任一方式：

```bash
pip install -r requirement.txt
```

或（推荐，使用 uv）：

```bash
uv sync
```

---

## 运行与学习建议

1. 按上面的 MCP 配置启动 `weather` server。
2. 在 Host 中调用 `get_alerts`、`get_forecast` 等工具。
3. 打开 `mcp_traffic.log` 观察完整的 JSON-RPC 往返过程。
4. 重点关注 initialize、tools/list、tools/call 等请求与响应结构。

通过这个流程，你可以直观看到 MCP Host 与 MCP Server 的协议交互细节。
