"""P1 参考实现：Team + Mailbox + Member 的最小 Python 模拟。

用途：
- 展示 ai-rd-team 未来 Adapter 层的核心抽象
- 作为真实 CodeBuddy Team 实验的对照参考
- 未来详细设计阶段可演进成正式实现

不是目标：
- 不调用真实 LLM
- 不考虑性能优化
- 不做错误恢复

用法：
    python team.py
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Message:
    """成员间消息。"""
    from_: str
    to: str                  # 可以是成员名，也可以是 "all" 或 "main"
    content: str
    msg_type: str = "message"  # message / broadcast / shutdown_request
    summary: str = ""
    ts: float = field(default_factory=time.time)


class Mailbox:
    """单个成员的收件箱。"""

    def __init__(self, owner: str):
        self.owner = owner
        self.queue: queue.Queue[Message] = queue.Queue()

    def put(self, msg: Message) -> None:
        self.queue.put(msg)

    def get(self, timeout: float | None = None) -> Message | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None


class Team:
    """团队容器，负责成员注册和消息路由。

    对应 CodeBuddy 的 team_create + 内部 dispatcher。
    """

    def __init__(self, team_name: str, main_handler: Callable[[Message], None] | None = None):
        self.team_name = team_name
        self.members: dict[str, Member] = {}
        self.main_mailbox: list[Message] = []      # 给 main 的消息
        self.main_handler = main_handler
        self.message_log: list[Message] = []       # 全局消息日志（用于观察）
        self._lock = threading.Lock()

    def spawn(self, name: str, role_prompt: str, behave: Callable[[Member], None]) -> Member:
        """对应 task(name=..., team_name=..., prompt=...) 的派发。"""
        member = Member(name=name, team=self, role_prompt=role_prompt, behave=behave)
        self.members[name] = member
        member.start()
        return member

    def deliver(self, msg: Message) -> None:
        """消息路由。"""
        with self._lock:
            self.message_log.append(msg)

        if msg.to == "main":
            self.main_mailbox.append(msg)
            if self.main_handler:
                self.main_handler(msg)
            return

        if msg.to == "all":
            for m in self.members.values():
                if m.name != msg.from_:
                    m.mailbox.put(msg)
            return

        if msg.to in self.members:
            self.members[msg.to].mailbox.put(msg)
        else:
            # 发给不存在的成员，退回 main
            self.main_mailbox.append(
                Message(from_="system", to="main",
                        content=f"[未送达] {msg.from_} → {msg.to}: {msg.content}",
                        summary="投递失败")
            )

    def shutdown_all(self) -> None:
        """对应 team_delete 的前置：向所有成员发 shutdown_request。"""
        for m in list(self.members.values()):
            self.deliver(Message(from_="main", to=m.name, content="",
                                 msg_type="shutdown_request", summary="关闭请求"))
        for m in list(self.members.values()):
            m.thread.join(timeout=2.0)
        self.members.clear()


class Member:
    """团队成员，跑在独立线程里模拟独立上下文。"""

    def __init__(self, name: str, team: Team, role_prompt: str, behave: Callable[["Member"], None]):
        self.name = name
        self.team = team
        self.role_prompt = role_prompt
        self.mailbox = Mailbox(name)
        self.behave = behave
        self.thread = threading.Thread(target=self._run, name=f"member-{name}", daemon=True)
        self.stopped = False

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        try:
            self.behave(self)
        except Exception as e:
            self.team.deliver(Message(from_=self.name, to="main",
                                      content=f"成员崩溃：{e}",
                                      summary="异常"))

    def send(self, to: str, content: str, summary: str = "", msg_type: str = "message") -> None:
        """对应 send_message。"""
        self.team.deliver(Message(from_=self.name, to=to, content=content,
                                  summary=summary, msg_type=msg_type))

    def recv(self, timeout: float | None = 5.0) -> Message | None:
        """等待收件箱消息。"""
        return self.mailbox.get(timeout=timeout)


# ============== 演示：计算器团队 ==============

def architect_behave(me: Member) -> None:
    # 等待启动消息
    msg = me.recv()
    if msg is None:
        return
    # 产出设计
    me.send("developer",
            "接口：def calc(op: str, a: float, b: float) -> float\n"
            "异常：除零抛 ZeroDivisionError",
            summary="接口设计")
    # 等待 developer 的问题
    while not me.stopped:
        msg = me.recv(timeout=3.0)
        if msg is None:
            break
        if msg.msg_type == "shutdown_request":
            break
        if "问题" in msg.content or "?" in msg.content:
            me.send(msg.from_, "按照设计文档，保持健壮性即可", summary="回答")
        else:
            # 完成
            me.send("main", "架构师工作完成", summary="完成")
            break


def developer_behave(me: Member) -> None:
    # 等待 architect 接口
    msg = me.recv()
    if msg is None or msg.msg_type == "shutdown_request":
        return
    design = msg.content
    # 产出代码（模拟）
    time.sleep(0.1)
    me.send("tester", f"代码已实现，基于：{design[:40]}...", summary="请求测试")
    # 等待 tester 反馈
    msg = me.recv()
    if msg and "Bug" in msg.content:
        time.sleep(0.05)
        me.send("tester", "已修复", summary="修复")
        msg = me.recv()
    me.send("main", "开发工作完成", summary="完成")


def tester_behave(me: Member) -> None:
    # 等待 developer
    msg = me.recv()
    if msg is None or msg.msg_type == "shutdown_request":
        return
    time.sleep(0.1)
    # 第一次发现 Bug
    me.send("developer", "发现 Bug：浮点精度", summary="测试反馈")
    # 等待修复
    msg = me.recv()
    if msg:
        me.send("developer", "测试通过", summary="通过")
    me.send("main", "测试完成，全部通过", summary="通过")


def demo() -> None:
    received_main_messages = []

    def on_main(msg: Message) -> None:
        received_main_messages.append(msg)
        print(f"[main 收到] {msg.from_}: {msg.content}")

    team = Team("proto-p1-simulated", main_handler=on_main)
    team.spawn("architect", "架构师", architect_behave)
    team.spawn("developer", "开发者", developer_behave)
    team.spawn("tester",    "测试",   tester_behave)

    # 启动对话
    time.sleep(0.05)
    team.deliver(Message(from_="main", to="architect",
                         content="请开始计算器接口设计", summary="启动"))

    time.sleep(2.0)
    team.shutdown_all()

    # 统计
    print("\n========== 统计 ==========")
    print(f"总消息数：{len(team.message_log)}")
    p2p_count = sum(1 for m in team.message_log
                    if m.from_ != "main" and m.to != "main" and m.from_ != "system")
    print(f"P2P 消息数（非 main 参与）：{p2p_count}")
    main_msgs = sum(1 for m in team.message_log if m.to == "main")
    print(f"发给 main 的消息数：{main_msgs}")

    print("\n========== 完整消息流 ==========")
    for m in team.message_log:
        print(f"  {m.from_:>10} → {m.to:<10} [{m.summary or '-'}] {m.content[:50]}")


if __name__ == "__main__":
    demo()
