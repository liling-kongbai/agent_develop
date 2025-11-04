# Agent：一个基于 LangGraph 和 PySide6 的模块化智能体桌面应用

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/liling-kongbai/agent_develop)

---

一个功能强大的桌面智能聊天客户端，它结合了基于 **LangGraph** 构建的复杂后端智能体和使用 **PySide6 (Qt for Python)** 开发的现代化图形用户界面。

本项目旨在展示如何构建一个具备**长期记忆、工具使用、自我反思**能力的复杂智能体，并为其提供一个美观、响应迅速且高度可定制的桌面用户界面。

## 核心特性

### 🧠 模块化智能体后端 (FastAPI & LangGraph)

*   **高级智能体工作流**: 基于 **LangGraph** 构建，实现了复杂的、可控的智能体工作流。通过意图分类（Intent Classification）和反思（Introspection）机制，智能体可以自主决策是直接回答、调用工具还是对自己的回答进行修正和反思，极大地提升了回复质量。
*   **动态 LLM 支持**: 支持在运行时动态切换多种大语言模型（LLM），目前已集成 **Ollama** 和 **DeepSeek**，具备良好的扩展性。
*   **持久化记忆系统**:
    *   **对话历史**: 所有对话都通过 LangGraph 的 `AsyncPostgresSaver` 持久化到 PostgreSQL 数据库中。
    *   **情景记忆 (Episodic Memory)**: 智能体能将对话中的关键情节提炼为结构化的“情景记忆”并存储，在后续对话中可以检索这些记忆来提供更具上下文和个性化的回答。
*   **持久化反思机制**: 智能体会在对话结束一段时候后，自动对本次对话进行复盘和反思，提炼出成功的经验或失败的教训，并形成新的情景记忆。该机制是**持久化的**，即使服务重启，待处理的反思任务也不会丢失。
*   **可扩展的工具集**: 通过 **Multi-Server MCP Client** 协议，可以轻松为智能体扩展各种工具，使其具备与外部世界交互的能力。

### 🖥️ 现代化桌面 UI (PySide6)

*   **类 VS Code 布局**: 采用经典的 IDE 布局，包含活动栏、侧边栏、主内容区和面板区。用户可以通过拖拽分隔条自由调整各区域大小，甚至完全隐藏侧边栏和面板。
*   **流畅的流式响应**: 对话界面完美支持大语言模型的流式（Streaming）输出，文字逐字显示，显著提升用户体验。
*   **丰富的文本渲染**: 对话气泡内支持 **Markdown** 格式的渲染，包括代码块、列表、引用等，并对代码块实现了语法高亮。
*   **实时语音合成 (TTS)**: 无缝集成了 **GPT-SoVITS**，可以将智能体的流式文本回复实时合成为高质量语音并同步播放。
*   **高内聚低耦合设计**:
    *   客户端各 UI 组件之间通过全局**事件总线 (Event Bus)** 进行通信，有效降低了模块间的耦合度，提升了代码的可维护性。
    *   客户端与服务端通过 **HTTP**（用于激活模型、加载历史等一次性请求）和 **WebSocket**（用于实时聊天）结合的方式进行高效通信。

## 技术栈

| 类别             | 技术                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| **后端 (Server)**  | `FastAPI`, `LangChain`, `LangGraph`, `PostgreSQL`, `asyncio`, `psycopg-pool`, `Ollama`, `DeepSeek` |
| **前端 (Client)**  | `PySide6 (Qt 6)`, `markdown-it-py`                                                               |
| **语音合成 (TTS)** | `GPT-SoVITS` (通过 API 调用)                                                                     |

## 代码亮点解析

#### 1. LangGraph 智能体工作流

项目的核心是 `src/server/graph/graph.py` 中定义的 LangGraph 状态图。它并非简单的“输入->LLM->输出”模式，而是精心设计的控制流：

*   **`intent_classifier`**: 接收到用户输入后，第一个节点是意图分类器。它判断用户的意图，决定下一步是直接调用聊天功能，还是需要动用更复杂的工具（通过 `ReAct` 图）。
*   **`introspection_classifier`**: 在 LLM 生成初步回复草稿后，流程会进入反思分类器。它会评估回复草稿是否“充分且恰当”，如果不够好，它会将流程导回意图分类器，让智能体重新思考，形成一个**反思循环**。
*   **`stream_final_response_node`**: 只有当反思分类器认为回复质量达标后，才会进入此节点，将最终润色过的回复流式传输给客户端。

这个流程确保了智能体在输出前会进行自我批判和修正，显著提高了交互的可靠性和质量。

#### 2. 持久化反思机制

在 `src/server/assist/durable_reflection.py` 中，通过包装 LangMem 的 `LocalReflectionExecutor`，实现了一个独特的持久化反思执行器 `DurableReflectionExecutor`。

当一个对话需要被反思时，该任务首先会被持久化到 PostgreSQL 数据库的 `pending_tasks` 命名空间下。只有当反思任务成功执行后，对应的数据库记录才会被删除。这意味着，**即使服务器在反思任务执行前意外关闭或重启，服务恢复后它能自动加载所有待办的反思任务并继续执行**，确保了智能体的长期学习和进化过程不会中断。

#### 3. PySide6 Model-View-Delegate 设计模式

客户端的聊天界面 (`src/client/`) 是 Model-View-Delegate 设计模式的优秀实践：

*   **`ChatMessageModel`**: 作为数据模型，它专门负责管理聊天消息列表。为了处理流式响应，它巧妙地使用 `QTimer` 对数据更新进行节流/防抖，避免了因过于频繁的UI刷新导致的性能问题和界面闪烁。
*   **`ChatListView`**: 作为视图，它继承自 `QListView`，并重写了鼠标事件 (`mousePressEvent`, `mouseMoveEvent` 等) 来实现复杂的文本选择和超链接点击功能。
*   **`ChatBubbleDelegate`**: 作为委托，它完全接管了每一个聊天气泡的绘制 (`paint` 方法) 和尺寸计算 (`sizeHint` 方法)。它使用 `QTextDocument` 来处理 Markdown 到富文本的转换和布局，并通过缓存 `QTextDocument` 实例来优化性能。这种方式将数据和视图彻底分离，使得界面渲染既高效又灵活。

## 致谢

本项目基于以下优秀的开源项目构建，在此表示衷心的感谢：

*   [LangChain & LangGraph](https://github.com/langchain-ai/langchain)
*   [FastAPI](https://github.com/tiangolo/fastapi)
*   [PySide6 (Qt for Python)](https://www.qt.io/qt-for-python)
*   以及所有本项目所依赖的开源库。