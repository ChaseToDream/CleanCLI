# CleanCLI

<p align="center">
  <strong>Windows 系统垃圾深度清理工具</strong>
</p>

<p align="center">
  智能扫描 · 安全清理 · 一键释放磁盘空间
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#命令详解">命令详解</a> •
  <a href="#清理范围">清理范围</a> •
  <a href="#安全机制">安全机制</a>
</p>

---

## 功能特性

- **深度扫描** - 覆盖 40+ 种垃圾文件类型，精准识别系统冗余
- **残留清理** - 智能检测已卸载程序的残留文件、注册表项、服务及计划任务
- **双模式运行** - 交互式菜单与命令行参数两种使用方式
- **模拟模式** - 预览清理效果，不实际删除文件
- **报告导出** - 支持 JSON 格式清理报告导出
- **零依赖** - 纯 Python 标准库实现，无需安装第三方包
- **安全可靠** - 路径白名单校验，防止误删重要文件

## 环境要求

- **操作系统**: Windows 7/8/10/11
- **Python**: 3.8 或更高版本（仅 pip 安装方式需要）

## 安装

### 方式一：下载可执行文件（推荐，无需 Python）

前往 [GitHub Releases](https://github.com/ChaseToDream/CleanCLI/releases) 下载最新版 `CleanCLI.exe`，双击即可运行。

也可以用 PowerShell 一键下载最新版：

```powershell
Invoke-WebRequest -Uri "https://github.com/ChaseToDream/CleanCLI/releases/latest/download/CleanCLI.exe" -OutFile "CleanCLI.exe"
.\CleanCLI.exe
```

### 方式二：pip 从 GitHub 安装（无需 clone）

```bash
pip install https://github.com/ChaseToDream/CleanCLI/archive/refs/heads/main.zip
```

安装后直接使用：

```bash
cleancli
```

> 如果已安装 git，也可以用：`pip install git+https://github.com/ChaseToDream/CleanCLI.git`

### 方式三：pipx 安装（推荐隔离环境）

```bash
pipx install https://github.com/ChaseToDream/CleanCLI/archive/refs/heads/main.zip
```

### 方式四：从源码安装

```bash
git clone https://github.com/ChaseToDream/CleanCLI.git
cd CleanCLI
pip install -e .
```

### 方式五：直接运行

```bash
python main.py
```

## 快速开始

### 交互式模式

直接运行命令进入交互式菜单：

```bash
cleancli
```

将显示如下菜单：

```
┌─────────────────────────────────────────────┐
│                                             │
│  [1]  完整清理  垃圾文件 + 残留文件          │
│  [2]  垃圾清理  临时文件/缓存/日志等         │
│  [3]  残留清理  已卸载程序残留文件           │
│  [4]  仅扫描    扫描但不执行清理             │
│  [5]  系统信息  查看磁盘/系统状态            │
│  [0]  退出                                   │
│                                             │
└─────────────────────────────────────────────┘
```

### 命令行模式

```bash
# 查看系统和磁盘信息
cleancli info

# 仅扫描，不清理
cleancli scan

# 扫描 30 天前的垃圾文件
cleancli scan --older-than 30

# 清理垃圾文件（交互选择类别）
cleancli clean

# 自动清理所有垃圾文件
cleancli clean --auto

# 模拟清理（不实际删除）
cleancli clean --dry-run

# 清理残留文件（自动选择低风险项）
cleancli residual --auto

# 完整清理（垃圾 + 残留）
cleancli full --auto --dry-run

# 导出清理报告
cleancli clean --export report.json
```

## 命令详解

### `cleancli info`

显示系统信息和磁盘使用情况，包括：
- 操作系统版本
- 处理器信息
- 各磁盘分区使用率可视化

### `cleancli scan`

扫描系统垃圾文件，显示各类别文件数量和大小。

| 参数 | 说明 |
|------|------|
| `--older-than N` | 仅扫描 N 天前的文件 |
| `--min-size N` | 仅扫描大于 N KB 的文件 |

### `cleancli clean`

扫描并清理系统垃圾文件。

| 参数 | 说明 |
|------|------|
| `--auto` | 自动选择所有类别，无需交互确认 |
| `--dry-run` | 模拟模式，不实际删除文件 |
| `--older-than N` | 仅清理 N 天前的文件 |
| `--min-size N` | 仅清理大于 N KB 的文件 |
| `--export FILE` | 导出 JSON 格式清理报告 |

### `cleancli residual`

扫描并清理已卸载程序的残留文件。

| 参数 | 说明 |
|------|------|
| `--auto` | 自动选择低风险残留项 |
| `--dry-run` | 模拟模式 |
| `--export FILE` | 导出清理报告 |

### `cleancli full`

执行完整清理流程（垃圾文件 + 残留文件）。

| 参数 | 说明 |
|------|------|
| `--auto` | 自动选择，无需交互确认 |
| `--dry-run` | 模拟模式 |
| `--older-than N` | 文件年龄过滤 |
| `--min-size N` | 文件大小过滤 |
| `--export FILE` | 导出清理报告 |

### 全局参数

| 参数 | 说明 |
|------|------|
| `--no-banner` | 不显示启动横幅 |

## 清理范围

### 系统垃圾

| 类别 | 说明 |
|------|------|
| 用户临时文件 | `%TEMP%`、`%LOCALAPPDATA%\Temp` |
| 系统临时文件 | `%WINDIR%\Temp` |
| Windows 更新缓存 | `SoftwareDistribution\Download` |
| 系统日志文件 | `Logs`、`Panther`、`debug` |
| 缩略图缓存 | `thumbcache_*.db` |
| 图标缓存 | `iconcache_*.db` |
| 字体缓存 | `FontCache` |
| Windows 错误报告 | `WER`、`Minidump`、`LiveKernelReports` |
| 预取文件 | `Prefetch\*.pf` |
| Windows.old | 旧系统备份目录 |
| 回收站 | `$Recycle.Bin` |
| DNS 缓存 | 系统DNS解析缓存 |

### 浏览器缓存

| 浏览器 | 清理内容 |
|--------|----------|
| Chrome | Cache、Code Cache、GPUCache、Service Worker |
| Edge | Cache、Code Cache、GPUCache、Service Worker |
| Firefox | cache2、startupCache、shader-cache |
| Brave | Cache、Code Cache、GPUCache |
| Vivaldi | Cache、Code Cache、GPUCache |
| Opera/Opera GX | Cache、Code Cache、GPUCache |

### 开发工具缓存

| 工具 | 清理路径 |
|------|----------|
| npm | `npm-cache`、`.npm` |
| pip | `pip\cache` |
| yarn | `Yarn\Cache` |
| Go | `go\pkg\mod\cache`、`go-build` |
| Cargo/Rust | `.cargo\registry`、`.cargo\git` |
| Conda | `.conda\pkgs`、`anaconda3\pkgs` |
| Chocolatey | `Chocolatey\Cache` |
| Scoop | `scoop\cache` |
| Docker | `Docker\log` |
| VS Code | `Code\Cache`、`Code\CachedData`、`Code\Logs` |

### 残留文件

| 类型 | 说明 |
|------|------|
| 残留目录 | 已卸载程序的安装目录残留 |
| 残留注册表 | 无效的卸载注册表项 |
| 孤立快捷方式 | 目标路径不存在的快捷方式 |
| 孤儿服务 | 可执行文件不存在的 Windows 服务 |
| 孤儿计划任务 | 目标程序不存在的计划任务 |
| 孤儿启动项 | 目标程序不存在的启动项 |

## 安全机制

### 路径白名单

CleanCLI 采用严格的路径白名单机制，仅清理以下安全路径：

- 系统临时目录（`%TEMP%`、`%WINDIR%\Temp`）
- 已知的缓存目录（浏览器、开发工具等）
- Windows 系统安全清理路径（`Logs`、`Prefetch` 等）

不在白名单内的路径将被拒绝清理，确保系统安全。

### 风险等级

残留文件扫描结果标注风险等级：

| 等级 | 说明 | 建议 |
|------|------|------|
| 🟢 低 | 应用数据残留、快捷方式等 | 可安全清理 |
| 🟡 中 | 安装目录残留、服务、计划任务 | 谨慎清理 |
| 🔴 高 | 系统关键项 | 不建议清理 |

### 删除保护

- **重试机制**：文件被占用时自动重试
- **只读清除**：自动清除只读属性后删除
- **错误追踪**：详细记录删除失败原因
- **模拟模式**：`--dry-run` 预览清理效果

## 权限说明

部分清理操作需要管理员权限：

- 系统临时文件
- Windows 更新缓存
- 预取文件
- 系统日志
- 回收站

建议以管理员身份运行以获得完整清理效果。

## 项目结构

```
CleanCLI/
├── cleancli/
│   ├── __init__.py      # 包初始化
│   ├── __main__.py      # 模块入口
│   ├── main.py          # 主程序入口
│   ├── cleaner.py       # 核心清理引擎
│   ├── residual.py      # 残留文件扫描
│   └── ui.py            # 终端UI模块
├── main.py              # 兼容入口
├── pyproject.toml       # 项目配置
└── requirements.txt     # 依赖声明（无外部依赖）
```

## 开发

### 环境准备

```bash
git clone https://github.com/ChaseToDream/CleanCLI.git
cd CleanCLI
pip install -e .
```

### 运行测试

```bash
cleancli scan --dry-run
```

## 常见问题

<details>
<summary><strong>Q: 为什么有些文件无法删除？</strong></summary>

A: 可能原因：
1. 文件正在被其他程序使用（显示 `locked`）
2. 权限不足，需要管理员权限（显示 `permission`）
3. 文件已被移动或删除（显示 `not_found`）

解决方案：关闭相关程序或以管理员身份运行。
</details>

<details>
<summary><strong>Q: 清理后能释放多少空间？</strong></summary>

A: 取决于系统使用情况，通常可释放：
- 轻度使用：500MB - 2GB
- 中度使用：2GB - 10GB
- 重度使用：10GB 以上（含浏览器缓存、开发工具缓存等）
</details>

<details>
<summary><strong>Q: 清理会影响系统正常运行吗？</strong></summary>

A: CleanCLI 仅清理安全的缓存和临时文件，不会影响：
- 用户个人文件
- 程序配置和设置
- 系统关键文件

部分清理（如字体缓存）可能需要重启后完全生效。
</details>

## 许可证

[MIT License](LICENSE)

## 作者

ChaseToDream

## 链接

- [GitHub 仓库](https://github.com/ChaseToDream/CleanCLI)
- [问题反馈](https://github.com/ChaseToDream/CleanCLI/issues)

---

<p align="center">
  如果觉得有用，请给一个 ⭐ Star 支持一下！
</p>
