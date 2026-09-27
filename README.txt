========================================
  Google NotebookLM 助手 - 使用说明
========================================

【第一步】安装 Python（已装可跳过）
  下载: https://www.python.org/downloads/
  安装时务必勾选 "Add Python to PATH"
  建议 3.8 以上版本

【第二步】导出 Cookie（最关键）
  1. 用浏览器打开 https://notebook.google.com/ （或 https://notebooklm.google.com/ ），确认已登录
  2. 按 F12 打开开发者工具 -> 切到 Network(网络) 标签
  3. 刷新页面，点击任意一条 notebook 请求（如 batchexecute）
  4. 在 Request Headers 里找到 Cookie: 那一整行，右键 -> Copy value
  5. 新建一个文本文件，把这一整串粘贴进去
  6. 保存为 cookie.txt （必须是这个文件名），放在本文件夹内（脚本已支持双域名自动识别与自愈）

  【重要】导出后请立刻使用，不要再去刷新页面，
         因为 Google 的会话令牌会滚动更新，刷新后旧的就会失效。

【第三步】双击运行 START.bat
  然后按菜单提示选择功能：
    [1] 管理/删除数据源
    [2] 上传文件/链接/文本

【上传命令示例】（也可手动敲命令）
  python notebooklm_uploader.py --to <笔记本ID> --file "D:/docs/report.pdf"
  python notebooklm_uploader.py --to <笔记本ID> --url "https://example.com/a"
  python notebooklm_uploader.py --to <笔记本ID> --title "备注" --text "纯文本内容"

  笔记本 ID 从功能 [1] 的列表里查看。

【常见问题】
  Q: 报错 401 / ["e",4] / 提示"身份凭证已失效"
  A: Cookie 过期或失效了，重新执行【第二步】导出即可。
     注意必须用同一台电脑、同一个浏览器、同一个网络导出。

  Q: 报错 SSL / verify_mode
  A: 本包已修复该问题（TLSAdapter 补丁），若仍出现请升级：
     python -m pip install -U requests urllib3

  Q: 提示 400 Bad Request 且自动重试后仍失败
  A: Google 前端版本号 bl= 参数过期了。在浏览器 F12 -> Network 里
     找到 batchexecute 请求，把 URL 里 bl= 后面的值复制出来，
     新建 config.json 填写：
     { "base_query_params": "bl=你复制的&hl=en&rt=c" }

【安全提醒】
  cookie.txt 等同于你的账号登录凭证，切勿发送给他人或上传到网上。
