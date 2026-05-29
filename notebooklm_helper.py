import os
import json
import re
import sys
import ssl
import time
from typing import List, Dict, Optional, Any
import requests
import urllib3
from requests.adapters import HTTPAdapter

# 禁用 SSL 警告以保持控制台整洁
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set terminal encoding to UTF-8 to prevent encoding crashes on Windows command line
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class TLSAdapter(HTTPAdapter):
    """Custom TLS Adapter to resolve [SSL: UNEXPECTED_EOF_WHILE_READING] handshake errors

    occurring behind Clash or other HTTP/2 local proxy environments with modern OpenSSL.
    """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class NotebookLMClient:
    """An elegant Python client for managing Google NotebookLM sources and notebooks.
    
    Uses reverse-engineered Google batchexecute RPC APIs with built-in 
    dynamic XSRF (CSRF) token acquisition, auto session-cookie pruning, 
    and self-healing request retries.
    """

    # Essential authentication keys needed by Google accounts.
    # Non-essential tracking and layout cookies (like NID, AEC, etc.) are pruned 
    # to dramatically reduce request header size, avoiding Clash proxy protocol violations.
    ESSENTIAL_COOKIE_KEYS = {
        "SAPISID", "__Secure-3PAPISID", "__Secure-1PAPISID", 
        "__Secure-1PSID", "__Secure-3PSID", 
        "__Secure-1PSIDTS", "__Secure-3PSIDTS",
        "__Secure-1PSIDCC", "__Secure-3PSIDCC",
        "SID", "HSID", "SSID", "APISID", "OSID", "__Secure-OSID"
    }

    def __init__(self, config_path: str = "config.json"):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(script_dir, config_path)
        self.cookie_txt_path = os.path.join(script_dir, "cookie.txt")
        
        self.notebook_id: str = ""
        self.base_query_params: str = ""
        self.cookie_header: str = ""
        self.headers: Dict[str, str] = {}
        self.xsrf_token: Optional[str] = None
        
        # Initialize robust session and mount our custom TLSAdapter
        self.session = requests.Session()
        self.session.mount("https://", TLSAdapter())
        
        self.load_config()

    def _prune_cookie_string(self, cookie_string: str) -> str:
        """Parses raw cookie string, prunes non-essential keys, and rebuilds the header."""
        pairs = [p.strip() for p in cookie_string.split(";") if p.strip()]
        pruned_pairs = []
        for pair in pairs:
            if "=" in pair:
                key, val = pair.split("=", 1)
                key = key.strip()
                if key in self.ESSENTIAL_COOKIE_KEYS:
                    pruned_pairs.append(f"{key}={val.strip()}")
            else:
                pruned_pairs.append(pair)
        return "; ".join(pruned_pairs)

    def _parse_raw_cookie_or_json(self, raw_content: str) -> str:
        """Intelligently detects and parses raw semicolon cookie strings or JSON arrays/objects

        while automatically pruning non-essential keys to shrink request size.
        """
        raw_content = raw_content.strip()
        if not raw_content:
            return ""
            
        # Clean up potential "Cookie: " prefix if copied directly from headers
        if raw_content.lower().startswith("cookie:"):
            raw_content = raw_content[7:].strip()
            
        try:
            # Attempt to parse as JSON (standard Chrome cookie export format)
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                # It's an exported JSON cookie list: [{"name": "A", "value": "B"}, ...]
                pruned_list = []
                for c in parsed:
                    if isinstance(c, dict) and 'name' in c and 'value' in c:
                        if c['name'] in self.ESSENTIAL_COOKIE_KEYS:
                            pruned_list.append(f"{c['name']}={c['value']}")
                return "; ".join(pruned_list)
            elif isinstance(parsed, dict):
                # It's a JSON config structure
                if "cookie" in parsed:
                    return self._parse_raw_cookie_or_json(str(parsed["cookie"]))
                elif "cookies" in parsed and isinstance(parsed["cookies"], list):
                    pruned_list = []
                    for c in parsed["cookies"]:
                        if isinstance(c, dict) and 'name' in c and 'value' in c:
                            if c['name'] in self.ESSENTIAL_COOKIE_KEYS:
                                pruned_list.append(f"{c['name']}={c['value']}")
                    return "; ".join(pruned_list)
                else:
                    # Simple key-value dict: {"A": "B"}
                    return "; ".join([f"{k}={v}" for k, v in parsed.items() if k in self.ESSENTIAL_COOKIE_KEYS])
        except json.JSONDecodeError:
            # Fall back to raw string and prune it
            return self._prune_cookie_string(raw_content)
        return raw_content

    def load_config(self) -> None:
        """Loads configuration from JSON file or cookie.txt safely."""
        # 1. Load config.json if present
        config = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    config = json.load(f)
                except Exception as e:
                    print(f"⚠️ 解析 config.json 失败: {e}，将尝试其他凭证。")
            
        self.notebook_id = config.get("notebook_id", "")
        self.base_query_params = config.get("base_query_params", "bl=boq_labs-tailwind-frontend_20260527.15_p0&f.sid=6211136545456590612&hl=en&rt=c")
        
        # 2. Extract Cookie (Priority: cookie.txt > config.json "cookie" string > config.json "cookies" list)
        if os.path.exists(self.cookie_txt_path):
            with open(self.cookie_txt_path, "r", encoding="utf-8") as f:
                raw_txt = f.read()
                self.cookie_header = self._parse_raw_cookie_or_json(raw_txt)
        else:
            raw_cookie = config.get("cookie", "")
            if raw_cookie:
                self.cookie_header = self._parse_raw_cookie_or_json(str(raw_cookie))
            else:
                cookies_list = config.get("cookies", [])
                cookies_dict = {c["name"]: c["value"] for c in cookies_list if c["name"] in self.ESSENTIAL_COOKIE_KEYS}
                self.cookie_header = "; ".join([f"{k}={v}" for k, v in cookies_dict.items()])
                
        if not self.cookie_header:
            raise ValueError(
                "❌ 未找到任何有效的 Cookie 凭证！\n"
                "请选择以下方式之一提供 Cookie:\n"
                "  1. 在脚本所在目录下创建 'cookie.txt' 并直接粘贴你的浏览器 Cookie 字符串。\n"
                "  2. 在 'config.json' 中添加 \"cookie\": \"你的浏览器 Cookie 字符串\"。\n"
                "  3. 在 'config.json' 中填写 \"cookies\" 列表结构。"
            )
        
        # Build standard HTTP headers simulating a legitimate browser request
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Cookie": self.cookie_header,
            "X-Same-Domain": "1",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://notebooklm.google.com/",
            "Origin": "https://notebooklm.google.com"
        }

    def _send_rpc(self, rpc_id: str, params: list, source_path: str = "/") -> requests.Response:
        """Sends an RPC request via the batchexecute endpoint, automatically retrying on proxy jitter."""
        url = (
            f"https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute"
            f"?rpcids={rpc_id}"
            f"&source-path={source_path}"
            f"&{self.base_query_params}"
        )
        
        payload = {
            "f.req": json.dumps([[[rpc_id, json.dumps(params), None, "generic"]]])
        }
        
        if self.xsrf_token:
            payload["at"] = self.xsrf_token
            
        last_err = None
        for attempt in range(3):
            try:
                # 使用 self.session.post 并设置 verify=False 及 10s 超时时间，完美规避本地代理网络波动
                return self.session.post(url, data=payload, headers=self.headers, verify=False, timeout=10)
            except (requests.exceptions.RequestException, ssl.SSLError) as e:
                last_err = e
                time.sleep(1)
                
        raise last_err

    def _execute_rpc_with_xsrf_retry(self, rpc_id: str, params: list, source_path: str = "/") -> requests.Response:
        """Executes an RPC request, automatically resolving and retrying upon XSRF 400 errors."""
        response = self._send_rpc(rpc_id, params, source_path)
        
        # If blocked by 400 Bad Request, intercept the XSRF token and self-heal
        if response.status_code == 400:
            match = re.search(r'"xsrf"\s*,\s*"([^"]+)"', response.text)
            if match:
                self.xsrf_token = match.group(1)
                # Retry request with valid token
                response = self._send_rpc(rpc_id, params, source_path)
                
        # 智能诊断：只有当响应中包含 Google 授权失效错误码 ["e", 4]，且不包含当前 RPC 请求成功标志时，才判定为凭证失效
        if ('[["e",4' in response.text or '["e",4' in response.text) and f'"{rpc_id}"' not in response.text:
            print("\n❌ 身份凭证已失效（Google 会话已过期或已被注销）！")
            print("💡 请重新在 Chrome 浏览器中登录 NotebookLM，打开 F12 复制最新的 Cookie 并更新到 'cookie.txt' 中。")
            raise PermissionError("❌ Google 登录会话已过期或被注销，请更新 cookie.txt 中的 Cookie。")
                
        return response

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """Retrieves all Notebooks belonging to the user."""
        rpc_id = "wXbhsf"
        params = [None, 1, None, [2]]
        
        print("正在请求获取 Notebook 列表...")
        response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path="/")
        
        if response.status_code != 200:
            print(f"❌ 获取 Notebook 列表失败，状态码: {response.status_code}")
            return []
            
        text = response.text
        if text.startswith(")]}'"):
            text = text[4:].strip()
            
        try:
            lines = text.split('\n')
            json_data = None
            for line in lines:
                if line.strip().startswith('[['):
                    json_data = json.loads(line.strip())
                    break
                    
            if json_data:
                result_str = json_data[0][2]
                if not result_str:
                    return []
                    
                result_list = json.loads(result_str)
                if not result_list or not isinstance(result_list, list) or len(result_list) == 0:
                    return []
                    
                raw_notebooks = result_list[0]
                if not isinstance(raw_notebooks, list):
                    return []
                    
                parsed_notebooks = []
                for nb in raw_notebooks:
                    if not isinstance(nb, list) or len(nb) < 3:
                        continue
                    
                    raw_title = nb[0] if isinstance(nb[0], str) else ""
                    title = raw_title.replace("thought\n", "").strip()
                    notebook_id = nb[2] if isinstance(nb[2], str) else ""
                    
                    # Extract sources count
                    sources_list = nb[1]
                    sources_count = len(sources_list) if isinstance(sources_list, list) else 0
                    
                    if notebook_id:
                        parsed_notebooks.append({
                            "title": title,
                            "id": notebook_id,
                            "sources_count": sources_count
                        })
                return parsed_notebooks
        except Exception as e:
            # Silence internal parsing tracebacks if auth failed
            if '[["e",4' not in response.text:
                print(f"❌ 解析 Notebook 列表异常: {e}")
        return []

    def list_sources(self) -> List[Dict[str, str]]:
        """Retrieves all sources inside the target notebook.
        
        Returns:
            A list of dicts representing sources, each containing 'title' and 'id'.
        """
        rpc_id = "rLM1Ne"
        params = [self.notebook_id, None, [2], None, 0]
        source_path = f"/notebook/{self.notebook_id}"
        
        print(f"正在请求获取 {self.notebook_id} 下的 Source 列表...")
        response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path=source_path)
        
        if response.status_code != 200:
            print(f"❌ 获取列表失败，状态码: {response.status_code}")
            return []
            
        text = response.text
        if text.startswith(")]}'"):
            text = text[4:].strip()
            
        try:
            lines = text.split('\n')
            json_data = None
            for line in lines:
                if line.strip().startswith('[['):
                    json_data = json.loads(line.strip())
                    break
                    
            if json_data:
                result_str = json_data[0][2]
                if not result_str:
                    return []
                    
                result_list = json.loads(result_str)
                if not result_list or not isinstance(result_list, list) or len(result_list) == 0:
                    return []
                    
                sources = result_list[0][1]
                if not sources:
                    return []
                    
                parsed_sources = []
                for src in sources:
                    title = src[1]
                    raw_id = src[0]
                    source_id = ""
                    
                    if isinstance(raw_id, list):
                        if raw_id[0] is not None:
                            source_id = str(raw_id[0])
                        elif len(raw_id) > 2 and isinstance(raw_id[2], list):
                            source_id = str(raw_id[2][0])
                    else:
                        source_id = str(raw_id)
                    
                    parsed_sources.append({"title": title, "id": source_id})
                return parsed_sources
        except Exception as e:
            pass
        return []

    def delete_sources(self, source_ids: List[str]) -> None:
        """Deletes a list of source files sequentially to prevent database lockups."""
        if not source_ids:
            print("⚠️ 未指定任何需要删除的文件 ID")
            return
            
        rpc_id = "tGMBJ"
        source_path = f"/notebook/{self.notebook_id}"
        total = len(source_ids)
        print(f"\n正在顺序执行删除任务（共 {total} 个文件）...")
        
        success_count = 0
        for idx, sid in enumerate(source_ids, start=1):
            print(f"[{idx}/{total}] 正在删除文件 ID: {sid} ...", end="", flush=True)
            
            args = json.dumps([[[sid]]])
            response = self._execute_rpc_with_xsrf_retry(rpc_id, [args], source_path=source_path)
            
            if response.status_code == 200:
                print(" ✅ 成功")
                success_count += 1
            else:
                print(f" ❌ 失败 (状态码: {response.status_code})")
                
        print(f"\n🎉 批量删除完成！成功删除 {success_count}/{total} 个文件。")


def sources_loop(client: NotebookLMClient, notebook_info: dict):
    """Handles source listings and operations for the selected notebook."""
    # Fetch sources dynamically for this notebook
    sources = client.list_sources()
    
    while True:
        print("\n" + "=" * 60)
        print(f"       管理笔记本: {notebook_info['title']}")
        print(f"       ID: {notebook_info['id']}")
        print("=" * 60)
        
        if not sources:
            print("📄 该 Notebook 下没有任何 Source 文档。")
            print("=" * 60)
            print("💡 输入 \"back\" 返回笔记本选择菜单，输入 \"exit\" 退出。")
            user_input = input("请输入您的指令: ").strip().lower()
            if user_input == "back":
                break
            elif user_input == "exit":
                print("已安全退出程序。")
                sys.exit(0)
            else:
                continue
                
        for i, src in enumerate(sources, start=1):
            print(f"[{i:2d}] 📄 {src['title']}")
            print(f"     ID: {src['id']}")
            print("-" * 60)
            
        print("\n💡 操作指令说明:")
        print(" 1. 输入单个数字（例如: 3）选择删除该文件。")
        print(" 2. 输入多个数字并用英文逗号隔开（例如: 1,3,5）批量选择删除。")
        print(" 3. 输入 \"all\" 全选删除该笔记本下的所有文件。")
        print(" 4. 输入 \"back\" 返回上级笔记本选择菜单。")
        print(" 5. 输入 \"exit\" 退出程序。")
        print("=" * 60)
        
        user_input = input("请输入您的指令或要删除的序号: ").strip().lower()
        
        if user_input == "exit":
            print("已安全退出程序. ")
            sys.exit(0)
            
        if user_input == "back":
            break
            
        if user_input == "all":
            selected_sources = sources
        else:
            try:
                indexes = [int(x.strip()) for x in user_input.split(",") if x.strip()]
                invalid_indexes = [idx for idx in indexes if idx < 1 or idx > len(sources)]
                if invalid_indexes:
                    print(f"❌ 错误：序号 {invalid_indexes} 超出了有效范围，请重新输入。")
                    continue
                selected_sources = [sources[idx - 1] for idx in indexes]
            except ValueError:
                print("❌ 错误：输入格式无法识别，请输入数字、逗号、\"all\"、\"back\" 或 \"exit\"。")
                continue
                
        if not selected_sources:
            print("⚠️ 未选中任何文件！")
            continue
            
        # Re-verify deletion
        print("\n⚠️ 您已选择从笔记本中永久删除以下文件:")
        for idx, src in enumerate(selected_sources, start=1):
            print(f"  {idx}. {src['title']} ({src['id']})")
            
        confirm = input(f"\n🔥 确定要从该笔记本中永久删除这 {len(selected_sources)} 个文件吗？此操作无法撤销！(yes/no): ").strip().lower()
        if confirm in ["yes", "y"]:
            ids_to_delete = [src["id"] for src in selected_sources]
            client.delete_sources(ids_to_delete)
            # Update local list after success
            sources = client.list_sources()
        else:
            print("❌ 操作已取消。")


def run_interactive_cli():
    """Starts the dynamic interactive CLI menu."""
    try:
        client = NotebookLMClient()
    except Exception as e:
        print(f"\n❌ 初始化错误: {e}")
        return

    while True:
        # Step 1: List and select Notebooks
        notebooks = client.list_notebooks()
        if not notebooks:
            print("未找到任何 Notebook，请检查 config.json 或 cookie.txt 中的 Cookie 是否正确且有效。")
            break
            
        print("\n" + "=" * 60)
        print("                  Google NotebookLM 笔记本选择菜单")
        print("=" * 60)
        for i, nb in enumerate(notebooks, start=1):
            print(f"[{i:2d}] 📓 {nb['title']}")
            print(f"     ID: {nb['id']} ({nb['sources_count']} 个文档源)")
            print("-" * 60)
        print("\n💡 操作指令说明:")
        print(" 1. 输入对应数字序号进入该笔记本进行管理与批量删除。")
        print(" 2. 输入 \"exit\" 退出程序。")
        print("=" * 60)
        
        nb_input = input("请选择要管理的笔记本序号: ").strip().lower()
        if nb_input == "exit":
            print("已安全退出程序。")
            break
            
        try:
            nb_idx = int(nb_input)
            if nb_idx < 1 or nb_idx > len(notebooks):
                print(f"❌ 错误：序号 {nb_idx} 超出范围。")
                continue
            selected_nb = notebooks[nb_idx - 1]
        except ValueError:
            print("❌ 错误：无效的输入。")
            continue
            
        # Set the active notebook ID
        client.notebook_id = selected_nb["id"]
        
        # Step 2: Manage sources inside the selected notebook
        sources_loop(client, selected_nb)


if __name__ == "__main__":
    run_interactive_cli()
