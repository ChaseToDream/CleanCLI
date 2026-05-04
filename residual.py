"""
CleanCLI - 残留文件识别模块
扫描已安装程序，识别已卸载或废弃程序的残留文件、注册表项及配置
"""

import os
import winreg
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
    residual_type: str  # file, dir, registry, shortcut
    associated_program: str  # 关联的程序名
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

    # 注册表中存储已安装程序的位置
    UNINSTALL_KEYS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    # 常见安装目录
    INSTALL_DIRS = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files")),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Programs"),
    ]

    # 常见残留目录模式
    COMMON_RESIDUAL_DIRS = [
        (os.path.join(os.environ.get("APPDATA", ""), ""), "AppData/Roaming"),
        (os.path.join(os.environ.get("LOCALAPPDATA", ""), ""), "AppData/Local"),
        (os.path.join(os.environ.get("ProgramData", r"C:\ProgramData")), "ProgramData"),
    ]

    # 忽略的系统目录
    SYSTEM_DIRS = {
        "microsoft", "windows", "google", "mozilla", "intel", "nvidia",
        "amd", "realtek", "common files", "internet explorer",
        "windows defender", "windows mail", "windows media player",
        "windows nt", "windows photo viewer", "windows portable devices",
        "windows sidebar", "windowspowershell",
    }

    # 忽略的注册表发布者
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

        # 1. 获取已安装程序列表
        self._scan_installed_programs(result)

        # 2. 扫描残留文件
        self._scan_residual_files(result)

        # 3. 扫描残留注册表项
        self._scan_residual_registry(result)

        # 4. 扫描孤立快捷方式
        self._scan_orphan_shortcuts(result)

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

                    # 去重
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
        # 收集所有已知安装路径
        known_paths: Set[str] = set()
        for prog in result.installed_programs:
            if prog.install_location and os.path.isdir(prog.install_location):
                known_paths.add(os.path.normcase(os.path.normpath(prog.install_location)))

        # 扫描常见安装目录
        for install_dir in self.INSTALL_DIRS:
            if not os.path.isdir(install_dir):
                continue
            try:
                for entry in os.scandir(install_dir):
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    dir_name_lower = entry.name.lower()

                    # 跳过系统目录
                    if dir_name_lower in self.SYSTEM_DIRS:
                        continue

                    norm_path = os.path.normcase(os.path.normpath(entry.path))

                    # 检查是否与已安装程序匹配
                    is_installed = False
                    for known in known_paths:
                        if norm_path.startswith(known) or known.startswith(norm_path):
                            is_installed = True
                            break

                    if not is_installed:
                        size = _get_dir_size(entry.path)
                        if size > 0:
                            result.residual_items.append(ResidualItem(
                                path=entry.path,
                                size=size,
                                residual_type="dir",
                                associated_program=entry.name,
                                description=f"安装目录残留 ({install_dir})",
                                risk_level="medium",
                            ))
                            result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描 {install_dir} 失败: {e}")

        # 扫描AppData中的程序数据目录
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

                    # 检查是否与已安装程序匹配
                    is_associated = False
                    for prog in result.installed_programs:
                        prog_name_lower = prog.name.lower().split()[0] if prog.name else ""
                        if prog_name_lower and len(prog_name_lower) > 2 and prog_name_lower in dir_name_lower:
                            is_associated = True
                            break

                    if not is_associated:
                        # 进一步检查：目录是否看起来像程序残留
                        if self._looks_like_program_residual(entry.path):
                            size = _get_dir_size(entry.path)
                            if size > 0:
                                result.residual_items.append(ResidualItem(
                                    path=entry.path,
                                    size=size,
                                    residual_type="dir",
                                    associated_program=entry.name,
                                    description=f"应用数据残留 ({label})",
                                    risk_level="low",
                                ))
                                result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描 {base_dir} 失败: {e}")

    def _scan_residual_registry(self, result: ResidualScanResult):
        """扫描残留注册表项"""
        # 检查卸载注册表中是否有无效条目
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

                    if name and install_loc and not os.path.isdir(install_loc):
                        result.residual_items.append(ResidualItem(
                            path=f"HKLM\\{subkey_path}\\{subkey_name}",
                            size=0,
                            residual_type="registry",
                            associated_program=name,
                            description=f"无效的卸载注册表项 (安装路径不存在: {install_loc})",
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
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        ]

        for shortcut_dir in shortcut_dirs:
            if not os.path.isdir(shortcut_dir):
                continue
            try:
                for root, _, files in os.walk(shortcut_dir):
                    for f in files:
                        if f.lower().endswith(".lnk"):
                            lnk_path = os.path.join(root, f)
                            # 检查快捷方式目标是否存在
                            target = self._resolve_shortcut_target(lnk_path)
                            if target and not os.path.exists(target):
                                try:
                                    size = os.path.getsize(lnk_path)
                                except (OSError, PermissionError):
                                    size = 0
                                result.residual_items.append(ResidualItem(
                                    path=lnk_path,
                                    size=size,
                                    residual_type="shortcut",
                                    associated_program=f.replace(".lnk", ""),
                                    description=f"孤立快捷方式 -> {target}",
                                    risk_level="low",
                                ))
                                result.total_size += size
            except (OSError, PermissionError) as e:
                result.errors.append(f"扫描快捷方式 {shortcut_dir} 失败: {e}")

    def _looks_like_program_residual(self, path: str) -> bool:
        """判断目录是否看起来像程序残留"""
        try:
            entries = list(os.scandir(path))
            entry_names = {e.name.lower() for e in entries}

            # 程序残留目录的典型特征
            program_indicators = {
                "config", "settings", "data", "cache", "logs",
                "log", "temp", "cache", "crashdumps",
            }
            # 包含可执行文件或DLL
            has_executables = any(
                e.name.lower().endswith(('.exe', '.dll', '.sys'))
                for e in entries if e.is_file()
            )

            # 包含配置文件
            has_config = any(
                e.name.lower().endswith(('.ini', '.cfg', '.conf', '.json', '.xml', '.yaml'))
                for e in entries if e.is_file()
            )

            # 如果目录很空或只有少数文件，可能不是残留
            if len(entries) < 2:
                return False

            return has_executables or has_config or bool(entry_names & program_indicators)
        except (OSError, PermissionError):
            return False

    def _resolve_shortcut_target(self, lnk_path: str) -> Optional[str]:
        """解析快捷方式目标（使用COM）"""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            return shortcut.Targetpath
        except Exception:
            # 回退：尝试读取二进制内容中的路径
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
        if item.residual_type == "file":
            os.remove(item.path)
            return True
        elif item.residual_type == "dir":
            import shutil
            shutil.rmtree(item.path, ignore_errors=True)
            return True
        elif item.residual_type == "registry":
            return _delete_registry_key(item.path)
        elif item.residual_type == "shortcut":
            os.remove(item.path)
            return True
    except (OSError, PermissionError):
        pass
    return False


def _delete_registry_key(key_path: str) -> bool:
    """删除注册表项"""
    try:
        # 解析路径
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
