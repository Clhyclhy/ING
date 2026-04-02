import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional


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


def to_circled_number(number: int) -> str:
	if 1 <= number <= len(_CIRCLED_NUMBERS):
		return _CIRCLED_NUMBERS[number - 1]
	return f"({number})"


@dataclass
class Task:
	title: str
	detail: str


@dataclass
class Collection:
	name: str
	tasks: List[Task]


class GoalOrganizerPlugin:
	"""
	目标整理插件。

	支持指令:
	- 新建合集 <合集名>
	- 添加任务 <合集序号> <任务标题> | <任务说明>
	- 查看任务
	- <合集序号>.<任务序号>  (例如: 1.1)
	- 帮助
	"""

	def __init__(self, data_file: str = "goals_data.json") -> None:
		self.data_path = Path(data_file)
		self.collections: List[Collection] = []
		self._load()

	def _load(self) -> None:
		if not self.data_path.exists():
			return
		data = json.loads(self.data_path.read_text(encoding="utf-8"))
		self.collections = []
		for col in data.get("collections", []):
			tasks = [Task(**task) for task in col.get("tasks", [])]
			self.collections.append(Collection(name=col["name"], tasks=tasks))

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
			"1. 新建合集 <合集名>\n"
			"2. 添加任务 <合集序号> <任务标题> | <任务说明>\n"
			"   例: 添加任务 1 完成需求文档 | 明确范围、里程碑和验收标准\n"
			"3. 查看任务\n"
			"4. 输入编号查看详情，例如: 1.1\n"
			"5. 帮助"
		)

	def _render_task_tree(self) -> str:
		if not self.collections:
			return "暂无任务合集。可先用“新建合集 <合集名>”创建。"

		lines: List[str] = []
		for i, col in enumerate(self.collections, start=1):
			lines.append(f"{i}、{col.name}")
			if not col.tasks:
				lines.append("  (暂无任务)")
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
		return (
			f"{collection_index}.{task_index} {task.title}\n"
			f"所属合集: {collection.name}\n"
			f"任务说明: {task.detail}"
		)

	def _create_collection(self, name: str) -> str:
		name = name.strip()
		if not name:
			return "合集名不能为空。"
		self.collections.append(Collection(name=name, tasks=[]))
		self._save()
		return f"已创建合集: {name}"

	def _add_task(self, collection_index: int, task_title: str, task_detail: str) -> str:
		if collection_index < 1 or collection_index > len(self.collections):
			return "合集编号不存在，请先用“查看任务”确认序号。"

		task_title = task_title.strip()
		task_detail = task_detail.strip()
		if not task_title:
			return "任务标题不能为空。"
		if not task_detail:
			return "任务说明不能为空。"

		collection = self.collections[collection_index - 1]
		collection.tasks.append(Task(title=task_title, detail=task_detail))
		self._save()
		task_no = len(collection.tasks)
		return (
			f"已添加任务: {collection_index}.{task_no} {task_title}\n"
			"可发送“查看任务”查看最新归纳结果。"
		)

	def handle_message(self, text: str) -> str:
		content = text.strip()
		if not content:
			return self._help_text()

		if content in {"帮助", "help", "?"}:
			return self._help_text()

		if content == "查看任务":
			return self._render_task_tree()

		detail_match = re.fullmatch(r"(\d+)\.(\d+)", content)
		if detail_match:
			collection_index = int(detail_match.group(1))
			task_index = int(detail_match.group(2))
			return self._show_task_detail(collection_index, task_index)

		if content.startswith("新建合集"):
			name = content.replace("新建合集", "", 1).strip()
			return self._create_collection(name)

		if content.startswith("添加任务"):
			# 格式: 添加任务 <合集序号> <任务标题> | <任务说明>
			payload = content.replace("添加任务", "", 1).strip()
			parts = payload.split(" ", 1)
			if len(parts) < 2:
				return "格式错误。请使用: 添加任务 <合集序号> <任务标题> | <任务说明>"

			try:
				collection_index = int(parts[0])
			except ValueError:
				return "合集序号必须是数字。"

			body = parts[1].strip()
			if "|" not in body:
				return "请用“|”分隔任务标题和任务说明。"

			task_title, task_detail = body.split("|", 1)
			return self._add_task(collection_index, task_title, task_detail)

		return "未识别的指令。发送“帮助”查看可用命令。"


def main() -> None:
	plugin = GoalOrganizerPlugin()
	print("目标整理插件已启动。输入“帮助”查看指令，输入“退出”结束。")
	while True:
		user_input = input("你: ").strip()
		if user_input in {"退出", "exit", "quit"}:
			print("插件已退出。")
			break
		print("插件:")
		print(plugin.handle_message(user_input))


if __name__ == "__main__":
	main()
