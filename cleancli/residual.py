"""
CleanCLI - 残留文件识别模块 v2.0
扫描已安装程序，识别已卸载或废弃程序的残留文件、注册表项及配置
新增：孤儿服务检测、计划任务检测、启动项检测、更全面的AppData扫描
"""

import os
import winreg
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional


@dataclass
class InstalledProgram:
    """已安装程序信息"""
    name: str
    version: str = ""
    publisher: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    registry_key: str = ""


@dataclass
class ResidualItem:
    """残留项目"""
    path: str
    size: int  # bytes
    residual_type: str  # file, dir, registry, shortcut, service, task, startup
    associated_program: str
    description: str = ""
    risk_level: str = "low"  # low, medium, high


@dataclass
class ResidualScanResult:
    """残留扫描结果"""
    installed_programs: List[InstalledProgram] = field(default_factory=list)
    residual_items: List[ResidualItem] = field(default_factory=list)
    total_size: int = 0
    errors: List[str] = field(default_factory=list)


def _get_dir_size(path: str) -> int:
    """获取目录大小"""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


class ResidualScanner:
    """残留文件扫描器"""

    UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    INSTALL_DIRS = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files")),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Programs"),
    ]

    COMMON_RESIDUAL_DIRS = [
        (os.path.join(os.environ.get("APPDATA", ""), ""), "AppData/Roaming"),
        (os.path.join(os.environ.get("LOCALAPPDATA", ""), ""), "AppData/Local"),
        (os.path.join(os.environ.get("ProgramData", r"C:\ProgramData")), "ProgramData"),
    ]

    SYSTEM_DIRS = {
        "microsoft", "windows", "google", "mozilla", "intel", "nvidia",
        "amd", "realtek", "common files", "internet explorer",
        "windows defender", "windows mail", "windows media player",
        "windows nt", "windows photo viewer", "windows portable devices",
        "windows sidebar", "windowspowershell", "packages", "connecteddevicesplatform",
        "temp", "temporary internet files", "crashdumps", "thumb",
    }

    SYSTEM_PUBLISHERS = {
        "microsoft corporation", "microsoft", "windows",
    }

    def __init__(self):
        self.user_profile = os.environ.get("USERPROFILE", "")
        self.local_appdata = os.environ.get("LOCALAPPDATA", "")
        self.appdata = os.environ.get("APPDATA", "")
        self.program_data = os.environ.get("ProgramData", r"C:\ProgramData")

    def scan_all(self) -> ResidualScanResult:
        """执行完整残留扫描"""
        result = ResidualScanResult()

        self._scan_installed_programs(result)
        self._scan_residual_files(result)
        self._scan_residual_registry(result)
        self._scan_orphan_shortcuts(result)
        self._scan_orphan_services(result)
        self._scan_orphan_tasks(result)
        self._scan_startup_entries(result)

        return result

    def _scan_installed_programs(self, result: ResidualScanResult):
        """扫描已安装程序"""
        installed = {}
        for hkey, subkey_path in self.UNINSTALL_KEYS:
            try:
                key = winreg.OpenKey(hkey, subkey_path)
            except (OSError, FileNotFoundError):
                continue
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                    name = self._reg_query_value(subkey, "DisplayName")
                    if not name:
                        continue
                    program = InstalledProgram(
                        name=name,
                        version=self._reg_query_value(subkey, "DisplayVersion"),
                        publisher=self._reg_query_value(subkey, "Publisher"),
                        install_location=self._reg_query_value(subkey, "InstallLocation"),
                        uninstall_string=self._reg_query_value(subkey, "UninstallString"),
                        registry_key=f"{subkey_path}\\{subkey_name}",
                    )
                    key_str = f"{name}|{program.version}|{program.publisher}"
                    if key_str not in installed:
                        installed[key_str] = program
                    winreg.CloseKey(subkey)
                except (OSError, WindowsError):
                    pass
            try:
                winreg.CloseKey(key)
            except (OSError, WindowsError):
                pass
        result.installed_programs = list(installed.values())

    def _scan_residual_files(self, result: ResidualScanResult):
        """扫描残留文件目录"""
        known_paths: Set[str] = set()
        known_names: Set[str] = set()
        for prog in result.installed_programs:
            if prog.install_location and os.path.isdir(prog.install_location):
                known_paths.add(os.path.normcase(os.path.normpath(prog.install_location)))
            if prog.name:
                known_names.add(prog.name.lower().split()[0])

        # 扫描安装目录
        for install_dir in self.INSTALL_DIRS:
            if not os.path.isdir(install_dir):
                continue
            try:
                for entry in os.scandir(install_dir):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    dir_name_lower = entry.name.lower()
                    if dir_name_lower in self.SYSTEM_DIRS:
                        continue
                    norm_path = os.path.normcase(os.path.normpath(entry.path))
                    is_installed = any(
                        norm_path.startswith(k) or k.startswith(norm_path) for k in known_paths
                    )
                    if not is_installed:
                        size = _get_dir_size(entry.path)
                        if size > 0:
                            result.residual_items.append(ResidualItem(
                                path=entry.path, size=size, residual_type="dir",
                                associated_program=entry.name,
                                description=f"安装目录残留 ({install_dir})",
                                risk_level="medium",
                            ))
                            result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描 {install_dir} 失败: {e}")

        # 扫描AppData
        for base_dir, label in self.COMMON_RESIDUAL_DIRS:
            if not os.path.isdir(base_dir):
                continue
            try:
                for entry in os.scandir(base_dir):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    dir_name_lower = entry.name.lower()
                    if dir_name_lower in self.SYSTEM_DIRS:
                        continue
                    is_associated = False
                    for name in known_names:
                        if name and len(name) > 2 and name in dir_name_lower:
                            is_associated = True
                            break
                    if not is_associated and self._looks_like_program_residual(entry.path):
                        size = _get_dir_size(entry.path)
                        if size > 0:
                            result.residual_items.append(ResidualItem(
                                path=entry.path, size=size, residual_type="dir",
                                associated_program=entry.name,
                                description=f"应用数据残留 ({label})",
                                risk_level="low",
                            ))
                            result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描 {base_dir} 失败: {e}")

    def _scan_residual_registry(self, result: ResidualScanResult):
        """扫描残留注册表项"""
        for hkey, subkey_path in self.UNINSTALL_KEYS:
            try:
                key = winreg.OpenKey(hkey, subkey_path)
            except (OSError, FileNotFoundError):
                continue
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    subkey = winreg.OpenKey(key, subkey_name)
                    name = self._reg_query_value(subkey, "DisplayName")
                    install_loc = self._reg_query_value(subkey, "InstallLocation")
                    winreg.CloseKey(subkey)
                    if name and install_loc and install_loc and not os.path.isdir(install_loc):
                        result.residual_items.append(ResidualItem(
                            path=f"HKLM\\{subkey_path}\\{subkey_name}",
                            size=0, residual_type="registry", associated_program=name,
                            description=f"无效卸载项 (路径不存在: {install_loc})",
                            risk_level="low",
                        ))
                except (OSError, WindowsError):
                    pass
            try:
                winreg.CloseKey(key)
            except (OSError, WindowsError):
                pass

    def _scan_orphan_shortcuts(self, result: ResidualScanResult):
        """扫描孤立快捷方式"""
        shortcut_dirs = [
            os.path.join(self.appdata, "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(self.program_data, "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(self.user_profile, "Desktop"),
        ]
        for shortcut_dir in shortcut_dirs:
            if not os.path.isdir(shortcut_dir):
                continue
            try:
                for root, _, files in os.walk(shortcut_dir):
                    for f in files:
                        if f.lower().endswith(".lnk"):
                            lnk_path = os.path.join(root, f)
                            target = self._resolve_shortcut_target(lnk_path)
                            if target and not os.path.exists(target):
                                try:
                                    size = os.path.getsize(lnk_path)
                                except (OSError, PermissionError):
                                    size = 0
                                result.residual_items.append(ResidualItem(
                                    path=lnk_path, size=size, residual_type="shortcut",
                                    associated_program=f.replace(".lnk", ""),
                                    description=f"孤立快捷方式 -> {target}",
                                    risk_level="low",
                                ))
                                result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描快捷方式 {shortcut_dir} 失败: {e}")

    def _scan_orphan_services(self, result: ResidualScanResult):
        """扫描孤儿Windows服务（指向不存在的可执行文件）"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services"
            )
        except (OSError, FileNotFoundError):
            return

        i = 0
        while True:
            try:
                service_name = winreg.EnumKey(key, i)
                i += 1
            except OSError:
                break

            try:
                svc_key = winreg.OpenKey(key, service_name)
                image_path = self._reg_query_value(svc_key, "ImagePath")
                display_name = self._reg_query_value(svc_key, "DisplayName")
                start_type = self._reg_query_value(svc_key, "Start")
                winreg.CloseKey(svc_key)

                if not image_path:
                    continue

                # 提取可执行文件路径
                exe_path = image_path.strip('"').split()[0] if image_path else ""
                # 展开环境变量
                exe_path = os.path.expandvars(exe_path)

                if exe_path and not os.path.exists(exe_path):
                    # 排除系统服务
                    if "\\system32\\" in exe_path.lower() or "\\syswow64\\" in exe_path.lower():
                        continue
                    svc_display = display_name or service_name
                    result.residual_items.append(ResidualItem(
                        path=f"Service: {service_name}",
                        size=0, residual_type="service",
                        associated_program=svc_display,
                        description=f"孤儿服务 -> {exe_path}",
                        risk_level="medium",
                    ))
            except (OSError, WindowsError):
                pass

        try:
            winreg.CloseKey(key)
        except (OSError, WindowsError):
            pass

    def _scan_orphan_tasks(self, result: ResidualScanResult):
        """扫描孤儿计划任务（指向不存在的可执行文件）"""
        try:
            tasks_dir = os.path.join(self.windir, "System32", "Tasks")
            if not os.path.isdir(tasks_dir):
                return
            self.windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
        except Exception:
            return

        self.windir = os.environ.get("SYSTEMROOT", r"C:\Windows")
        tasks_dir = os.path.join(self.windir, "System32", "Tasks")
        if not os.path.isdir(tasks_dir):
            return

        # 跳过 Microsoft 和 Windows 系统任务
        skip_prefixes = {"Microsoft", "Windows", "MicrosoftEdge", "Google", "Opera"}

        try:
            for root, dirs, files in os.walk(tasks_dir):
                # 跳过系统任务目录
                rel = os.path.relpath(root, tasks_dir)
                first_part = rel.split(os.sep)[0] if os.sep in rel else rel
                if first_part in skip_prefixes:
                    dirs.clear()
                    continue

                for f in files:
                    task_path = os.path.join(root, f)
                    try:
                        tree = ET.parse(task_path)
                        ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
                        # 查找 Exec 节点中的 Command
                        for exec_elem in tree.iter():
                            if exec_elem.tag.endswith("}Command") or exec_elem.tag == "Command":
                                cmd = exec_elem.text
                                if cmd:
                                    cmd = os.path.expandvars(cmd.strip())
                                    if cmd and not os.path.exists(cmd) and not cmd.startswith(("cmd", "powershell", "wscript", "cscript")):
                                        task_name = os.path.relpath(task_path, tasks_dir)
                                        result.residual_items.append(ResidualItem(
                                            path=f"Task: {task_name}",
                                            size=0, residual_type="task",
                                            associated_program=f.replace(".xml", ""),
                                            description=f"孤儿计划任务 -> {cmd}",
                                            risk_level="low",
                                        ))
                                break
                    except (ET.ParseError, OSError, PermissionError):
                        pass
        except (OSError, PermissionError) as e:
            result.errors.append(f"扫描计划任务失败: {e}")

    def _scan_startup_entries(self, result: ResidualScanResult):
        """扫描启动项（指向不存在的可执行文件）"""
        startup_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hkey, key_path in startup_keys:
            try:
                key = winreg.OpenKey(hkey, key_path)
            except (OSError, FileNotFoundError):
                continue
            i = 0
            while True:
                try:
                    value_name, value_data, _ = winreg.EnumValue(key, i)
                    i += 1
                except OSError:
                    break
                try:
                    cmd = str(value_data).strip().strip('"')
                    # 提取可执行文件路径
                    exe = cmd.split()[0] if cmd else ""
                    exe = os.path.expandvars(exe)
                    if exe and not os.path.exists(exe):
                        result.residual_items.append(ResidualItem(
                            path=f"Startup: {value_name}",
                            size=0, residual_type="startup",
                            associated_program=value_name,
                            description=f"孤儿启动项 -> {exe}",
                            risk_level="low",
                        ))
                except (OSError, WindowsError):
                    pass
            try:
                winreg.CloseKey(key)
            except (OSError, WindowsError):
                pass

    def _looks_like_program_residual(self, path: str) -> bool:
        """判断目录是否看起来像程序残留"""
        try:
            entries = list(os.scandir(path))
            entry_names = {e.name.lower() for e in entries}
            program_indicators = {
                "config", "settings", "data", "cache", "logs",
                "log", "temp", "crashdumps", "preferences",
            }
            has_executables = any(
                e.name.lower().endswith(('.exe', '.dll', '.sys'))
                for e in entries if e.is_file()
            )
            has_config = any(
                e.name.lower().endswith(('.ini', '.cfg', '.conf', '.json', '.xml', '.yaml'))
                for e in entries if e.is_file()
            )
            if len(entries) < 2:
                return False
            return has_executables or has_config or bool(entry_names & program_indicators)
        except (OSError, PermissionError):
            return False

    def _resolve_shortcut_target(self, lnk_path: str) -> Optional[str]:
        """解析快捷方式目标"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            return shortcut.Targetpath
        except Exception:
            return None

    @staticmethod
    def _reg_query_value(key, value_name: str) -> str:
        """读取注册表值"""
        try:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value) if value else ""
        except (OSError, WindowsError):
            return ""


def clean_residual_item(item: ResidualItem) -> bool:
    """清理单个残留项目"""
    try:
        if item.residual_type in ("file", "shortcut"):
            os.remove(item.path)
            return True
        elif item.residual_type == "dir":
            import shutil
            shutil.rmtree(item.path, ignore_errors=True)
            return True
        elif item.residual_type == "registry":
            return _delete_registry_key(item.path)
        elif item.residual_type in ("service", "task", "startup"):
            return _clean_system_entry(item)
    except (OSError, PermissionError):
        pass
    return False


def _delete_registry_key(key_path: str) -> bool:
    """删除注册表项"""
    try:
        if key_path.startswith("HKLM\\"):
            hkey = winreg.HKEY_LOCAL_MACHINE
            subkey = key_path[5:]
        elif key_path.startswith("HKCU\\"):
            hkey = winreg.HKEY_CURRENT_USER
            subkey = key_path[5:]
        else:
            return False
        winreg.DeleteKey(hkey, subkey)
        return True
    except (OSError, WindowsError):
        return False


def _clean_system_entry(item: ResidualItem) -> bool:
    """清理系统条目（服务/计划任务/启动项）"""
    try:
        if item.residual_type == "service":
            svc_name = item.path.replace("Service: ", "")
            subprocess.run(
                ["sc", "delete", svc_name],
                capture_output=True, timeout=10,
            )
            return True
        elif item.residual_type == "task":
            task_name = item.path.replace("Task: ", "")
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                capture_output=True, timeout=10,
            )
            return True
        elif item.residual_type == "startup":
            entry_name = item.path.replace("Startup: ", "")
            for hkey, key_path in [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
            ]:
                try:
                    key = winreg.OpenKey(hkey, key_path, 0, winreg.KEY_ALL_ACCESS)
                    winreg.DeleteValue(key, entry_name)
                    winreg.CloseKey(key)
                    return True
                except (OSError, WindowsError):
                    pass
    except Exception:
        pass
    return False
