import os
from datetime import date, datetime
from typing import Literal

import numexpr
from langchain_tavily import TavilySearch
from mcp.server.fastmcp import FastMCP

mcp = FastMCP('MCPServer')


# 时间相关
@mcp.tool()
async def get_current_date() -> str:
    '''
    获取当前的日期。

    Args:
        无参数

    Returns:
        例如: 2025-06-10
    '''
    return str(date.today())


@mcp.tool()
async def get_current_time() -> str:
    '''
    获取当前的时间。

    Args:
        无参数

    Returns:
        例如: 17:20:44.400391
    '''
    return str(datetime.now().time())


# 搜索相关
@mcp.tool()
async def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: Literal['basic', 'advanced'] = 'basic',
    topic: Literal['general', 'news', 'finance'] = 'general',
    include_answer: bool = False,
    include_raw_content: bool = False,
    time_range: Literal['day', 'week', 'month', 'year'] | None = None,
) -> dict:
    '''
    使用 Tavily 搜索引擎执行强大的网络搜索。适用于需要获取实时信息以回答问题的场景。

    当用户的问题涉及近期事件、特定事实、或任何需要外部知识库才能回答的内容时，应使用此工具。

    Args:
        query (str): 必需，要执行的搜索查询。应尽可能具体，例如“英伟达最新发布的 GPU 型号是什么？”。
        max_results (int, optional): 返回搜索结果的最大数量。默认为 5。
        search_depth (Literal['basic', 'advanced'], optional): 搜索深度。'basic' 速度快，成本低；'advanced' 进行更深入的分析和事实核查，结果更全面但耗时更长。默认为 'basic'。
        topic (Literal['general', 'news', 'finance'], optional): 搜索的主题领域，用于优化特定领域的搜索结果。默认为 'general'。
        include_answer (bool, optional): 是否在结果中包含一个由 AI 生成的、基于搜索结果的直接总结性回答。默认为 False。
        include_raw_content (bool, optional): 是否在结果中包含每个网页的原始、干净的文本内容。默认为 False。
        time_range (Optional[Literal['day', 'week', 'month', 'year']], optional): 将搜索结果的来源限制在指定的时间范围内发布。默认为 None，即无时间限制。

    Returns:
        Dict[str, Any]: 一个包含搜索结果的字典。
            如果成功，字典将包含键如 'answer' (如果 include_answer=True), 'results' (一个包含来源网站信息的列表) 等。
            'results' 列表中的每个项目都是一个字典，包含 'title', 'url', 'content', 'score' 等字段。
            如果搜索失败或客户端未初始化，将返回一个空的字典。
    '''

    init_params = {
        **(
            {'tavily_api_key': os.getenv('TAVILY_API_KEY')}
            if os.getenv('TAVILY_API_KEY')
            else {'tavily_api_key': None}
        ),
        'max_results': max_results,
        'include_answer': include_answer,
        'include_raw_content': include_raw_content,
    }
    invoke_params = {
        'query': query,
        'search_depth': search_depth,
        'topic': topic,
        'time_range': time_range,
    }
    invoke_params = {i: j for i, j in invoke_params.items() if j is not None}
    try:
        t_s = TavilySearch(**init_params)
        results = await t_s.ainvoke(invoke_params)
        return results
    except Exception as e:
        print(f'tavily_search 工具错误！！！\n{e}')
        return {}


# 计算相关
@mcp.tool()
async def calculator(expression: str) -> str:
    '''
    A powerful and safe calculator.
    Use this tool to evaluate any mathematical expression.
    It supports basic arithmetic (+, -, *, /), exponentiation (**), and more advanced functions like sqrt(), log(), sin(), cos(), tan().

    Args:
        expression (str): must, a string representing a valid mathematical expression. For example, 'sqrt(25) + 5'.

    Returns:
        str: a string that represents the result of a mathematical expression calculation

    Example:
        A user query: 'What is the square root of 25 plus 5?'. The expression is 'sqrt(25) + 5'.
    '''
    # '''
    # 功能强大且安全的计算器。
    # 使用此工具可以计算任何数学表达式。
    # 它支持基本算术 (+, -, *, /)，幂 (**) 和更高级的函数，如 sqrt(), log(), sin(), cos(), tan()。

    # Args:
    #     expression (str): must，表示有效数学表达式的字符串。例如，'sqrt(25) + 5'。

    # Returns:
    #     str: 表示有效数学表达式计算结果的字符串。

    # Example:
    #     用户查询: 25 加 5 的平方根是多少？
    #     expression: 'sqrt(25) + 5'
    # '''
    try:
        result = str(float(numexpr.evaluate(expression.strip())))
        return result
    except Exception as e:
        return f'Failed to evaluate the expression. Error: {e}. Please check if the expression is valid and try again.'


if __name__ == '__main__':
    mcp.run(transport='stdio')
