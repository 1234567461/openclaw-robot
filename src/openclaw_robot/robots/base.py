"""物理机器人抽象基类。

参考 OpenClaw-Robotics 的适配器设计：定义统一接口，
让 Agent 通过同一套工具控制不同厂商的机器人。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class Pose:
    """机器人位姿。"""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0  # 朝向角（度）


class Robot(abc.ABC):
    """所有物理机器人的统一接口。

    子类（Unitree/ANYmal 等）实现具体通信协议。
    Agent 通过这些方法控制机器人，无需关心底层 SDK。
    """

    name: str = "base"

    @abc.abstractmethod
    def move(self, vx: float, vy: float, vrot: float, duration: float = 1.0) -> None:
        """以 (vx, vy, vrot) 速度运动 duration 秒。"""

    @abc.abstractmethod
    def pose(self) -> Pose:
        """返回当前位姿。"""

    @abc.abstractmethod
    def sensors(self) -> dict[str, Any]:
        """返回传感器读数（IMU/关节/电池等），结构由子类定义。"""

    def stop(self) -> None:
        """急停。默认实现：发零速度。"""
        self.move(0, 0, 0, 0)

    def slam(self) -> dict[str, Any]:
        """返回 SLAM 地图/位姿数据（若支持）。"""
        return {"supported": False}
