# 📓 NotebookLM Helper

An elegant, robust, and lightweight Python-based CLI tool to manage and batch-delete sources in your **Google NotebookLM** notebooks. Features automatic dynamic XSRF (CSRF) token acquisition, session self-healing, interactive notebook-selection menu, and sequential execution routing to bypass Google's backend transaction limits.

一套优雅、稳健且轻量级的 Python 命令行工具，用于快速管理和批量删除 **Google NotebookLM** 笔记本中的文档源。具备笔记本交互式管理列表、XSRF (CSRF) 安全 Token 自动动态提取、会话自愈重试，以及顺序执行防事务锁死等机制。

---

## 🌟 Features / 功能特性

- **Notebook Selection / 笔记本轻松选择**：Instantly lists all your notebooks. Select any notebook by index to manage its sources. / 自动获取并列出你的所有笔记本，支持输入序号轻松跨笔记本切换与管理。
- **Bilingual CLI / 中英双语控制台**：Fully customizable interactive menu. / 支持全中文交互菜单。
- **Batch Selection / 多选与全选**：Delete specific items by index (e.g., `1,3,5`), select all (`all`), or exit safely. / 键入多个序号（如 `1,3,5`）批量删除，或输入 `all` 一键全选清空。
- **Super-Simple Credentials / 极简身份凭证加载**：
  - **Option 1**: Directly paste your raw browser cookie string into a simple `cookie.txt` file. / **方法 1**: 直接创建 `cookie.txt` 粘贴你从浏览器复制的整段 Cookie 文本。
  - **Option 2**: Configure it as a string `"cookie": "..."` or array inside `config.json`. / **方法 2**: 在 `config.json` 中以字符串或传统数组形式配置。
- **Credential Safety / 安全隐私保障**：All credentials (`config.json`, `cookie.txt`) are dynamically ignored by `.gitignore` to prevent leaking your Google account on GitHub. / 敏感的 Cookies 及文件已被 `.gitignore` 自动忽略，100% 杜绝因提交代码导致泄露谷歌账号的风险。
- **Dynamic XSRF Bypass / 自动突破 XSRF 防御**：Intercepts `400 Bad Request` and dynamically parses Google's short-lived XSRF token for smooth execution. / 智能捕获 400 校验阻断，动态解析并装载最新的 XSRF Token 并自动重试。
- **Safe Transaction Locks / 分布式事务锁规避**：Iterates deletions sequentially, preventing Google's backend from returning strict transactional HTTP 400 errors. / 采用顺序式渐进删除，规避 Google 后端并发删除时引发的物理事务拦截锁。

---

## 🛠️ Setup & Usage / 安装与使用步骤

### Step 1: Install Requirements / 步骤一：安装依赖项
Ensure you have Python 3.7+ installed. Clone this repository and install requests:
确保你已安装 Python 3.7+ 版本。安装 `requests` 库：
```bash
pip install requests
```

### Step 2: Paste Cookie / 步骤二：粘贴 Cookie (极简)
- **The Easiest Way / 最简单方法**：
  Create a file named `cookie.txt` in the project directory, and paste your raw browser `Cookie` header string directly inside it.
  在项目根目录下创建一个名为 `cookie.txt` 的文件，直接粘贴从浏览器开发者工具（F12 -> 网络 Network）中复制的整段 `Cookie` 文本。
- **Alternative Way / 备选方法**：
  Rename `config.json.template` to `config.json` and fill out the `"cookie"` string property.
  复制 `config.json.template` 并命名为 `config.json`，在其中的 `"cookie"` 字段中填入你的 Cookie 串。

### Step 3: Run the CLI Console / 步骤三：运行交互式控制台
Start the script via your terminal:
直接在终端或命令行中启动脚本：
```bash
python notebooklm_helper.py
```

---

## 🎮 How to Interact / 控制台操作指南

Once launched, the console lists all your notebooks:
启动后，控制台首先会列出你的所有笔记本：

```text
============================================================
                  Google NotebookLM 笔记本选择菜单
============================================================
[ 1] 📓 机器学习研究资料
     ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8 (3 个文档源)
------------------------------------------------------------
[ 2] 📓 英语单词背诵库
     ID: a8b9c1d2-3e4f-5a6b-7c8d-9e0f1a2b3c4d (12 个文档源)
------------------------------------------------------------

💡 操作指令说明:
 1. 输入对应数字序号进入该笔记本进行管理与批量删除。
 2. 输入 "exit" 退出程序。
```

Select a notebook to load its sources and perform bulk deletes:
输入数字进入具体笔记本后，即可对文档源进行管理：

```text
============================================================
       管理笔记本: 机器学习研究资料
       ID: 6fbc4156-647a-4453-8ad5-f6cc7008a6e8
============================================================
[ 1] 📄 confusing-words.txt
     ID: 12fe3c81-4f54-49a7-9b1f-99fa61345e04
------------------------------------------------------------

💡 操作指令说明:
 1. 输入单个数字（例如: 3）选择删除该文件。
 2. 输入多个数字并用英文逗号隔开（例如: 1,3,5）批量选择删除。
 3. 输入 "all" 全选删除该笔记本下的所有文件。
 4. 输入 "back" 返回上级笔记本选择菜单。
 5. 输入 "exit" 退出程序。
```

---

## 🚀 Smart Source Uploader / 智能 Source 上传器 (`notebooklm_uploader.py`)

We have added a powerful new uploader utility **`notebooklm_uploader.py`** to let you ingest files, web URLs, or plain text into your designated Google NotebookLM notebooks.
我们全新加入了强大的上传工具 **`notebooklm_uploader.py`**，支持将本地文件、网页链接或纯文本极速导入指定的 Google NotebookLM 笔记本中。

### Features / 核心功能
1. **Interactive Wizard / 极简交互菜单**：If run without arguments, it lists all notebooks, guides you to select or create a notebook, choose a source type, and complete the upload in seconds. / 不带参数运行时，自动拉取笔记本列表，一步步引导你选择或新建笔记本、选择导入源类型，完成上传。
2. **Command-Line Ingestion / 命令行脚本对接**：Ingest resources programmatically using simple shell commands. / 支持通过命令行参数直接调用，非常适合脚本自动化与工作流对接。
3. **Resumable Uploads / 谷歌分块可恢复协议**：Upload large local files (PDFs, Word docs, Audios, Images, etc.) reliably via Google's 3-step Resumable Upload API. / 通过逆向出的 Google 3阶段 Resumable Upload 协议，支持上传 PDF、Word、音频、图片等各种本地大文件。

### Usage / 导入指令示例

#### 1. Interactive Mode / 极简保姆级交互模式
```bash
python notebooklm_uploader.py
```

#### 2. Direct CLI Ingestion Mode / 命令行极速导入模式
```bash
# Upload a local PDF file / 上传本地 PDF 文件到指定笔记本
python notebooklm_uploader.py --to <notebook-id> --file "C:\\path\\to\\document.pdf"

# Add a Web URL / 导入网页链接到指定笔记本
python notebooklm_uploader.py --to <notebook-id> --url "https://example.com/article"

# Upload plain text / 导入纯文本数据源
python notebooklm_uploader.py --to <notebook-id> --title "My Notes" --text "This is raw text content to ingest."

# Ingest a Google Drive file (Google Docs, Slides, Sheets, PDF, etc.) / 导入 Google Drive 云端文件 (支持文档、幻灯片、表格、PDF)
python notebooklm_uploader.py --to <notebook-id> --gdrive "<Google-Drive-File-ID>" --title "My Drive Doc" --mime "application/vnd.google-apps.document"
```

---

## 📄 License / 开源协议

This project is open-source and licensed under the **MIT License**.
本项目基于 **MIT 协议** 开源，欢迎提交 Issue 或 Pull Request 进行功能扩展与改进。
