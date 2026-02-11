"""
系统监控 MCP 工具
提供系统资源使用情况监控功能
"""

from typing import Dict, Any
from src.mcp.base_tool import BaseTool


class GetSystemResourceTool(BaseTool):
    """
    获取系统资源使用情况工具
    返回 CPU、内存、磁盘等系统资源的使用情况
    """

    name = "get_system_resource"
    description = "获取当前系统资源使用情况，包括 CPU 使用率、内存使用情况、磁盘使用情况等"
    parameters = {
        "include_processes": {
            "type": "boolean",
            "description": "是否包含进程信息（进程数、僵尸进程等）",
            "required": False
        }
    }

    async def execute(self, include_processes: bool = False) -> Dict[str, Any]:
        """
        执行获取系统资源信息

        Args:
            include_processes: 是否包含进程信息

        Returns:
            dict: 系统资源信息
        """
        try:
            import psutil
        except ImportError:
            return {
                "error": "psutil 库未安装，请运行: pip install psutil",
                "cpu_percent": None,
                "memory": None,
                "disk": None,
                "processes": None
            }

        result = {
            "cpu": self._get_cpu_info(),
            "memory": self._get_memory_info(),
            "disk": self._get_disk_info(),
        }

        if include_processes:
            result["processes"] = self._get_process_info()

        return result

    def _get_cpu_info(self) -> Dict[str, Any]:
        """获取 CPU 信息（适配树莓派 ARM 架构）"""
        import psutil
        import platform

        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        cpu_count_logical = psutil.cpu_count(logical=True)

        cpu_freq = psutil.cpu_freq()
        freq_info = {}
        if cpu_freq and cpu_freq.current > 0:
            freq_info = {
                "current_mhz": round(cpu_freq.current, 2),
                "min_mhz": cpu_freq.min if cpu_freq.min else 0,
                "max_mhz": cpu_freq.max if cpu_freq.max else 0,
            }
        else:
            freq_info = {"note": "CPU 频率信息不可用（ARM 架构常见情况）"}

        cpu_times = psutil.cpu_times()
        times_info = {}
        if cpu_times:
            times_info = {
                "user": round(cpu_times.user, 2),
                "system": round(cpu_times.system, 2),
                "idle": round(cpu_times.idle, 2),
            }

        load_avg = None
        try:
            load_avg = psutil.getloadavg()
        except (AttributeError, OSError):
            pass

        cpu_info = {
            "percent": round(cpu_percent, 2),
            "count_physical": cpu_count,
            "count_logical": cpu_count_logical,
            "architecture": platform.machine(),
            "frequency": freq_info,
            "times": times_info,
        }

        if load_avg:
            cpu_info["load_average"] = [round(x, 2) for x in load_avg]

        return cpu_info

    def _get_memory_info(self) -> Dict[str, Any]:
        """获取内存信息"""
        import psutil

        virtual_mem = psutil.virtual_memory()
        swap_mem = psutil.swap_memory()

        return {
            "virtual": {
                "total_mb": round(virtual_mem.total / 1024 / 1024, 2),
                "available_mb": round(virtual_mem.available / 1024 / 1024, 2),
                "used_mb": round(virtual_mem.used / 1024 / 1024, 2),
                "free_mb": round(virtual_mem.free / 1024 / 1024, 2),
                "percent": virtual_mem.percent,
            },
            "swap": {
                "total_mb": round(swap_mem.total / 1024 / 1024, 2),
                "used_mb": round(swap_mem.used / 1024 / 1024, 2),
                "free_mb": round(swap_mem.free / 1024 / 1024, 2),
                "percent": swap_mem.percent,
            },
        }

    def _get_disk_info(self) -> Dict[str, Any]:
        """获取磁盘信息（适配树莓派 ARM 架构）"""
        import psutil
        import os

        disk_info = {}

        try:
            disk_usage = psutil.disk_usage("/")
            disk_info["usage"] = {
                "mount_point": "/",
                "total_gb": round(disk_usage.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk_usage.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk_usage.free / 1024 / 1024 / 1024, 2),
                "percent": disk_usage.percent,
            }
        except (OSError, FileNotFoundError) as e:
            disk_info["usage"] = {"error": f"无法获取根分区信息: {str(e)}"}

        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                disk_info["io"] = {
                    "read_count": disk_io.read_count,
                    "write_count": disk_io.write_count,
                    "read_bytes_mb": round(disk_io.read_bytes / 1024 / 1024, 2),
                    "write_bytes_mb": round(disk_io.write_bytes / 1024 / 1024, 2),
                }
        except (OSError, AttributeError):
            disk_info["io"] = {"note": "磁盘 IO 统计不可用"}

        return disk_info

    def _get_process_info(self) -> Dict[str, Any]:
        """获取进程信息"""
        import psutil

        total_processes = len(psutil.pids())
        running = 0
        sleeping = 0
        zombie = 0

        for proc in psutil.process_iter(["status"]):
            try:
                status = proc.info["status"]
                if status == psutil.STATUS_RUNNING:
                    running += 1
                elif status == psutil.STATUS_SLEEPING:
                    sleeping += 1
                elif status == psutil.STATUS_ZOMBIE:
                    zombie += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "total": total_processes,
            "running": running,
            "sleeping": sleeping,
            "zombie": zombie,
        }


class GetNetworkInfoTool(BaseTool):
    """
    获取网络信息工具
    返回网络连接和接口信息
    """

    name = "get_network_info"
    description = "获取网络接口和连接信息"
    parameters = {}

    async def execute(self) -> Dict[str, Any]:
        """
        执行获取网络信息

        Returns:
            dict: 网络信息
        """
        try:
            import psutil
        except ImportError:
            return {
                "error": "psutil 库未安装，请运行: pip install psutil",
                "connections": None,
                "io_counters": None
            }

        connections = psutil.net_connections(kind="inet")
        conn_info = {
            "established": sum(1 for c in connections if c.status == "ESTABLISHED"),
            "listen": sum(1 for c in connections if c.status == "LISTEN"),
            "time_wait": sum(1 for c in connections if c.status == "TIME_WAIT"),
            "total": len(connections),
        }

        net_io = psutil.net_io_counters()
        io_info = {}
        if net_io:
            io_info = {
                "bytes_sent_mb": round(net_io.bytes_sent / 1024 / 1024, 2),
                "bytes_recv_mb": round(net_io.bytes_recv / 1024 / 1024, 2),
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }

        return {
            "connections": conn_info,
            "io_counters": io_info,
        }


class GetRaspberryPiInfoTool(BaseTool):
    """
    获取树莓派硬件信息工具
    返回 CPU 温度、电压、硬件型号等树莓派特有信息
    """

    name = "get_raspberry_pi_info"
    description = "获取树莓派硬件信息（CPU 温度、电压、硬件型号等），仅适用于树莓派设备"
    parameters = {}

    async def execute(self) -> Dict[str, Any]:
        """
        执行获取树莓派硬件信息

        Returns:
            dict: 树莓派硬件信息
        """
        import platform
        import os

        info = {
            "is_raspberry_pi": False,
            "platform": platform.machine(),
            "system": platform.system(),
        }

        try:
            vcgencmd_available = os.path.exists("/usr/bin/vcgencmd")

            if info["platform"] in ["aarch64", "armv7l", "armv6l"] or vcgencmd_available:
                info["is_raspberry_pi"] = True

                cpu_temp = self._get_cpu_temperature()
                if cpu_temp:
                    info["cpu_temperature_celsius"] = cpu_temp

                voltages = self._get_voltages()
                if voltages:
                    info["voltages"] = voltages

                hardware_info = self._get_hardware_info()
                if hardware_info:
                    info.update(hardware_info)

                throttling_status = self._get_throttling_status()
                if throttling_status:
                    info["throttling"] = throttling_status

            return info

        except Exception as e:
            return {
                "error": f"获取树莓派信息时出错: {str(e)}",
                "is_raspberry_pi": False,
                "platform": platform.machine(),
            }

    def _get_cpu_temperature(self) -> float:
        """获取 CPU 温度"""
        import os

        try:
            if os.path.exists("/usr/bin/vcgencmd"):
                import subprocess

                result = subprocess.run(
                    ["vcgencmd", "measure_temp"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    temp_str = result.stdout.strip()
                    temp_value = float(temp_str.split("=")[1].split("'")[0])
                    return round(temp_value, 2)
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass

        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_millidegrees = float(f.read().strip())
                return round(temp_millidegrees / 1000, 2)
        except (OSError, FileNotFoundError, ValueError):
            pass

        return None

    def _get_voltages(self) -> Dict[str, float]:
        """获取电压信息"""
        import os
        import subprocess

        voltages = {}

        try:
            if os.path.exists("/usr/bin/vcgencmd"):
                result = subprocess.run(
                    ["vcgencmd", "measure_volts"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    volt_str = result.stdout.strip()
                    volt_value = float(volt_str.split("=")[1].split("V")[0])
                    voltages["core_volts"] = round(volt_value, 3)
        except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass

        try:
            with open("/sys/class/power_supply/battery/voltage_now", "r") as f:
                voltage_uv = float(f.read().strip())
                voltages["battery_volts"] = round(voltage_uv / 1000000, 3)
        except (OSError, FileNotFoundError, ValueError):
            pass

        return voltages if voltages else None

    def _get_hardware_info(self) -> Dict[str, str]:
        """获取硬件信息"""
        import os
        import subprocess

        hardware = {}

        try:
            if os.path.exists("/usr/bin/vcgencmd"):
                result = subprocess.run(
                    ["vcgencmd", "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    hardware["vcgencmd_version"] = result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass

        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                    for line in cpuinfo.split("\n"):
                        if "Hardware" in line:
                            hardware["hardware_model"] = line.split(":")[1].strip()
                        elif "Revision" in line:
                            hardware["revision"] = line.split(":")[1].strip()
                        elif "Serial" in line:
                            hardware["serial"] = line.split(":")[1].strip()
        except (OSError, FileNotFoundError):
            pass

        return hardware if hardware else None

    def _get_throttling_status(self) -> Dict[str, Any]:
        """获取限流状态"""
        import os

        try:
            if os.path.exists("/sys/class/thermal/thermal_zone0/trip_point_0_temp"):
                with open("/sys/class/thermal/thermal_zone0/trip_point_0_temp", "r") as f:
                    trip_temp = int(f.read().strip())
                    return {"trip_point_celsius": round(trip_temp / 1000, 2)}
        except (OSError, FileNotFoundError, ValueError):
            pass

        return None


class GetBootTimeTool(BaseTool):
    """
    获取系统启动时间工具
    返回系统启动时间和运行时长
    """

    name = "get_boot_time"
    description = "获取系统启动时间和运行时长"
    parameters = {}

    async def execute(self) -> Dict[str, Any]:
        """
        执行获取启动时间

        Returns:
            dict: 启动时间信息
        """
        try:
            import psutil
            import datetime
        except ImportError:
            return {
                "error": "psutil 库未安装，请运行: pip install psutil",
                "boot_time": None,
                "uptime": None
            }

        boot_time = psutil.boot_time()
        boot_datetime = datetime.datetime.fromtimestamp(boot_time)
        now = datetime.datetime.now()
        uptime = now - boot_datetime

        uptime_seconds = uptime.total_seconds()
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        return {
            "boot_timestamp": boot_time,
            "boot_datetime": boot_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "uptime_seconds": int(uptime_seconds),
            "uptime_days": uptime_days,
            "uptime_hours": uptime_hours,
            "uptime_minutes": uptime_minutes,
            "uptime_human": f"{uptime_days}天 {uptime_hours}小时 {uptime_minutes}分钟",
        }
