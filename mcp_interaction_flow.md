# MCP Host 与 MCP Server 交互流程图

## 整体架构图

```mermaid
graph TD
    A[MCP Host] -->|①JSON-RPC请求| B[mcp_logger.py]
    B -->|②转发请求| C[MCP Server<br/>weather.py]
    C -->|③JSON-RPC响应| B
    B -->|④转发响应| A
    B -->|记录日志| D[mcp_traffic.log]
```

## 详细交互流程图

### 1. 初始化阶段

```mermaid
sequenceDiagram
    participant H as MCP Host
    participant L as mcp_logger.py
    participant S as MCP Server (weather.py)
    
    H->>L: {"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"Cline","version":"3.78.0"}},"jsonrpc":"2.0","id":0}
    L->>S: 转发initialize请求
    S->>L: 返回初始化结果
    L->>H: {"jsonrpc":"2.0","id":0,"result":{"protocolVersion":"2025-11-25","capabilities":{"experimental":{},"prompts":{"listChanged":false},"resources":{"subscribe":false,"listChanged":false},"tools":{"listChanged":false}},"serverInfo":{"name":"weather","version":"1.27.0"}}}
    
    H->>L: {"method":"notifications/initialized","jsonrpc":"2.0"}
    L->>S: 转notifications/initialized通知
```
> mcp_traffic.log 13-25行

![初始化](./.images/init.png)

### 2. 工具和能力发现阶段

```mermaid
sequenceDiagram
    participant H as MCP Host
    participant L as mcp_logger.py
    participant S as MCP Server (weather.py)
    
    H->>L: {"method":"tools/list","jsonrpc":"2.0","id":1}
    L->>S: 转发tools/list请求
    S->>L: 返回工具列表
    L->>H: {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"get_alerts","description":"Get weather alerts for a US state.\n\n ..... }}
    
    H->>L: {"method":"resources/list","jsonrpc":"2.0","id":2}
    L->>S: 转发resources/list请求
    S->>L: 返回资源列表
    L->>H: {"jsonrpc":"2.0","id":2,"result":{"resources":[]}}
    
    H->>L: {"method":"resources/templates/list","jsonrpc":"2.0","id":3}
    L->>S: 转发resources/templates/list请求
    S->>L: 返回资源模板列表
    L->>H: {"jsonrpc":"2.0","id":3,"result":{"resourceTemplates":[]}}
    
    H->>L: {"method":"prompts/list","jsonrpc":"2.0","id":4}
    L->>S: 转发prompts/list请求
    S->>L: 返回提示词列表
    L->>H: {"jsonrpc":"2.0","id":4,"result":{"prompts":[]}}
```
> mcp_traffic.log 28-65行，因文本较长，部分省略

![call](./.images/call.png)

### 3. 工具调用阶段

```mermaid
sequenceDiagram
    participant H as MCP Host
    participant L as mcp_logger.py
    participant S as MCP Server (weather.py)
    participant API as NWS API
    
    H->>L: {"method":"tools/call","params":{"name":"get_forecast","arguments":{"latitude":40.7128,"longitude":-74.006}},"jsonrpc":"2.0","id":5}
    L->>S: 转发tools/call请求
    S->>API: 请求天气数据 (NWS API)
    API->>S: 返回JSON格式的天气数据
    S->>L: 返回工具调用结果
    L->>H: {"jsonrpc":"2.0","id":5,"result":{"content":[{"type":"text","text":"\n            Tonight:\n            Temperature: 44°F\n  ......  "},"isError":false}}
```
> mcp_traffic.log 75-82行，因文本较长，部分省略

![call](./.images/call.png)

## 数据流说明

1. **初始化流程**：
   - Host发送`initialize`请求，包含协议版本、客户端信息和能力
   - Server返回支持协议版本、能力和服务器信息
   - Host发送`notifications/initialized`通知，表示初始化完成

2. **能力发现流程**：
   - Host依次请求工具列表、资源列表、资源模板列表和提示词列表
   - Server返回相应的能力信息

3. **工具调用流程**：
   - Host调用`get_forecast`工具，传入经纬度参数
   - Server接收请求，调用NWS API获取天气数据
   - Server处理数据并格式化响应
   - 通过`mcp_logger.py`返回结果给Host

## 日志记录

所有交互都通过`mcp_logger.py`进行中转，并记录到`mcp_traffic.log`文件中，包含：
- 时间戳
- 传输方向（HOST -> SERVER 或 SERVER -> HOST）
- 完整的JSON-RPC协议消息内容
- 错误信息（如有）