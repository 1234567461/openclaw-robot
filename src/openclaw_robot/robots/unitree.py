"""Unitree GO1/GO2 适配器：基于 unitree_sdk2py 的实际运动控制。

参考：OpenClaw-Robotics 的 unitree_robot_skill。
SDK: https://github.com/unitreerobotics/unitree_sdk2_python

需先安装：pip install unitree_sdk2_python
机器人需在共同网络（GO2 默认 192.168.123.161）。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .base import Pose, Robot

log = logging.getLogger(__name__)


class UnitreeRobot(Robot):
    """Unitree 四足机器人适配器。

    通过环境变量 UNITREE_IP 配置机器人 IP（GO2 默认 192.168.123.161）。
    未装 SDK 或未连机器人时自动降级为桩模式（只记日志）。
    """

    name = "unitree"

    def __init__(self, ip: str = "") -> None:
        import os

        self.ip = ip or os.getenv("UNITREE_IP", "")
        self._sport: Any = None
        self._connected = False
        self._last_pose = Pose()

    # ---------- 连接 ----------

    def _connect(self) -> bool:
        """连接机器人 SportClient。返回是否成功。"""
        if self._connected:
            return True
        if not self.ip:
            log.warning("UNITREE_IP 未设置，Unitree 运行在桩模式")
            return False
        try:
            from unitree_sdk2py.core.channel import ChannelFactory  # type: ignore
            from unitree_sdk2py.go2.sport.client import SportClient  # type: ignore

            ChannelFactory().Init(0, self.ip)
            self._sport = SportClient()
            self._sport.SetTimeout(10.0)
            self._sport.Init()
            self._connected = True
            log.info("Unitree 已连接 IP=%s", self.ip)
            return True
        except ImportError:
            log.warning("unitree_sdk2_python 未安装，Unitree 运动指令仅为日志（桩）")
            return False
        except Exception as e:  # noqa: BLE001
            log.error("Unitree 连接失败: %s", e)
            return False

    # ---------- 基础运动 ----------

    def move(self, vx: float, vy: float, vrot: float, duration: float = 1.0) -> None:
        """以 (vx, vy, vrot) 速度运动 duration 秒后停止。

        vx: 前后（+前）
        vy: 左右（+左）
        vrot: 旋转（+左转）
        """
        if not self._connect():
            log.info("[Unitree 桩] move vx=%.2f vy=%.2f vrot=%.2f t=%.1f", vx, vy, vrot, duration)
            return

        try:
            self._sport.Move(vx, vy, vrot)
            time.sleep(duration)
            self._sport.Move(0, 0, 0)  # 停止
        except Exception as e:  # noqa: BLE001
            log.error("Unitree 运动失败: %s", e)

    def stand_up(self) -> None:
        """恢复站立姿态。"""
        if not self._connect():
            log.info("[Unitree 桩] stand_up")
            return
        try:
            self._sport.RecoveryStand()
        except Exception as e:  # noqa: BLE001
            log.error("Unitree stand_up 失败: %s", e)

    def lie_down(self) -> None:
        """趴下。"""
        if not self._connect():
            log.info("[Unitree 桩] lie_down")
            return
        try:
            self._sport.StandDown()
        except Exception as e:  # noqa: BLE001
            log.error("Unitree lie_down 失败: %s", e)

    def stop(self) -> None:
        """急停。"""
        if self._connected and self._sport:
            try:
                self._sport.Move(0, 0, 0)
                self._sport.StopMove()
            except Exception:  # noqa: BLE001
                pass
        else:
            log.info("[Unitree 桩] stop")

    # ---------- 状态查询 ----------

    def pose(self) -> Pose:
        """返回当前位姿（来自机器人状态）。"""
        if not self._connect():
            return self._last_pose
        try:
            state = self._sport.GetState()
            # unitree_sdk2py 的 RobotState 包含位置/速度/姿态
            pos = getattr(state, "position", None) or getattr(state, "Position", None)
            rpy = getattr(state, "rpy", None) or getattr(state, "RPY", None)
            if pos and rpy:
                self._last_pose = Pose(
                    x=getattr(pos, "x", 0.0),
                    y=getattr(pos, "y", 0.0),
                    z=getattr(pos, "z", 0.0),
                    yaw=getattr(rpy, "z", 0.0) if hasattr(rpy, "z") else getattr(rpy, "yaw", 0.0),
                )
        except Exception as e:  # noqa: BLE001
            log.debug("获取位姿失败: %s", e)
        return self._last_pose

    def sensors(self) -> dict[str, Any]:
        """返回传感器读数：IMU + 足端 + 电池。"""
        if not self._connect():
            return {"note": "SDK 未连接，无传感器数据"}
        try:
            state = self._sport.GetState()
            return {
                "imu": {
                    "rpy": _safe_attr(state, "rpy"),
                    "gyroscope": _safe_attr(state, "gyroscope"),
                    "accelerometer": _safe_attr(state, "accelerometer"),
                },
                "foot_force": _safe_attr(state, "foot_force"),
                "position": _safe_attr(state, "position"),
                "velocity": _safe_attr(state, "velocity"),
            }
        except Exception as e:  # noqa: BLE001
            log.debug("获取传感器失败: %s", e)
            return {"error": str(e)}

    def slam(self) -> dict[str, Any]:
        """Unitree GO2 自带激光雷达 SLAM（若启用）。"""
        if not self._connect():
            return {"supported": False}
        try:
            state = self._sport.GetState()
            return {
                "supported": True,
                "position": _safe_attr(state, "position"),
                "velocity": _safe_attr(state, "velocity"),
            }
        except Exception as e:  # noqa: BLE001
            return {"supported": False, "error": str(e)}


def _safe_attr(obj: Any, name: str) -> Any:
    """安全读取属性，不存在时返回 None。"""
    return getattr(obj, name, None) or getattr(obj, name.capitalize(), None)
