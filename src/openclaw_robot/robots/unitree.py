"""Unitree GO1/GO2 适配器（桩，需装 SDK 后实现协议层）。

参考：OpenClaw-Robotics 的 unitree_robot_skill。
Unitree SDK 见 https://github.com/unitreerobotics/unitree_sdk2_python
"""

from __future__ import annotations

import logging
from typing import Any

from .base import Pose, Robot

log = logging.getLogger(__name__)


class UnitreeRobot(Robot):
    """Unitree 四足机器人适配器。

    通过环境变量 UNITREE_IP 配置机器人 IP。
    实际运动指令需安装 unitree_sdk2_python 后在 _client 中实现。
    """

    name = "unitree"

    def __init__(self, ip: str = "") -> None:
        import os

        self.ip = ip or os.getenv("UNITREE_IP", "")
        self._client: Any = None
        if self.ip:
            log.info("Unitree 适配器初始化，目标 IP=%s（SDK 未连接，运动指令为桩）", self.ip)

    def _connect(self) -> None:
        """连接机器人 SDK（需 pip install unitree_sdk2_python）。"""
        try:
            from unitree_sdk2py.core.channel import ChannelFactory  # type: ignore
            self._client = ChannelFactory()
            self._client.initialize(0, self.ip)
        except ImportError:
            log.warning("unitree_sdk2_python 未安装，Unitree 运动指令仅为日志输出")

    def move(self, vx: float, vy: float, vrot: float, duration: float = 1.0) -> None:
        if self._client is None:
            log.info("[Unitree 桩] move vx=%.2f vy=%.2f vrot=%.2f t=%.1f", vx, vy, vrot, duration)
            return
        # 实际实现：通过 sport_client 发布 HighLevel 运动指令
        raise NotImplementedError("实际运动指令待 SDK 接入后实现")

    def pose(self) -> Pose:
        if self._client is None:
            return Pose()
        raise NotImplementedError

    def sensors(self) -> dict[str, Any]:
        if self._client is None:
            return {"note": "SDK 未连接，无传感器数据"}
        raise NotImplementedError
