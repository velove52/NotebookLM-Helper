# 📓 NotebookLM Helper & Automator

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Google%20NotebookLM-Reverse%20API-orange.svg?style=for-the-badge&logo=google&logoColor=white" alt="Google NotebookLM API" />
  <img src="https://img.shields.io/badge/Google%20Drive-Rclone%20OAuth2-yellow.svg?style=for-the-badge&logo=googledrive&logoColor=white" alt="Google Drive integration" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License" />
</p>

An elegant, highly robust, and professional reverse-engineered suite designed to automate and orchestrate **Google NotebookLM** operations. Supports dynamic XSRF self-healing, multi-source stream upload, full Google Drive OAuth2 synchronization, and automated cron-friendly pipeline reconstruction.

一套优雅、稳健且专业级逆向工程工具套件，专为 **Google NotebookLM** 的全自动同步与管理而生。完美支持动态 XSRF 自愈握手、多源流式上传、完整的 Google Drive OAuth2 网盘集成以及定时任务友好的一键重建流。

---

## 🗺️ Quick Navigation / 快速导航

- [🌐 English README](#-english-documentation)
- [🇨🇳 中文说明文档](#-中文说明文档)

---

# 🌐 English Documentation

## ✨ Key Features
- **⚡ Bulletproof Session Self-Healing**: Automatically catches Google's strict validation checks. Seamlessly intercepts short-lived XSRF token expiry and auto-updates dynamically on the fly.
- **🔄 Fail-Fast Invalidation Diagnostics**: Intercepts Google's cross-origin `["e", 4]` (Unauthorized) session errors, instantly halting failure cascades with clear, human-readable troubleshooting guidance.
- **📂 Google Drive native OAuth2 integration**: Native integration with Google Drive (via OAuth2 / Rclone). Instantly syncs Google Docs/Slides/Sheets using server-side zero-traffic links, and streams binary files (PDF, docx, txt, etc.) using a 3-step Resumable Upload pipeline.
- **📅 Dynamic Date-Based Ingestion (`sync_ielts.py`)**: Automatically scans custom backups (like `/openclaw`), detects the latest date-stamped folder, purges existing items inside NotebookLM, and rebuilds the corpus in one click.
- **🔒 Fully Ignored Credentials**: Pre-configured Git configuration ensures sensitive files (`cookie.txt`, `rclone.conf`, `sync_ielts.py`) are strictly kept local and never pushed to public repositories.

---

## 🚀 Getting Started

### 1. Requirements & Setup
Clone the repository and install the standard networking dependencies:
```bash
pip install requests urllib3 configparser
```

### 2. Quick Credentials Configuration
To connect with Google Services, you need to provide your authentication details locally:

| File Name | Purpose | Configuration Method |
| :--- | :--- | :--- |
| **`cookie.txt`** | Authenticates NotebookLM | Log into [NotebookLM](https://notebooklm.google.com/), open **F12** ➡️ **Network**, copy the raw request `Cookie` header (or export cookie JSON list), and paste it directly into this file. |
| **`rclone.conf`** | Connects to Google Drive | Place your Rclone config containing `[gdriver]` with valid client credentials and refresh token in the root folder. |

---

## 🎮 Execution Commands

### A. One-Click Automated Sync (`sync_ielts.py`)
Run the standalone cron-friendly reconstruction script. It completely clears the designated notebook, locates the latest backup inside your Google Drive, and uploads all learning files:
```bash
python sync_ielts.py
```

### B. Interactive Notebook Management Console (`notebooklm_helper.py`)
Launch the terminal manager to view notebooks, search, or batch-delete sources:
```bash
python notebooklm_helper.py
```

### C. Direct CLI & Interactive Source Uploader (`notebooklm_uploader.py`)
Upload any type of document either interactively or through direct shell execution:
```bash
# Launch interactive helper
python notebooklm_uploader.py

# Ingest a Web URL programmatically
python notebooklm_uploader.py --to <notebook-id> --url "https://example.com/article"

# Stream-upload a local PDF file
python notebooklm_uploader.py --to <notebook-id> --file "C:\docs\ielts-prep.pdf"
```

---

# 🇨🇳 中文说明文档

## ✨ 核心特性
- **⚡ 坚不可摧的 Session 自愈**: 自动捕获并突破 Google 严格的会话安全检查。当发生 XSRF Token 过期或 400 拦截时，自动完成动态刷新并静默重试。
- **🔄 极速 Fail-Fast 凭证诊断**: 智能拦截 Google 跨域 `["e", 4]` (会话失效/注销) 错误。拒绝静默失败，在发生失效的第一时间中断运行，并给出最精准的保姆级排障提示。
- **📂 谷歌网盘原生 OAuth2 对接**: 基于安全通道的 Google Drive 集成。可实现谷歌 Docs、Slides、Sheets 的“云端免流量秒挂载”，并对 PDF、Docx、Markdown 等二进制文件进行 3阶段流式流控上传。
- **📅 智能日期备份定位与一键同步 (`sync_ielts.py`)**: 专为自动化场景打造。自动扫描云端网盘（如 `openclaw`）下的最新日期文件夹，智能清空目标笔记本，并秒级重构导入全部最新语料。
- **🔒 绝对的隐私与配置安全**: 预置了极致安全的 Git 规则，所有敏感配置文件（如 `cookie.txt`、`rclone.conf`、个人专属的 `sync_ielts.py`）已被配置为自动忽略，**绝不会意外提交至公开 GitHub 仓库**。

---

## 🚀 极速上手

### 1. 环境与依赖安装
克隆本项目到本地后，安装标准的网络支持库：
```bash
pip install requests urllib3 configparser
```

### 2. 身份凭证快速配置
为了能够访问您的谷歌服务，请在项目根目录下配置以下两个私有文件：

| 配置文件名 | 用途 | 获取与配置方法 |
| :--- | :--- | :--- |
| **`cookie.txt`** | 鉴权 NotebookLM | 浏览器打开并登录 [Google NotebookLM](https://notebooklm.google.com/)，按 **F12** ➡️ **网络(Network)**，复制任意请求的标头 `Cookie` 字符串（或导出 Cookies JSON 数组），粘贴进该文件保存。 |
| **`rclone.conf`** | 鉴权 Google Drive | 将包含有 `[gdriver]` 以及 OAuth2 的 `client_id`, `client_secret` 和 `refresh_token` 的 rclone 配置文件放入项目根目录。 |

---

## 🎮 自动化与运行命令

### A. 一键全自动同步与重建 (`sync_ielts.py`)
专门针对 IELTS 等定期学习资料更新设计的自动化同步脚本。自动清空云端旧数据，并在云端网盘锁定最新日期文件夹一键重构：
```bash
python sync_ielts.py
```

### B. 交互式笔记本管理控制台 (`notebooklm_helper.py`)
启动保姆级中文控制台，管理并批量挑选删除指定的旧文档源：
```bash
python notebooklm_helper.py
```

### C. 命令行与交互式极速上传器 (`notebooklm_uploader.py`)
支持手动选择或编写脚本调用导入：
```bash
# 启动图形向导式交互菜单
python notebooklm_uploader.py

# 脚本化导入网页文章
python notebooklm_uploader.py --to <笔记本ID> --url "https://example.com/article"

# 3阶段流式上传本地大文件/PDF/Markdown
python notebooklm_uploader.py --to <笔记本ID> --file "C:\docs\ielts-prep.pdf"
```

---

## 📄 MIT License / 开源协议

This project is open-source and licensed under the **MIT License**.  
本项目基于 **MIT 协议** 开放，随时欢迎提交 Issue 或拉取 Pull Request 进行升级！
