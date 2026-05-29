# 📓 NotebookLM Helper & Automator

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Google%20NotebookLM-Reverse%20API-orange.svg?style=for-the-badge&logo=google&logoColor=white" alt="Google NotebookLM API" />
  <img src="https://img.shields.io/badge/Google%20Drive-Rclone%20OAuth2-yellow.svg?style=for-the-badge&logo=googledrive&logoColor=white" alt="Google Drive integration" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge" alt="License" />
</p>

An elegant, highly robust, and professional reverse-engineered suite designed to manage, browse, and perform batch operations on your **Google NotebookLM** sources. Safely delete sources in bulk, upload multi-format documents, and bypass transactional and XSRF limitations with a seamless bilingual CLI.

一套优雅、稳健且专业级的 Google NotebookLM 辅助管理工具套件。支持对笔记本内的 Sources 文档源进行批量查看、精准多选/全选批量删除、多格式文档极速上传，并具备防事务锁死及 XSRF Token 动态自愈等强大机制。

---

## 🗺️ Quick Document Switch / 快速文档切换

> [!TIP]
> Click the panels below to switch or expand/collapse your preferred language documentation.
> 点击下方对应的面板，即可展开/收起或自由切换中英文文档。

---

<details open>
<summary><b>🇨🇳 点击收起/展开：中文说明文档 (Chinese Documentation)</b></summary>
<br />

## ✨ 核心特性

- **📂 笔记本源批量管理控制台 (`notebooklm_helper.py`)**: 
  - **自动加载与列表展示**: 一键获取所有笔记本列表，并展示每个笔记本包含的 Sources 文档源数量与 ID。
  - **👑 强悍的批量删除 (Batch Delete)**: 进入笔记本后，支持通过数字多选（如 `1,3,5`）进行精准批量删除，或键入 `all` 一键清空所有数据源！
  - **防锁死顺序删除**: 采用逆向的微延迟顺序执行算法，完美规避 Google 后端多线程并发删除引发的 400 物理事务锁死报错。
- **🚀 多源智能流式上传器 (`notebooklm_uploader.py`)**:
  - 支持将**本地二进制大文件**（PDF, Word docx, Markdown, 音频, 图片等）通过分块流式上传协议 (Resumable Upload) 极速导入。
  - 支持将**网络 URL 链接**或直接粘贴的**纯文本**一键导入笔记本。
  - 支持直接免流量挂载 **Google Drive** 中的云端原生 Docs 文档、Slides 幻灯片、Sheets 表格或大文件。
- **⚡ 坚不可摧的 Session 鉴权自愈**: 
  - **XSRF 自动修复**: 自动捕获并突破 400 Bad Request 校验阻断，动态拦截最新的 XSRF Token 并静默重试。
  - **Fail-Fast 凭证诊断**: 遇到 Cookie 失效 (`["e", 4]`) 时立即中断执行，提供最精准的单点登录 (OSID) 页面排障提示。
- **🔒 隐私配置安全**: 所有敏感配置文件（如 `cookie.txt`、`rclone.conf`）已被自动忽略，绝不泄漏您的谷歌账户。

---

## 🚀 快速上手

### 1. 环境与依赖安装
克隆本项目到本地后，安装标准的网络支持库：
```bash
pip install requests urllib3 configparser
```

### 2. 身份凭证配置
在项目根目录下配置以下两个私有文件（均已加入 `.gitignore` 保护）：

| 配置文件名 | 用途 | 获取与配置方法 |
| :--- | :--- | :--- |
| **`cookie.txt`** | 鉴权 NotebookLM | 浏览器打开并登录 [Google NotebookLM](https://notebooklm.google.com/)，按 **F12** ➡️ **网络(Network)**，复制任意请求的标头 `Cookie` 字符串（或导出 Cookies JSON 数组），粘贴进该文件保存。 |
| **`rclone.conf`** | 鉴权 Google Drive | 将包含有 `[gdriver]` 以及 OAuth2 的 `client_id`, `client_secret` 和 `refresh_token` 的 rclone 配置文件放入项目根目录（仅在使用网盘导入时需要）。 |

---

## 🎮 控制台操作指南

### A. 批量管理与删除数据源 (`notebooklm_helper.py`)
直接在终端或命令行中启动主控制台：
```bash
python notebooklm_helper.py
```

#### 1. 选择要操作的笔记本
启动后，控制台会拉取并列出您的所有笔记本：
```text
============================================================
                  Google NotebookLM 笔记本选择菜单
============================================================
[ 1] 📓 个人知识库资料
     ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8 (3 个文档源)
------------------------------------------------------------
[ 2] 📓 备考单词背诵库
     ID: a8b9c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d (12 个文档源)
------------------------------------------------------------
请输入您的操作序号: 1
```

#### 2. 对笔记本数据源进行精准批量操作
输入序号进入具体笔记本后，会批量展示所有的文档源列表：
```text
============================================================
       管理笔记本: 个人知识库资料
       ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8
============================================================
[ 1] 📄 mistakes.md (ID: 12fe3c81-4f54-49a7-9b1f-99fa61345e04)
[ 2] 📄 chunks.md   (ID: a8b9c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d)
[ 3] 📄 README.md   (ID: f5g6h7i8-9j0k-1l2m-3n4o-5p6q7r8s9t0u)
------------------------------------------------------------

💡 批量操作指令说明:
 👉 输入单个数字（例如: 3）：删除该文件。
 👉 输入多个数字并用英文逗号隔开（例如: 1,3）：批量多选删除指定的这几个文档。
 👉 输入 "all"：一键全选删除该笔记本下的所有文件。
 👉 输入 "back"：返回上级笔记本选择菜单。
 👉 输入 "exit"：退出程序。
```

---

### B. 多功能文档源上传 (`notebooklm_uploader.py`)

支持手动选择或编写脚本调用导入：
```bash
# 启动图形向导式交互菜单（手动一步步选择）
python notebooklm_uploader.py

# 脚本命令行直连上传
# 1. 3阶段分块流式上传本地大文件/PDF/docx
python notebooklm_uploader.py --to <笔记本ID> --file "C:\docs\report.pdf"

# 2. 批量脚本化导入网页链接
python notebooklm_uploader.py --to <笔记本ID> --url "https://example.com/article"

# 3. 导入纯文本数据源
python notebooklm_uploader.py --to <笔记本ID> --title "My Memo" --text "This is raw text to import."
```

</details>

---

<details>
<summary><b>🌐 Click to Expand/Collapse: English Documentation (英文说明文档)</b></summary>
<br />

## ✨ Key Features

- **📂 Bulk Source Manager & Console (`notebooklm_helper.py`)**: 
  - **Auto-List and Discover**: Automatically scans and lists all your notebooks along with their respective source counts and unique IDs.
  - **👑 Powerful Bulk Purge (Batch Delete)**: Allows selecting specific items by indices (e.g., `1,3,5`), or typing `all` to wipe out all sources inside the designated notebook in one click.
  - **Safe Deletion Throttle**: Utilizes sequential execution routing to fully bypass Google's strict backend transaction locks and concurrency 400 errors.
- **🚀 Advanced Source Uploader (`notebooklm_uploader.py`)**:
  - Stream-uploads **local binary files** (PDFs, docx, Markdown, audios, images, etc.) safely via Google's 3-step Resumable Upload protocol.
  - Instantly ingests public **Web URLs** or raw **copied plain text**.
  - Mounts **Google Drive** native documents (Docs, Slides, Sheets) with zero server bandwidth overhead.
- **⚡ Bulletproof Session Self-Healing**: 
  - **XSRF Auto-Recovery**: Intercepts 400 validation locks, parses Google's short-lived XSRF token, and auto-retries dynamically.
  - **Fail-Fast OSID Diagnostics**: Stops execution immediately upon cookie expiry (`["e", 4]`), pointing out precise cross-origin OSID solutions.

---

## 🚀 Getting Started

### 1. Requirements & Setup
Clone the repository and install the standard networking dependencies:
```bash
pip install requests urllib3 configparser
```

### 2. Credentials Setup
Place these private credential files in the root directory (they are safely ignored in `.gitignore`):

| File Name | Purpose | Configuration Method |
| :--- | :--- | :--- |
| **`cookie.txt`** | Authenticates NotebookLM | Log into [NotebookLM](https://notebooklm.google.com/), open **F12** ➡️ **Network**, copy the raw request `Cookie` header (or export cookie JSON list), and paste it directly into this file. |
| **`rclone.conf`** | Connects to Google Drive | Contains your Rclone `[gdriver]` OAuth2 refresh token credentials (only required for Google Drive ingestion). |

---

## 🎮 Execution Commands

### A. Bulk Source Management & Deletion (`notebooklm_helper.py`)
Launch the interactive terminal manager:
```bash
python notebooklm_helper.py
```

#### 1. Select a Notebook
The tool lists all your available notebooks:
```text
============================================================
                  Google NotebookLM Notebook Menu
============================================================
[ 1] 📓 My Knowledge Base
     ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8 (3 sources)
------------------------------------------------------------
[ 2] 📓 English Vocabulary
     ID: a8b9c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d (12 sources)
------------------------------------------------------------
Please enter your operation index: 1
```

#### 2. Execute Batch Actions on Sources
Once entered, list all documents and perform bulk operations:
```text
============================================================
       Manage Notebook: My Knowledge Base
       ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8
============================================================
[ 1] 📄 mistakes.md (ID: 12fe3c81-4f54-49a7-9b1f-99fa61345e04)
[ 2] 📄 chunks.md   (ID: a8b9c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d)
[ 3] 📄 README.md   (ID: f5g6h7i8-9j0k-1l2m-3n4o-5p6q7r8s9t0u)
------------------------------------------------------------

💡 Batch Commands Instructions:
 👉 Enter a single index (e.g., 3): Deletes that specific file.
 👉 Enter multiple indices separated by commas (e.g., 1,3): Deletes the chosen sources in bulk.
 👉 Enter "all": Instantly deletes all files in this notebook.
 👉 Enter "back": Returns to the notebook selection menu.
 👉 Enter "exit": Closes the program.
```

---

### B. Ingesting Documents (`notebooklm_uploader.py`)

Either use the step-by-step interactive wizard or call it via shell script:
```bash
# Start interactive wizard
python notebooklm_uploader.py

# Programmatically upload files or URLs
# 1. 3-step Resumable Upload for local files
python notebooklm_uploader.py --to <notebook-id> --file "C:\docs\report.pdf"

# 2. Ingest Web articles
python notebooklm_uploader.py --to <notebook-id> --url "https://example.com/article"
```

</details>

---

## 📄 MIT License / 开源协议

This project is open-source and licensed under the **MIT License**.  
本项目基于 **MIT 协议** 开放，随时欢迎提交 Issue 或拉取 Pull Request 进行升级！
