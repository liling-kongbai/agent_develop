from asyncio import Event, Task
from datetime import datetime
from textwrap import dedent

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class RemindTaskManager:
    '''提醒任务管理器'''

    CREATE_TABLE_SQL = dedent(
        '''\
        CREATE TABLE IF NOT EXISTS remind_tasks (
            id SERIAL PRIMARY KEY,
            description TEXT NOT NULL,
            due_time TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
            context TEXT,
            is_completed BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT LOCALTIMESTAMP NOT NULL,
            completed_at TIMESTAMP WITHOUT TIME ZONE
        );
        '''
    )

    CREATE_INDEX_SQL = dedent(
        '''\
        CREATE INDEX IF NOT EXISTS due_time_idx
            ON remind_tasks (due_time)
            WHERE is_completed = FALSE;
        '''
    )

    INSERT_SQL = dedent(
        '''\
        INSERT INTO remind_tasks (description, due_time, context)
        VALUES (%s, %s, %s)
        '''
    )

    SELECT_NEXT_TASK_DUE_TIME_SQL = dedent(
        '''\
        SELECT due_time FROM remind_tasks WHERE is_completed = FALSE AND due_time > %s ORDER BY due_time ASC LIMIT 1
        '''
    )

    SELECT_DUE_TASKS_SQL = dedent(
        '''\
        SELECT * FROM remind_tasks WHERE is_completed = FALSE AND due_time <= %s ORDER BY due_time ASC
        '''
    )

    UPDATE_SQL = 'UPDATE remind_tasks SET is_completed = TRUE, completed_at = LOCALTIMESTAMP WHERE id = %s'

    def __init__(self, pool: AsyncConnectionPool, remind_task_scheduler_wakeup_event: Event):
        self._pool = pool
        self._remind_task_scheduler_wakeup_event = remind_task_scheduler_wakeup_event

    @staticmethod
    async def setup(conn: AsyncConnection):
        try:
            async with conn.cursor() as cur:
                await cur.execute(RemindTaskManager.CREATE_TABLE_SQL)
                await cur.execute(RemindTaskManager.CREATE_INDEX_SQL)
            await conn.commit()
        except Exception:
            raise

    async def add_task(self, task: Task):
        '''添加任务，将任务添加到数据库并激活提醒任务调度器唤醒事件'''

        task_description = task.description
        async with self._pool.connection() as conn:
            await conn.execute(self.INSERT_SQL, (task_description, task.due_time, task.context))
            await conn.commit()

            self._remind_task_scheduler_wakeup_event.set()

    async def get_next_task_due_time(self) -> datetime | None:
        '''获取下一个任务的到期时间'''

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(self.SELECT_NEXT_TASK_DUE_TIME_SQL, (datetime.now(),))
                row = await cur.fetchone()
                return row[0] if row else None

    async def get_due_tasks(self) -> list[dict]:
        '''获取到期任务'''

        async with self._pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(self.SELECT_DUE_TASKS_SQL, (datetime.now(),))
                return await cur.fetchall()

    async def mark_task_completed(self, task_id: int):
        '''标记任务已完成'''

        async with self._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(self.UPDATE_SQL, (task_id,))
            await conn.commit()
