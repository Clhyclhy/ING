import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from astrbot.api import AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

_CIRCLED_NUMBERS = [
    "①",
    "②",
    "③",
    "④",
    "⑤",
    "⑥",
    "⑦",
    "⑧",
    "⑨",
    "⑩",
    "⑪",
    "⑫",
    "⑬",
    "⑭",
    "⑮",
    "⑯",
    "⑰",
    "⑱",
    "⑲",
    "⑳",
]


@dataclass
class Task:
    title: str
    detail: str


@dataclass
class Collection:
    name: str
    tasks: list[Task]


def to_circled_number(number: int) -> str:
    if 1 <= number <= len(_CIRCLED_NUMBERS):
        return _CIRCLED_NUMBERS[number - 1]
    return f"({number})"


@register(
    "astrbot_plugin_goal_organizer",
    "Lcy23",
    "按两级标题整理用户目标任务，支持查看任务与编号详情查询",
    "1.0.0",
)
class GoalOrganizerPlugin(Star):
    """目标整理助手。

    指令:
    1. /任务 新建 <合集名>
    2. /任务 添加 <合集序号> <任务标题> | <任务说明>
    3. /任务 查看
    4. /任务 详情 <合集序号.任务序号>
    5. /任务 帮助

    快捷查询（可关闭）:
    - 查看任务
    - 1.1
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        data_file_name = str(self.config.get("data_file_name", "goals_data.json"))
        self.max_tasks_per_collection = int(
            self.config.get("max_tasks_per_collection", 200)
        )
        self.allow_plain_text_query = bool(
            self.config.get("allow_plain_text_query", True)
        )

        self.data_path = Path(__file__).parent / data_file_name
        self.collections: list[Collection] = []
        self.pending_detail_updates: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.data_path.exists():
            return
        try:
            data = json.loads(self.data_path.read_text(encoding="utf-8"))
        except Exception:
            self.collections = []
            return

        self.collections = []
        for col in data.get("collections", []):
            tasks = [Task(**task) for task in col.get("tasks", [])]
            self.collections.append(Collection(name=col.get("name", "未命名合集"), tasks=tasks))

    def _save(self) -> None:
        data = {
            "collections": [
                {
                    "name": col.name,
                    "tasks": [asdict(task) for task in col.tasks],
                }
                for col in self.collections
            ]
        }
        self.data_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _help_text(self) -> str:
        return (
            "可用指令:\n"
            "- /任务 新建 <合集名>\n"
            "- /任务 添加 <合集序号> <任务标题> | <任务说明(可空)>\n"
            "- /任务 查看\n"
            "- /任务 详情 <合集序号.任务序号>\n"
            "- /任务 帮助"
        )

    def _event_session_key(self, event: AstrMessageEvent) -> str:
        for attr in ("unified_msg_origin", "session_id", "conversation_id"):
            value = getattr(event, attr, None)
            if value:
                return str(value)

        get_sender_id = getattr(event, "get_sender_id", None)
        if callable(get_sender_id):
            try:
                sender_id = get_sender_id()
                if sender_id:
                    return f"sender:{sender_id}"
            except Exception:
                pass

        for attr in ("sender_id", "user_id"):
            value = getattr(event, attr, None)
            if value:
                return f"sender:{value}"

        return "global"

    def _is_affirmative(self, text: str) -> bool:
        return text.lower() in {"是", "要", "好", "好的", "ok", "yes", "y"}

    def _is_negative(self, text: str) -> bool:
        return text.lower() in {"否", "不用", "不", "不要", "no", "n"}

    def _get_task(self, collection_index: int, task_index: int) -> Task | None:
        if collection_index < 1 or collection_index > len(self.collections):
            return None
        collection = self.collections[collection_index - 1]
        if task_index < 1 or task_index > len(collection.tasks):
            return None
        return collection.tasks[task_index - 1]

    def _render_task_tree(self) -> str:
        if not self.collections:
            return "暂无任务合集。可使用 /任务 新建 <合集名> 创建。"

        lines: list[str] = []
        for i, col in enumerate(self.collections, start=1):
            lines.append(f"{i}、{col.name}")
            if not col.tasks:
                lines.append("  （暂无任务）")
                continue
            for j, task in enumerate(col.tasks, start=1):
                lines.append(f"  {to_circled_number(j)} {task.title}")
        return "\n".join(lines)

    def _show_task_detail(self, collection_index: int, task_index: int) -> str:
        if collection_index < 1 or collection_index > len(self.collections):
            return "合集编号不存在。"

        collection = self.collections[collection_index - 1]
        if task_index < 1 or task_index > len(collection.tasks):
            return "任务编号不存在。"

        task = collection.tasks[task_index - 1]
        detail_text = task.detail if task.detail else "（空）"
        return (
            f"{collection_index}.{task_index} {task.title}\n"
            f"所属合集: {collection.name}\n"
            f"任务说明: {detail_text}"
        )

    @staticmethod
    def _parse_detail_index(text: str) -> tuple[int, int] | None:
        matched = re.fullmatch(r"(\d+)\.(\d+)", text.strip())
        if not matched:
            return None
        return int(matched.group(1)), int(matched.group(2))

    @filter.command_group("任务")
    def task(self):
        """目标任务管理指令组"""
        pass

    @task.command("帮助")
    async def task_help(self, event: AstrMessageEvent):
        """查看目标整理插件帮助"""
        yield event.plain_result(self._help_text())

    @task.command("新建")
    async def task_create_collection(self, event: AstrMessageEvent, name: str = ""):
        """新建任务合集：/任务 新建 <合集名>"""
        name = name.strip()
        if not name:
            yield event.plain_result("合集名不能为空。用法: /任务 新建 <合集名>")
            return

        self.collections.append(Collection(name=name, tasks=[]))
        self._save()
        yield event.plain_result(f"已创建合集: {name}")

    @task.command("添加")
    async def task_add(self, event: AstrMessageEvent, raw: str = ""):
        """添加任务：/任务 添加 <合集序号> <任务标题> | <任务说明(可空)>"""
        if not raw.strip():
            yield event.plain_result(
                "格式错误。用法: /任务 添加 <合集序号> <任务标题> | <任务说明(可空)>"
            )
            return

        parts = raw.strip().split(" ", 1)
        if len(parts) < 2:
            yield event.plain_result(
                "格式错误。用法: /任务 添加 <合集序号> <任务标题> | <任务说明(可空)>"
            )
            return

        try:
            collection_index = int(parts[0])
        except ValueError:
            yield event.plain_result("合集序号必须是数字。")
            return

        body = parts[1].strip()
        if collection_index < 1 or collection_index > len(self.collections):
            yield event.plain_result("合集编号不存在，请先使用 /任务 查看 确认序号。")
            return

        if "|" in body:
            title, detail = body.split("|", 1)
        else:
            title, detail = body, ""
        title = title.strip()
        detail = detail.strip()
        if not title:
            yield event.plain_result("任务标题不能为空。")
            return

        collection = self.collections[collection_index - 1]
        if len(collection.tasks) >= self.max_tasks_per_collection:
            yield event.plain_result(
                f"当前合集任务数量已达到上限 {self.max_tasks_per_collection}。"
            )
            return

        collection.tasks.append(Task(title=title, detail=detail))
        self._save()
        task_no = len(collection.tasks)
        yield event.plain_result(
            f"已添加任务: {collection_index}.{task_no} {title}\n可发送“查看任务”或 /任务 查看 查看归纳结果。"
        )

    @task.command("查看")
    async def task_view(self, event: AstrMessageEvent):
        """查看两级任务标题"""
        yield event.plain_result(self._render_task_tree())

    @task.command("详情")
    async def task_detail(self, event: AstrMessageEvent, index: str = ""):
        """查看任务详情：/任务 详情 <合集序号.任务序号>"""
        parsed = self._parse_detail_index(index)
        if not parsed:
            yield event.plain_result("格式错误。用法: /任务 详情 <合集序号.任务序号>，例如 /任务 详情 1.1")
            return

        collection_index, task_index = parsed
        detail_text = self._show_task_detail(collection_index, task_index)
        yield event.plain_result(detail_text)

        task = self._get_task(collection_index, task_index)
        if task is not None and not task.detail.strip():
            session_key = self._event_session_key(event)
            self.pending_detail_updates[session_key] = {
                "stage": "confirm",
                "collection_index": collection_index,
                "task_index": task_index,
            }
            yield event.plain_result("该任务说明为空，是否现在添加？回复“是”或“否”。")

    @filter.event_message_type(filter.EventMessageType.ALL, priority=1)
    async def quick_query_handler(self, event: AstrMessageEvent):
        """纯文本快捷查询：查看任务、1.1"""
        if not self.allow_plain_text_query:
            return

        text = (event.message_str or "").strip()
        session_key = self._event_session_key(event)

        pending = self.pending_detail_updates.get(session_key)
        if pending:
            stage = pending.get("stage")
            collection_index = int(pending.get("collection_index", 0))
            task_index = int(pending.get("task_index", 0))

            if stage == "confirm":
                if self._is_affirmative(text):
                    pending["stage"] = "input"
                    yield event.plain_result("请直接回复任务说明内容。")
                    event.stop_event()
                    return
                if self._is_negative(text):
                    self.pending_detail_updates.pop(session_key, None)
                    yield event.plain_result("已取消添加任务说明。")
                    event.stop_event()
                    return
                yield event.plain_result("请回复“是”或“否”。")
                event.stop_event()
                return

            if stage == "input":
                task = self._get_task(collection_index, task_index)
                if task is None:
                    self.pending_detail_updates.pop(session_key, None)
                    yield event.plain_result("任务不存在，无法更新说明。")
                    event.stop_event()
                    return

                detail = text.strip()
                if not detail:
                    yield event.plain_result("任务说明不能为空，请重新输入。")
                    event.stop_event()
                    return

                task.detail = detail
                self._save()
                self.pending_detail_updates.pop(session_key, None)
                yield event.plain_result(f"已更新任务说明: {collection_index}.{task_index}")
                event.stop_event()
                return

        if text == "查看任务":
            yield event.plain_result(self._render_task_tree())
            event.stop_event()
            return

        parsed = self._parse_detail_index(text)
        if parsed:
            collection_index, task_index = parsed
            yield event.plain_result(self._show_task_detail(collection_index, task_index))
            task = self._get_task(collection_index, task_index)
            if task is not None and not task.detail.strip():
                self.pending_detail_updates[session_key] = {
                    "stage": "confirm",
                    "collection_index": collection_index,
                    "task_index": task_index,
                }
                yield event.plain_result("该任务说明为空，是否现在添加？回复“是”或“否”。")
            event.stop_event()
