from __future__ import annotations  # 自动前向引用，不在代码运行时立即计算类型提示，而是当作字符串先存起来

import asyncio
import typing
import uuid
from asyncio import create_task, gather, to_thread, wrap_future
from concurrent.futures import Future
from time import time
from traceback import format_exc
from typing import Any, Optional

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.store.base import BaseStore, SearchItem
from langmem.reflection import LocalReflectionExecutor, MemoryItem

PENDING_TASKS_NAMESPACE = ('memories', 'pending_tasks')
SEARCH_LIMIT_FOR_RECOVERY = 1000000
SENTINEL = object()


class DurableReflectionExecutor:
    '''持久化反思执行器，LocalReflectionExecutor 包装器，持久化待办任务并提供重启恢复'''

    def __init__(self, reflector: Runnable, store: BaseStore):
        self._inner_executor = LocalReflectionExecutor(reflector, store=store)
        self._store = store

    @classmethod
    def init(cls, reflector: Runnable, store: BaseStore) -> DurableReflectionExecutor:
        instance = cls(reflector, store)
        instance._resume_pending_tasks()
        return instance

    @classmethod
    async def ainit(cls, reflector: Runnable, store: BaseStore) -> DurableReflectionExecutor:
        instance = cls(reflector, store)
        await instance._aresume_pending_tasks()
        return instance

    # 辅助相关
    def _resume_pending_items(self, items: list[SearchItem]):
        '''恢复待办项'''

        if not items:
            return

        now = time()
        for item in items:
            try:
                task_data = item.value
                payload = task_data.get('payload')
                config = task_data.get('config')
                execute_at = task_data.get('execute_at')

                if not payload or not config or not execute_at:
                    continue

                remaining_seconds = max(0, execute_at - now)
                self.submit(payload, config, after_seconds=remaining_seconds)
            except Exception:
                print(f'<_resume_pending_items> 恢复待办项报错！！！\n{format_exc()}')

    async def _aresume_pending_items(self, items: list[SearchItem]):
        '''恢复待办项'''

        if not items:
            return

        now = time()
        resume_pending_tasks = []
        for item in items:
            try:
                task_data = item.value
                payload = task_data.get('payload')
                config = task_data.get('config')
                execute_at = task_data.get('execute_at')

                if not payload or not config or not execute_at:
                    continue

                remaining_seconds = max(0, execute_at - now)
                resume_pending_tasks.append(await self.asubmit(payload, config, after_seconds=remaining_seconds))
            except Exception:
                print(f'<_resume_pending_items> 恢复待办项报错！！！\n{format_exc()}')

        try:
            if resume_pending_tasks:
                await gather(*resume_pending_tasks)
        except Exception:
            print(f'<_resume_pending_items> 恢复待办项报错！！！\n{format_exc()}')

    def _resume_pending_tasks(self):
        '''恢复待办任务'''

        try:
            pending_items = self._store.search(PENDING_TASKS_NAMESPACE, limit=SEARCH_LIMIT_FOR_RECOVERY)
            self._resume_pending_items(pending_items)
        except Exception:
            print(f'<_resume_pending_tasks> 恢复待办任务报错！！！\n{format_exc()}')

    async def _aresume_pending_tasks(self):
        '''恢复待办任务'''

        try:
            pending_items = await self._store.asearch(PENDING_TASKS_NAMESPACE, limit=SEARCH_LIMIT_FOR_RECOVERY)
            await self._aresume_pending_items(pending_items)
        except Exception:
            print(f'<_aresume_pending_tasks> 恢复待办任务报错！！！\n{format_exc()}')

    def _resolve_thread_id(
        self,
        config: RunnableConfig,
        thread_id: Optional[typing.Union[str, uuid.UUID]] = SENTINEL,
    ) -> str:
        '''解析 thread_id'''

        if thread_id and thread_id is not SENTINEL:
            return str(thread_id)

        resolved_thread_id = config.get('configurable', {}).get('thread_id')
        if not resolved_thread_id:
            raise ValueError('<_resolve_thread_id> 无法解析 thread_id，请在配置中提供或直接提供。')
        return str(resolved_thread_id)

    # 功能相关
    def submit(
        self,
        payload: dict[str, Any],
        /,
        config: RunnableConfig | None = None,
        *,
        after_seconds: int = 0,
        thread_id: Optional[typing.Union[str, uuid.UUID]] = SENTINEL,
    ) -> Future:
        resolved_thread_id = self._resolve_thread_id(config, thread_id)
        execute_at = time() + after_seconds
        task_data = {'payload': payload, 'config': config, 'execute_at': execute_at}
        try:
            self._store.put(PENDING_TASKS_NAMESPACE, resolved_thread_id, task_data)
        except Exception:
            print(f'<submit> 提交反思待办任务 {resolved_thread_id} 失败！！！\n{format_exc()}')

        future = self._inner_executor.submit(
            payload, config, after_seconds=after_seconds, thread_id=resolved_thread_id
        )

        def _clean_on_done(future: Future):
            if not future.cancelled() and future.exception() is None:
                try:
                    self._store.delete(PENDING_TASKS_NAMESPACE, resolved_thread_id)
                except Exception:
                    print(f'<_clean_on_done> 清理报错！！！\n{format_exc()}')

        future.add_done_callback(_clean_on_done)
        return future

    async def asubmit(
        self,
        payload: dict[str, Any],
        /,
        config: RunnableConfig | None = None,
        *,
        after_seconds: int = 0,
        thread_id: Optional[typing.Union[str, uuid.UUID]] = SENTINEL,
    ) -> asyncio.Future:
        resolved_thread_id = self._resolve_thread_id(config, thread_id)
        execute_at = time() + after_seconds
        task_data = {'payload': payload, 'config': config, 'execute_at': execute_at}
        try:
            await self._store.aput(PENDING_TASKS_NAMESPACE, resolved_thread_id, task_data)
        except Exception:
            print(f'<asubmit> 提交反思待办任务 {resolved_thread_id} 失败！！！\n{format_exc()}')

        future = await to_thread(
            self._inner_executor.submit,
            payload,
            config=config,
            after_seconds=after_seconds,
            thread_id=resolved_thread_id,
        )

        async def _async_clean_on_done(future: Future):
            try:
                await wrap_future(future)
                if not future.cancelled() and future.exception() is None:
                    await self._store.adelete(PENDING_TASKS_NAMESPACE, resolved_thread_id)
            except Exception:
                print(f'<_async_clean_on_done> 清理报错！！！\n{format_exc()}')

        create_task(_async_clean_on_done(future))
        return wrap_future(future)

    # 代理相关
    def search(self, *args, **kwargs) -> list[MemoryItem]:
        return self._inner_executor.search(*args, **kwargs)

    def asearch(self, *args, **kwargs) -> list[MemoryItem]:
        return self._inner_executor.asearch(*args, **kwargs)

    def shutdown(self, wait=True, *, cancel_futures=False):
        self._inner_executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self):
        return self

    def __aenter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True, cancel_futures=True)
        return False

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await to_thread(self.shutdown, wait=True, cancel_futures=True)
        return False
