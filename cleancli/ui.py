"""
CleanCLI - 交互式CLI界面模块 v3.0
专业级终端UI：交互式主菜单、表格化扫描结果、仪表盘式报告、动画进度
"""

import os
import sys
import json
import time
import platform
import ctypes
from typing import List, Optional, Tuple
from dataclasses import dataclass

from cleancli.cleaner import ScanResult, CleanItem
from cleancli.residual import ResidualItem, ResidualScanResult


# ── ANSI 颜色与样式 ──────────────────────────────────────────

class C:
    """颜色与样式常量"""
    RST = "\033[0m"
    B   = "\033[1m"
    DIM = "\033[2m"
    U   = "\033[4m"
    REV = "\033[7m"

    BLK = "\033[30m"
    RED = "\033[31m"
    GRN = "\033[32m"
    YEL = "\033[33m"
    BLU = "\033[34m"
    MAG = "\033[35m"
    CYN = "\033[36m"
    WHT = "\033[37m"

    HRED = "\033[91m"
    HGRN = "\033[92m"
    HYEL = "\033[93m"
    HBLU = "\033[94m"
    HMAG = "\033[95m"
    HCYN = "\033[96m"
    HWHT = "\033[97m"

    BGRN = "\033[42m"
    BYEL = "\033[43m"
    BRED = "\033[41m"
    BCYN = "\033[46m"


def _init_terminal():
    """初始化终端：启用ANSI、设置UTF-8"""
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
        try:
            os.system("")
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.encoding != "utf-8":
                stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


_init_terminal()


# ── 工具函数 ──────────────────────────────────────────────────

W = 64  # 默认输出宽度

def fmt_size(b: int) -> str:
    """格式化文件大小"""
    if b <= 0:
        return "0 B"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {u}" if u != "B" else f"{int(b)} {u}"
        b /= 1024
    return f"{b:.1f} PB"

def fmt_age(days: int) -> str:
    if days <= 0:   return "不限"
    if days < 30:   return f"{days}天+"
    if days < 365:  return f"{days//30}个月+"
    return f"{days//365}年+"


# ── 底层输出 ──────────────────────────────────────────────────

def _p(text: str, end: str = "\n"):
    """安全输出"""
    try:
        print(text, end=end, flush=True)
    except (OSError, UnicodeEncodeError):
        pass

def _line(ch: str = "─", w: int = W, color: str = ""):
    _p(f"{color or C.DIM}{ch * w}{C.RST}")

def _blank(n: int = 1):
    _p("\n" * (n - 1), end="")


# ── 横幅与标题 ──────────────────────────────────────────────

def print_banner():
    _p(f"""
{C.CYN}{C.B}    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │     ██████╗██╗     ███████╗ █████╗ ███╗   ██╗        │
    │    ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║        │
    │    ██║     ██║     █████╗  ███████║██╔██╗ ██║        │
    │    ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║        │
    │    ╚██████╗███████╗███████╗██║  ██║██║ ╚████║        │
    │     ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝        │
    │                                                      │
    │       {C.HWHT}Windows System Cleaner  v3.1{C.CYN}                  │
    │       {C.DIM}Deep Scan · Smart Clean · Safe & Fast{C.CYN}          │
    │                                                      │
    └──────────────────────────────────────────────────────┘{C.RST}""")

def print_header(title: str, icon: str = ""):
    _blank()
    _p(f"{C.HCYN}{C.B}  {'━' * (W - 4)}{C.RST}")
    tag = f" {icon}" if icon else ""
    _p(f"{C.HCYN}{C.B}  {tag}  {title}{C.RST}")
    _p(f"{C.HCYN}{C.B}  {'━' * (W - 4)}{C.RST}")

def print_section(title: str, icon: str = ""):
    _blank()
    tag = f"{icon} " if icon else ""
    _p(f"  {C.HYEL}{C.B}{tag}{title}{C.RST}")
    _p(f"  {C.DIM}{'─' * 48}{C.RST}")

def _info_row(label: str, value: str, indent: int = 4):
    _p(f"{' ' * indent}{C.DIM}{label:<12}{C.RST} {value}")

def _ok(msg: str, indent: int = 4):
    _p(f"{' ' * indent}{C.HGRN}[OK]{C.RST} {msg}")

def _warn(msg: str, indent: int = 4):
    _p(f"{' ' * indent}{C.HYEL}[!!]{C.RST} {C.YEL}{msg}{C.RST}")

def _err(msg: str, indent: int = 4):
    _p(f"{' ' * indent}{C.HRED}[XX]{C.RST} {C.RED}{msg}{C.RST}")


# ── 进度条 ──────────────────────────────────────────────────

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

class Spinner:
    """终端旋转动画"""
    def __init__(self, msg: str = ""):
        self.msg = msg
        self._i = 0
        self._running = False

    def tick(self):
        frame = _SPINNER_FRAMES[self._i % len(_SPINNER_FRAMES)]
        _p(f"\r  {C.HCYN}{frame}{C.RST} {self.msg}", end="")
        self._i += 1

    def done(self, msg: str = ""):
        _p(f"\r  {C.HGRN}✓{C.RST} {msg or self.msg}                    ")

def print_progress(current: int, total: int, width: int = 36, prefix: str = ""):
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = f"{C.HGRN}{'█' * filled}{C.DIM}{'░' * (width - filled)}{C.RST}"
    pct_str = f"{pct*100:5.1f}%"
    cnt_str = f"({current}/{total})"
    _p(f"\r  {prefix} {bar} {C.B}{pct_str}{C.RST} {C.DIM}{cnt_str}{C.RST}", end="" if current < total else "\n", flush=True)


# ── 系统信息面板 ──────────────────────────────────────────────

def display_system_info(disk_info: List[dict], older_than: int = 0, min_size: int = 0):
    print_header("系统信息", icon="SYS")

    _info_row("操作系统", f"Windows {platform.version()}")
    _info_row("计算机名", platform.node())
    cpu = platform.processor()
    if cpu:
        cpu = cpu[:48] + "..." if len(cpu) > 48 else cpu
    _info_row("处理器", cpu or "N/A")

    if disk_info:
        print_section("磁盘空间", icon="DISK")
        for d in disk_info:
            pct = d["percent"]
            bw = 24
            filled = int(bw * pct / 100)
            if pct > 90:
                bar_color, tag = C.RED, " [满]"
            elif pct > 75:
                bar_color, tag = C.YEL, ""
            else:
                bar_color, tag = C.GRN, ""
            bar = f"{bar_color}{'▓' * filled}{C.DIM}{'░' * (bw - filled)}{C.RST}"
            _p(f"    {C.B}{d['drive']}:{C.RST} {bar}  "
                f"{C.B}{pct:>5.1f}%{C.RST}{tag}  "
                f"{C.DIM}{fmt_size(d['used'])} / {fmt_size(d['total'])}"
                f"  (可用 {fmt_size(d['free'])}){C.RST}")

    if older_than > 0 or min_size > 0:
        print_section("过滤规则", icon="FLT")
        if older_than > 0:
            _info_row("文件年龄", f"{C.HYEL}>{fmt_age(older_than)}{C.RST}")
        if min_size > 0:
            _info_row("最小大小", f"{C.HYEL}>={fmt_size(min_size)}{C.RST}")


# ── 扫描结果展示 ──────────────────────────────────────────────

def display_scan_results(results: List[ScanResult], show_detail: bool = True) -> Tuple[int, int]:
    total_items = 0
    total_size = 0

    print_header("扫描结果", icon="SCAN")

    active = [r for r in results if r.items and not r.error]
    if not active:
        _ok("未发现任何垃圾文件，系统很干净！")
        return 0, 0

    max_sz = max(r.total_size for r in active) if active else 1

    _p(f"  {C.DIM}{'类别':<20} {'数量':>6} {'大小':>10}  {'占比':>5}  条形图{C.RST}")
    _p(f"  {C.DIM}{'─' * 56}{C.RST}")

    for r in results:
        if r.error:
            _p(f"  {r.category:<20} {C.RED}{'ERR':>6}{C.RST} {C.DIM}{'--':>10}{C.RST}  {C.RED}[!]{C.RST}")
            continue
        if not r.items:
            if show_detail:
                _p(f"  {C.DIM}{r.category:<20} {'0':>6} {'0 B':>10}  {'--':>5}  --{C.RST}")
            continue

        cnt = len(r.items)
        sz = r.total_size
        total_items += cnt
        total_size += sz

        pct = (sz / max(max_sz, 1) * 100)

        if sz > 1024 * 1024 * 1024:
            sz_color = C.HRED
        elif sz > 100 * 1024 * 1024:
            sz_color = C.HYEL
        else:
            sz_color = C.HWHT

        bar_w = 14
        filled = int(bar_w * sz / max_sz) if max_sz > 0 else 0
        if sz > 1024 * 1024 * 1024:
            bar = f"{C.HRED}{'█' * filled}{C.DIM}{'░' * (bar_w - filled)}{C.RST}"
        elif sz > 100 * 1024 * 1024:
            bar = f"{C.HYEL}{'█' * filled}{C.DIM}{'░' * (bar_w - filled)}{C.RST}"
        else:
            bar = f"{C.HCYN}{'█' * filled}{C.DIM}{'░' * (bar_w - filled)}{C.RST}"

        pct_str = f"{pct:>4.1f}%" if pct >= 0.1 else f" {C.DIM}--{C.RST} "

        _p(f"  {C.HCYN}{r.category:<20}{C.RST} {C.B}{cnt:>6}{C.RST} {sz_color}{fmt_size(sz):>10}{C.RST}  {pct_str}  {bar}")

        if show_detail:
            for item in r.items[:3]:
                name = os.path.basename(item.path) if item.path else "?"
                if len(name) > 34:
                    name = name[:31] + "..."
                _p(f"    {C.DIM}  · {name}  {fmt_size(item.size)}{C.RST}")
            if cnt > 3:
                _p(f"    {C.DIM}  · ... 还有 {cnt - 3} 项{C.RST}")

    _blank()
    _p(f"  {C.HCYN}{'━' * 56}{C.RST}")
    _p(f"  {C.B}合计:{C.RST}  {C.HGRN}{C.B}{total_items}{C.RST} 个文件  "
        f"占用 {C.HYEL}{C.B}{fmt_size(total_size)}{C.RST}")
    _p(f"  {C.HCYN}{'━' * 56}{C.RST}")

    return total_items, total_size


def display_error_summary(errors: dict):
    """展示清理错误汇总"""
    if not errors:
        return
    print_section("错误详情", icon="ERR")
    err_labels = {
        "locked": ("文件被占用", C.HYEL),
        "permission": ("权限不足", C.HRED),
        "not_found": ("文件不存在", C.DIM),
        "unsafe_path": ("路径不安全", C.HYEL),
        "command_failed": ("命令执行失败", C.HYEL),
        "recycle_bin_failed": ("回收站清理失败", C.HYEL),
        "unknown": ("未知错误", C.HRED),
        "other": ("其他错误", C.HRED),
    }
    for err_type, count in errors.items():
        label, color = err_labels.get(err_type, (err_type, C.HWHT))
        _p(f"    {color}[{count}]{C.RST} {C.DIM}{label}{C.RST}")


def display_residual_results(result: ResidualScanResult, show_detail: bool = True):
    print_header("残留扫描", icon="SCAN")

    _info_row("已安装程序", f"{C.B}{len(result.installed_programs)}{C.RST} 个")

    if not result.residual_items:
        _ok("未发现残留文件，系统很干净！")
        return

    by_type = {}
    for item in result.residual_items:
        by_type.setdefault(item.residual_type, []).append(item)

    type_labels = {
        "dir": "残留目录", "file": "残留文件", "registry": "残留注册表",
        "shortcut": "孤立快捷方式", "service": "孤儿服务",
        "task": "孤儿计划任务", "startup": "孤儿启动项",
    }
    risk_style = {
        "low":   (C.HGRN, "低"),
        "medium":(C.HYEL, "中"),
        "high":  (C.HRED, "高"),
    }

    _p(f"  {C.DIM}{'类型':<14} {'数量':>6} {'大小':>12}  {'风险':<6}{C.RST}")
    _p(f"  {C.DIM}{'─' * 48}{C.RST}")

    for rtype, items in by_type.items():
        label = type_labels.get(rtype, rtype)
        cnt = len(items)
        sz = sum(i.size for i in items)
        # 取该类别最高风险
        risk_order = {"high": 3, "medium": 2, "low": 1}
        max_risk = max(items, key=lambda x: risk_order.get(x.risk_level, 0)).risk_level
        rc, rl = risk_style.get(max_risk, (C.WHT, "?"))

        _p(f"  {label:<14} {C.B}{cnt:>6}{C.RST} {fmt_size(sz):>12}  {rc}[{rl}]{C.RST}")

        if show_detail:
            for item in items[:4]:
                rc2, rl2 = risk_style.get(item.risk_level, (C.WHT, "?"))
                sz_str = fmt_size(item.size) if item.size > 0 else "--"
                _p(f"    {C.DIM}· {item.path}{C.RST}")
                _p(f"      {C.DIM}{item.associated_program} | {sz_str} | 风险{rc2}[{rl2}]{C.RST}")
            if cnt > 4:
                _p(f"    {C.DIM}· ... 还有 {cnt - 4} 项{C.RST}")

    _blank()
    _p(f"  {C.HCYN}{'━' * 50}{C.RST}")
    _p(f"  {C.B}合计:{C.RST}  {C.HYEL}{C.B}{len(result.residual_items)}{C.RST} 项残留  "
        f"占用 {C.HYEL}{C.B}{fmt_size(result.total_size)}{C.RST}")
    _p(f"  {C.HCYN}{'━' * 50}{C.RST}")

    if result.errors:
        _warn(f"扫描过程中有 {len(result.errors)} 个错误")


# ── 交互式选择 ──────────────────────────────────────────────

def prompt_yes_no(question: str, default: bool = True) -> bool:
    hint = f"{C.HGRN}Y{C.DIM}/n{C.RST}" if default else f"{C.DIM}y{C.RST}/{C.HRED}N{C.RST}"
    while True:
        try:
            ans = input(f"  {C.HCYN}?{C.RST} {question} [{hint}]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _p("")
            return False
        if not ans:
            return default
        if ans in ("y", "yes", "是"):
            return True
        if ans in ("n", "no", "否"):
            return False
        _p(f"    {C.DIM}请输入 y 或 n{C.RST}")


def prompt_category_select(results: List[ScanResult]) -> List[ScanResult]:
    print_header("选择清理类别", icon="SEL")

    available = [(i, r) for i, r in enumerate(results) if r.items and not r.error]
    if not available:
        _info_row("提示", "没有可清理的类别")
        return []

    # 带大小条的表格
    max_sz = max(r.total_size for _, r in available) if available else 1
    for idx, (_, r) in enumerate(available, 1):
        sz = r.total_size
        cnt = len(r.items)
        # 迷你条形图
        bar_w = 12
        filled = int(bar_w * sz / max_sz) if max_sz > 0 else 0
        bar = f"{C.HCYN}{'█' * filled}{C.DIM}{'░' * (bar_w - filled)}{C.RST}"
        _p(f"  {C.HGRN}{C.B}[{idx:>2}]{C.RST} {r.category:<20} "
            f"{bar}  {C.B}{cnt:>5}{C.RST} 项  {C.HYEL}{fmt_size(sz):>10}{C.RST}")

    _blank()
    _p(f"  {C.DIM}输入序号选择，逗号分隔 (1,3,5)  |  a=全部  |  回车=跳过{C.RST}")

    while True:
        try:
            ans = input(f"\n  {C.HCYN}?{C.RST} 请选择: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _p("")
            return []
        if not ans:
            return []
        if ans in ("a", "all", "全部"):
            return [r for _, r in available]
        try:
            indices = []
            for part in ans.split(","):
                part = part.strip()
                if part:
                    n = int(part)
                    if 1 <= n <= len(available):
                        indices.append(n - 1)
            if indices:
                return [available[i][1] for i in indices]
        except ValueError:
            pass
        _p(f"    {C.RED}无效输入{C.RST}")


def prompt_residual_select(result: ResidualScanResult) -> List[ResidualItem]:
    print_header("选择清理残留", icon="SEL")

    if not result.residual_items:
        _info_row("提示", "没有发现残留项目")
        return []

    type_labels = {
        "dir": "目录", "file": "文件", "registry": "注册表",
        "shortcut": "快捷方式", "service": "服务", "task": "任务", "startup": "启动项",
    }
    risk_style = {"low": (C.HGRN, "低"), "medium": (C.HYEL, "中"), "high": (C.HRED, "高")}

    for idx, item in enumerate(result.residual_items, 1):
        rc, rl = risk_style.get(item.risk_level, (C.WHT, "?"))
        tl = type_labels.get(item.residual_type, item.residual_type)
        sz = fmt_size(item.size) if item.size > 0 else "--"
        _p(f"  {C.HGRN}{C.B}[{idx:>2}]{C.RST} {C.DIM}[{tl}]{C.RST} {item.path}")
        _p(f"      {C.DIM}{item.associated_program} | {sz} | 风险 {rc}[{rl}]{C.RST}")

    _blank()
    _p(f"  {C.DIM}输入序号选择，逗号分隔  |  a=低风险  |  all=全部  |  回车=跳过{C.RST}")

    while True:
        try:
            ans = input(f"\n  {C.HCYN}?{C.RST} 请选择: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            _p("")
            return []
        if not ans:
            return []
        if ans == "a":
            return [i for i in result.residual_items if i.risk_level == "low"]
        if ans in ("all", "全部"):
            return list(result.residual_items)
        try:
            indices = []
            for part in ans.split(","):
                part = part.strip()
                if part:
                    n = int(part)
                    if 1 <= n <= len(result.residual_items):
                        indices.append(n - 1)
            if indices:
                return [result.residual_items[i] for i in indices]
        except ValueError:
            pass
        _p(f"    {C.RED}无效输入{C.RST}")


# ── 交互式主菜单 ──────────────────────────────────────────────

def prompt_main_menu() -> str:
    """显示交互式主菜单，返回用户选择的命令"""
    _blank()
    _p(f"  {C.HCYN}{C.B}┌─────────────────────────────────────────────┐{C.RST}")
    _p(f"  {C.HCYN}{C.B}│                                             │{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.HGRN}{C.B}[1]{C.RST}  {C.HWHT}完整清理{C.RST}  {C.DIM}垃圾文件 + 残留文件{C.RST}       {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.HGRN}{C.B}[2]{C.RST}  {C.HWHT}垃圾清理{C.RST}  {C.DIM}临时文件/缓存/日志等{C.RST}       {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.HGRN}{C.B}[3]{C.RST}  {C.HWHT}残留清理{C.RST}  {C.DIM}已卸载程序残留文件{C.RST}         {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.HGRN}{C.B}[4]{C.RST}  {C.HWHT}仅扫描  {C.RST}  {C.DIM}扫描但不执行清理{C.RST}           {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.HBLU}{C.B}[5]{C.RST}  {C.HWHT}系统信息{C.RST}  {C.DIM}查看磁盘/系统状态{C.RST}           {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│{C.RST}  {C.DIM}{C.B}[0]{C.RST}  {C.DIM}退出{C.RST}                               {C.HCYN}{C.B}│{C.RST}")
    _p(f"  {C.HCYN}{C.B}│                                             │{C.RST}")
    _p(f"  {C.HCYN}{C.B}└─────────────────────────────────────────────┘{C.RST}")

    while True:
        try:
            ans = input(f"\n  {C.HCYN}?{C.RST} 请选择操作 {C.DIM}[0-5]{C.RST}: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        mapping = {"1": "full", "2": "clean", "3": "residual", "4": "scan", "5": "info", "0": "quit", "q": "quit"}
        if ans in mapping:
            return mapping[ans]
        _p(f"    {C.RED}请输入 0-5{C.RST}")


def prompt_scan_options() -> dict:
    """交互式选择扫描选项"""
    _blank()
    _p(f"  {C.HYEL}{C.B}扫描选项{C.RST}  {C.DIM}(直接回车使用默认值){C.RST}")
    _p(f"  {C.DIM}{'─' * 48}{C.RST}")

    opts = {"older_than": 0, "min_size": 0, "dry_run": False, "export": None}

    # 年龄过滤
    try:
        ans = input(f"  {C.HCYN}?{C.RST} 文件年龄过滤(天) {C.DIM}[0=不限]:{C.RST} ").strip()
        if ans and ans.isdigit() and int(ans) > 0:
            opts["older_than"] = int(ans)
    except (EOFError, KeyboardInterrupt):
        pass

    # 大小过滤
    try:
        ans = input(f"  {C.HCYN}?{C.RST} 最小文件大小(KB) {C.DIM}[0=不限]:{C.RST} ").strip()
        if ans and ans.isdigit() and int(ans) > 0:
            opts["min_size"] = int(ans)
    except (EOFError, KeyboardInterrupt):
        pass

    # 模拟模式
    try:
        ans = input(f"  {C.HCYN}?{C.RST} 模拟模式(不实际删除) {C.DIM}[y/N]:{C.RST} ").strip().lower()
        opts["dry_run"] = ans in ("y", "yes", "是")
    except (EOFError, KeyboardInterrupt):
        pass

    # 导出报告
    try:
        ans = input(f"  {C.HCYN}?{C.RST} 导出报告路径 {C.DIM}[留空不导出]:{C.RST} ").strip()
        if ans:
            opts["export"] = ans
    except (EOFError, KeyboardInterrupt):
        pass

    return opts


# ── 清理报告 ──────────────────────────────────────────────

@dataclass
class CleanReport:
    junk_files_cleaned: int = 0
    junk_space_freed: int = 0
    junk_failed: int = 0
    residual_files_cleaned: int = 0
    residual_space_freed: int = 0
    residual_failed: int = 0
    categories: dict = None
    dry_run: bool = False
    elapsed_seconds: float = 0.0

    def __post_init__(self):
        if self.categories is None:
            self.categories = {}


def display_clean_report(report: CleanReport):
    title = "清理报告 [模拟]" if report.dry_run else "清理报告"
    print_header(title, icon="RPT")

    total_ok = report.junk_files_cleaned + report.residual_files_cleaned
    total_freed = report.junk_space_freed + report.residual_space_freed
    total_fail = report.junk_failed + report.residual_failed

    # 垃圾清理
    print_section("垃圾文件", icon="JUNK")
    _info_row("清理数量", f"{C.HGRN}{C.B}{report.junk_files_cleaned}{C.RST} 个")
    _info_row("释放空间", f"{C.HGRN}{C.B}{fmt_size(report.junk_space_freed)}{C.RST}")
    if report.junk_failed > 0:
        _info_row("失败数量", f"{C.HRED}{report.junk_failed}{C.RST} 个")

    if report.categories:
        _blank()
        for cat, count in report.categories.items():
            _p(f"      {C.DIM}· {cat}: {count} 项{C.RST}")

    # 残留清理
    if report.residual_files_cleaned > 0 or report.residual_failed > 0:
        print_section("残留文件", icon="RESI")
        _info_row("清理数量", f"{C.HGRN}{C.B}{report.residual_files_cleaned}{C.RST} 个")
        _info_row("释放空间", f"{C.HGRN}{C.B}{fmt_size(report.residual_space_freed)}{C.RST}")
        if report.residual_failed > 0:
            _info_row("失败数量", f"{C.HRED}{report.residual_failed}{C.RST} 个")

    # 总计面板
    _blank()
    _p(f"  {C.BGRN}{C.BLK}  CLEAN SUMMARY  {C.RST}")
    _p(f"  {C.HGRN}{'━' * 48}{C.RST}")
    _p(f"    {C.HGRN}[OK]{C.RST} 清理项目  {C.HGRN}{C.B}{total_ok}{C.RST} 个")
    _p(f"    {C.HGRN}[OK]{C.RST} 释放空间  {C.HGRN}{C.B}{fmt_size(total_freed)}{C.RST}")
    if total_fail > 0:
        _p(f"    {C.HYEL}[!!]{C.RST} 失败项目  {C.HYEL}{total_fail}{C.RST} 个  {C.DIM}(被占用/权限不足){C.RST}")
    if report.elapsed_seconds > 0:
        _p(f"    {C.DIM}耗时 {report.elapsed_seconds:.1f}s{C.RST}")
    _p(f"  {C.HGRN}{'━' * 48}{C.RST}")

    if report.dry_run:
        _blank()
        _p(f"  {C.BYEL}{C.BLK}  DRY RUN - 未实际删除任何文件  {C.RST}")
    else:
        _blank()
        _p(f"  {C.DIM}提示: 部分清理可能需要重启才能完全生效{C.RST}")


def export_report(report: CleanReport, filepath: str,
                  junk_results: List[ScanResult] = None,
                  residual_result: ResidualScanResult = None):
    data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run": report.dry_run,
        "summary": {
            "junk_files_cleaned": report.junk_files_cleaned,
            "junk_space_freed": report.junk_space_freed,
            "junk_space_freed_human": fmt_size(report.junk_space_freed),
            "junk_failed": report.junk_failed,
            "residual_files_cleaned": report.residual_files_cleaned,
            "residual_space_freed": report.residual_space_freed,
            "residual_space_freed_human": fmt_size(report.residual_space_freed),
            "residual_failed": report.residual_failed,
            "total_cleaned": report.junk_files_cleaned + report.residual_files_cleaned,
            "total_freed": report.junk_space_freed + report.residual_space_freed,
            "total_freed_human": fmt_size(report.junk_space_freed + report.residual_space_freed),
            "elapsed_seconds": report.elapsed_seconds,
        },
        "categories": report.categories,
    }
    if junk_results:
        data["junk_details"] = []
        for r in junk_results:
            if r.items:
                data["junk_details"].append({
                    "category": r.category,
                    "item_count": len(r.items),
                    "total_size": r.total_size,
                    "total_size_human": fmt_size(r.total_size),
                    "items": [{"path": i.path, "size": i.size, "description": i.description} for i in r.items[:50]],
                })
    if residual_result and residual_result.residual_items:
        data["residual_details"] = [
            {"path": i.path, "size": i.size, "type": i.residual_type,
             "associated": i.associated_program, "description": i.description,
             "risk": i.risk_level}
            for i in residual_result.residual_items
        ]
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _ok(f"报告已导出: {filepath}")
    except (OSError, IOError) as e:
        _err(f"导出失败: {e}")
