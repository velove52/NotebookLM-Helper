import os
import sys
import json
import re
import ssl
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any
import requests
import urllib3
from requests.adapters import HTTPAdapter

# 禁用 SSL 警告以保持控制台整洁
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 确保 Windows 控制台正确支持 UTF-8，防止编码崩坏
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class TLSAdapter(HTTPAdapter):
    """自定义 TLS 适配器以解决 [SSL: UNEXPECTED_EOF_WHILE_READING] 握手错误
    
    能够完美解决由 Clash 等本地 HTTP/2 代理或特定网络环境引发的连接断开问题。
    """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class NotebookLMUploaderClient:
    """NotebookLM 智能上传客户端
    
    集成动态 XSRF 令牌自愈、Cookie 智能裁剪及 Google 分块可恢复上传协议 (Resumable Upload)
    """
    
    # 精简必须保留的 Google 核心鉴权 Cookie 键，自动过滤冗余 cookie 规避 Clash 代理握手限制
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
        
        self.base_query_params: str = ""
        self.cookie_header: str = ""
        self.headers: Dict[str, str] = {}
        self.xsrf_token: Optional[str] = None
        
        self.session = requests.Session()
        self.session.mount("https://", TLSAdapter())
        
        self.rclone_path = os.path.join(script_dir, "rclone.conf")
        self.rclone_config: Dict[str, str] = {}
        
        self.load_config()
        self.load_rclone_config()

    def _prune_cookie_string(self, cookie_string: str) -> str:
        """解析 Cookie 字符串，仅保留核心鉴权字段，缩减标头体积"""
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
        """智能解析 cookie.txt 或是 json 格式的 cookies 数据"""
        raw_content = raw_content.strip()
        if not raw_content:
            return ""
            
        if raw_content.lower().startswith("cookie:"):
            raw_content = raw_content[7:].strip()
            
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, list):
                pruned_list = []
                for c in parsed:
                    if isinstance(c, dict) and 'name' in c and 'value' in c:
                        if c['name'] in self.ESSENTIAL_COOKIE_KEYS:
                            pruned_list.append(f"{c['name']}={c['value']}")
                return "; ".join(pruned_list)
            elif isinstance(parsed, dict):
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
                    return "; ".join([f"{k}={v}" for k, v in parsed.items() if k in self.ESSENTIAL_COOKIE_KEYS])
        except json.JSONDecodeError:
            return self._prune_cookie_string(raw_content)
        return raw_content

    def load_config(self) -> None:
        """载入配置文件与凭证"""
        config = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                try:
                    config = json.load(f)
                except Exception as e:
                    print(f"⚠️ 解析 config.json 失败: {e}，将尝试其他凭证。")
            
        self.base_query_params = config.get("base_query_params", "bl=boq_labs-tailwind-frontend_20260527.15_p0&hl=en&rt=c")
        
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
                "请在脚本同级目录下创建 'cookie.txt' 并粘贴您的 Cookie。"
            )
        
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

    def load_rclone_config(self) -> None:
        """从 rclone.conf 中读取 gdriver 配置"""
        if os.path.exists(self.rclone_path):
            import configparser
            config = configparser.ConfigParser()
            try:
                config.read(self.rclone_path, encoding="utf-8")
                if "gdriver" in config:
                    self.rclone_config = dict(config["gdriver"])
            except Exception as e:
                print(f"⚠️ 读取 rclone.conf 失败: {e}")

    def save_rclone_config(self) -> None:
        """把更新后的 Token 写回 rclone.conf"""
        if not os.path.exists(self.rclone_path):
            return
        import configparser
        config = configparser.ConfigParser()
        try:
            config.read(self.rclone_path, encoding="utf-8")
            if "gdriver" in config:
                config["gdriver"]["token"] = self.rclone_config["token"]
                with open(self.rclone_path, "w", encoding="utf-8") as f:
                    config.write(f)
        except Exception as e:
            print(f"⚠️ 保存 rclone.conf 失败: {e}")

    def refresh_gdrive_token(self) -> Optional[str]:
        """使用 refresh_token 智能刷新 Google Drive access_token"""
        if not self.rclone_config:
            return None
            
        client_id = self.rclone_config.get("client_id")
        client_secret = self.rclone_config.get("client_secret")
        token_str = self.rclone_config.get("token")
        
        if not (client_id and client_secret and token_str):
            return None
            
        try:
            token_json = json.loads(token_str)
            refresh_token = token_json.get("refresh_token")
            if not refresh_token:
                return token_json.get("access_token")
                
            # 发送刷新令牌请求
            payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            res = requests.post("https://oauth2.googleapis.com/token", data=payload, timeout=10)
            if res.status_code == 200:
                data = res.json()
                new_access_token = data.get("access_token")
                if new_access_token:
                    token_json["access_token"] = new_access_token
                    if "expires_in" in data:
                        token_json["expiry"] = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() + data["expires_in"]))
                    self.rclone_config["token"] = json.dumps(token_json)
                    self.save_rclone_config()
                    return new_access_token
            return token_json.get("access_token")
        except Exception as e:
            print(f"⚠️ 刷新 Google Drive Token 失败: {e}")
            try:
                return json.loads(token_str).get("access_token")
            except:
                return None

    def list_gdrive_files(self, q: str = "trashed = false", page_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出 Google Drive 内的文件列表"""
        access_token = self.refresh_gdrive_token()
        if not access_token:
            return []
            
        url = "https://www.googleapis.com/drive/v3/files"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "pageSize": 50,
            "fields": "nextPageToken, files(id, name, mimeType, size)",
            "q": q,
            "orderBy": "folder, name"
        }
        if page_token:
            params["pageToken"] = page_token
            
        try:
            res = requests.get(url, headers=headers, params=params, verify=False, timeout=15)
            if res.status_code == 200:
                return res.json().get("files", [])
            else:
                print(f"❌ 获取网盘列表失败: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"❌ 访问 Google Drive 发生异常: {e}")
        return []

    def download_gdrive_file(self, file_id: str, local_path: str) -> bool:
        """从 Google Drive 下载二进制文件到本地临时路径"""
        access_token = self.refresh_gdrive_token()
        if not access_token:
            return False
            
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # 首先检查文件的大小，以便于进度显示
        try:
            meta_res = requests.get(url, headers=headers, params={"fields": "size,name"}, verify=False, timeout=10)
            if meta_res.status_code != 200:
                print(f"❌ 获取文件元数据失败: {meta_res.status_code}")
                return False
            meta = meta_res.json()
            file_size = int(meta.get("size", 0))
            file_name = meta.get("name", "downloaded_file")
        except Exception as e:
            print(f"⚠️ 无法获取文件大小: {e}")
            file_size = 0
            file_name = "downloaded_file"

        print(f"⬇️ 正在从 Google Drive 下载 '{file_name}' ({file_size/1024/1024:.2f} MB) ...", end="", flush=True)
        
        download_url = f"{url}?alt=media"
        try:
            with requests.get(download_url, headers=headers, stream=True, verify=False, timeout=60) as r:
                if r.status_code != 200:
                    print(f" ❌ 下载失败 (HTTP {r.status_code})")
                    return False
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
            print(" ✅ 下载完成")
            return True
        except Exception as e:
            print(f" ❌ 下载异常: {e}")
            if os.path.exists(local_path):
                os.remove(local_path)
            return False

    def _send_rpc(self, rpc_id: str, params: list, source_path: str = "/") -> requests.Response:
        """发送 batchexecute 请求"""
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
                return self.session.post(url, data=payload, headers=self.headers, verify=False, timeout=12)
            except (requests.exceptions.RequestException, ssl.SSLError) as e:
                last_err = e
                time.sleep(1)
                
        raise last_err

    def _execute_rpc_with_xsrf_retry(self, rpc_id: str, params: list, source_path: str = "/") -> requests.Response:
        """发送 RPC 请求并在 XSRF 过期时进行重试自愈"""
        response = self._send_rpc(rpc_id, params, source_path)
        
        if response.status_code == 400:
            match = re.search(r'"xsrf"\s*,\s*"([^"]+)"', response.text)
            if match:
                self.xsrf_token = match.group(1)
                response = self._send_rpc(rpc_id, params, source_path)
                
        if ('[["e",4' in response.text or '["e",4' in response.text) and f'"{rpc_id}"' not in response.text:
            print("\n❌ 身份凭证已失效（Google 会话已过期或已被注销）！")
            print("💡 请重新在浏览器中登录 NotebookLM 并更新 'cookie.txt'。")
                
        return response

    def _extract_first_string(self, data) -> Optional[str]:
        """递归提取嵌套数据中的第一个字符串值"""
        if isinstance(data, str):
            return data
        if isinstance(data, list):
            for item in data:
                result = self._extract_first_string(item)
                if result:
                    return result
        return None

    def list_notebooks(self) -> List[Dict[str, Any]]:
        """获取笔记本列表"""
        rpc_id = "wXbhsf"
        params = [None, 1, None, [2]]
        
        response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path="/")
        if response.status_code != 200:
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
                    
                    sources_list = nb[1]
                    sources_count = len(sources_list) if isinstance(sources_list, list) else 0
                    
                    if notebook_id:
                        parsed_notebooks.append({
                            "title": title,
                            "id": notebook_id,
                            "sources_count": sources_count
                        })
                return parsed_notebooks
        except Exception:
            pass
        return []

    def create_notebook(self, title: str) -> Optional[str]:
        """创建全新笔记本并返回 ID"""
        rpc_id = "CCqFvf"
        params = [
            title, None, None, [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        print(f"📘 正在创建全新笔记本: '{title}' ...", end="", flush=True)
        response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path="/")
        
        if response.status_code != 200:
            print(f" ❌ 失败 (HTTP 状态码: {response.status_code})")
            return None
            
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
                if result_str:
                    result_list = json.loads(result_str)
                    if len(result_list) > 2:
                        notebook_id = result_list[2]
                        print(f" ✅ 成功! ID: {notebook_id}")
                        return notebook_id
        except Exception as e:
            print(f" ❌ 解析新建 ID 失败: {e}")
        return None

    def add_source_url(self, notebook_id: str, url: str) -> Optional[str]:
        """添加 URL 网页/YouTube 链接源"""
        source_data = [None, None, [url], None, None, None, None, None, None, None, 1]
        params = [
            [source_data], notebook_id, [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        
        for rpc_id in ["izAoDd", "ozz5Z"]:
            try:
                response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path=f"/notebook/{notebook_id}")
                if response.status_code == 200:
                    text = response.text
                    if text.startswith(")]}'"):
                        text = text[4:].strip()
                    lines = text.split('\n')
                    json_data = None
                    for line in lines:
                        if line.strip().startswith('[['):
                            json_data = json.loads(line.strip())
                            break
                    if json_data:
                        result_str = json_data[0][2]
                        if result_str:
                            result_list = json.loads(result_str)
                            source_id = result_list[0][0][0][0]
                            return source_id
            except Exception:
                continue
        return None

    def add_source_text(self, notebook_id: str, title: str, text_content: str) -> Optional[str]:
        """添加纯文本/Copied Text 数据源"""
        source_data = [None, [title, text_content], None, 2, None, None, None, None, None, None, 1]
        params = [
            [source_data], notebook_id, [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        
        for rpc_id in ["izAoDd", "ozz5Z"]:
            try:
                response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path=f"/notebook/{notebook_id}")
                if response.status_code == 200:
                    text = response.text
                    if text.startswith(")]}'"):
                        text = text[4:].strip()
                    lines = text.split('\n')
                    json_data = None
                    for line in lines:
                        if line.strip().startswith('[['):
                            json_data = json.loads(line.strip())
                            break
                    if json_data:
                        result_str = json_data[0][2]
                        if result_str:
                            result_list = json.loads(result_str)
                            source_id = result_list[0][0][0][0]
                            return source_id
            except Exception:
                continue
        return None

    def parse_drive_url(self, url: str) -> tuple[Optional[str], Optional[str]]:
        """从 Google Drive / Docs / Slides / Sheets 链接中自动解析出 File ID 和对应的 MIME 类型"""
        url = url.strip()
        # 1. 匹配 Docs: /document/d/<id>
        doc_match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', url)
        if doc_match:
            return doc_match.group(1), "application/vnd.google-apps.document"
            
        # 2. 匹配 Slides: /presentation/d/<id>
        slides_match = re.search(r'/presentation/d/([a-zA-Z0-9_-]+)', url)
        if slides_match:
            return slides_match.group(1), "application/vnd.google-apps.presentation"
            
        # 3. 匹配 Sheets: /spreadsheets/d/<id>
        sheets_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
        if sheets_match:
            return sheets_match.group(1), "application/vnd.google-apps.spreadsheet"
            
        # 4. 匹配通用 Drive 文件: /file/d/<id> 或 ?id=<id>
        file_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
        if file_match:
            return file_match.group(1), "application/pdf"
            
        open_match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if open_match:
            return open_match.group(1), "application/pdf"
            
        # 如果长度符合典型 ID 长度，直接当作 ID 处理
        if re.match(r'^[a-zA-Z0-9_-]{25,}$', url):
            return url, None
            
        return None, None

    def add_source_drive(self, notebook_id: str, file_id: str, title: str, mime_type: str = "application/vnd.google-apps.document") -> Optional[str]:
        """添加 Google Drive 文件 (如 Google Docs, Slides, Sheets 或 Drive 中的 PDF)
        
        支持 izAoDd / ozz5Z 双 RPC 自动回退机制。
        """
        source_data = [
            [file_id, mime_type, 1, title],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            1,
        ]
        params = [
            [source_data], notebook_id, [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        
        for rpc_id in ["izAoDd", "ozz5Z"]:
            try:
                response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path=f"/notebook/{notebook_id}")
                if response.status_code == 200:
                    text = response.text
                    if text.startswith(")]}'"):
                        text = text[4:].strip()
                    lines = text.split('\n')
                    json_data = None
                    for line in lines:
                        if line.strip().startswith('[['):
                            json_data = json.loads(line.strip())
                            break
                    if json_data:
                        result_str = json_data[0][2]
                        if result_str:
                            result_list = json.loads(result_str)
                            source_id = result_list[0][0][0][0]
                            return source_id
            except Exception:
                continue
        return None

    def upload_file(self, notebook_id: str, file_path: str) -> Optional[str]:
        """使用 Google 分块可恢复协议上传本地二进制文件(如 PDF, docx, mp3, png 等)"""
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            print(f"❌ 找不到本地文件: {file_path}")
            return None
            
        filename = file_path_obj.name
        file_size = file_path_obj.stat().st_size
        
        # Step 1: 注册文件元数据并产生 source_id
        rpc_id = "o4cbdc"
        params = [
            [[filename]], notebook_id, [2],
            [1, None, None, None, None, None, None, None, None, None, [1]],
        ]
        
        print(f"📦 [1/3] 正在注册文件元数据: '{filename}' ...", end="", flush=True)
        response = self._execute_rpc_with_xsrf_retry(rpc_id, params, source_path=f"/notebook/{notebook_id}")
        
        if response.status_code != 200:
            print(f" ❌ 失败 (状态码: {response.status_code})")
            return None
            
        text = response.text
        if text.startswith(")]}'"):
            text = text[4:].strip()
            
        source_id = None
        try:
            lines = text.split('\n')
            json_data = None
            for line in lines:
                if line.strip().startswith('[['):
                    json_data = json.loads(line.strip())
                    break
            if json_data:
                result_str = json_data[0][2]
                if result_str:
                    result_list = json.loads(result_str)
                    source_id = self._extract_first_string(result_list)
        except Exception as e:
            print(f" ❌ 解析注册响应异常: {e}")
            return None
            
        if not source_id:
            print(" ❌ 无法获得 source_id")
            return None
            
        print(f" ✅ 成功 (ID: {source_id})")
        
        # Step 2: 握手创建 resumable upload 会话通道
        upload_url_init = "https://notebooklm.google.com/upload/_/?authuser=0"
        upload_meta = json.dumps({
            "PROJECT_ID": notebook_id,
            "SOURCE_NAME": filename,
            "SOURCE_ID": source_id,
        })
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": "https://notebooklm.google.com",
            "Referer": "https://notebooklm.google.com/",
            "User-Agent": self.headers["User-Agent"],
            "Cookie": self.cookie_header,
            "x-goog-authuser": "0",
            "x-goog-upload-command": "start",
            "x-goog-upload-header-content-length": str(file_size),
            "x-goog-upload-protocol": "resumable",
        }
        
        print("🚀 [2/3] 正在与 Google 握手建立上传通道 ...", end="", flush=True)
        try:
            res_init = self.session.post(upload_url_init, data=upload_meta.encode("utf-8"), headers=headers, verify=False, timeout=15)
            if res_init.status_code != 200:
                print(f" ❌ 失败 (状态码: {res_init.status_code})")
                return None
            upload_url = res_init.headers.get("x-goog-upload-url")
        except Exception as e:
            print(f" ❌ 请求上传通道异常: {e}")
            return None
            
        if not upload_url:
            print(" ❌ 握手失败，未得到上传通道链接")
            return None
            
        print(" ✅ 成功")
        
        # Step 3: 开始数据流传输并最终确认
        upload_headers = {
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Content-Length": str(file_size),
            "Origin": "https://notebooklm.google.com",
            "Referer": "https://notebooklm.google.com/",
            "User-Agent": self.headers["User-Agent"],
            "Cookie": self.cookie_header,
            "x-goog-authuser": "0",
            "x-goog-upload-command": "upload, finalize",
            "x-goog-upload-offset": "0",
        }
        
        print(f"📤 [3/3] 正在流式传输文件二进制 ({file_size / 1024 / 1024:.2f} MB) ...", end="", flush=True)
        try:
            with open(file_path, "rb") as f:
                res_upload = self.session.post(upload_url, data=f, headers=upload_headers, verify=False, timeout=90)
                if res_upload.status_code == 200:
                    print(" ✅ 上传成功！")
                    return source_id
                else:
                    print(f" ❌ 传输失败 (HTTP 状态码: {res_upload.status_code})")
                    return None
        except Exception as e:
            print(f" ❌ 传输发生网络异常: {e}")
            return None


def show_title():
    print("""
============================================================
              Google NotebookLM Source 智能上传器
============================================================
    """)


def handle_interactive():
    """交互式引导模式"""
    show_title()
    try:
        client = NotebookLMUploaderClient()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return

    # 1. 选择或创建 Notebook
    print("正在加载您的笔记本列表...")
    notebooks = client.list_notebooks()
    if not notebooks:
        print("❌ 未获取到任何 Notebook。请确保 'cookie.txt' 内凭证正确且未失效。")
        return

    print("\n可用笔记本列表:")
    print("-" * 60)
    for i, nb in enumerate(notebooks, start=1):
        print(f"[{i:2d}] 📓 {nb['title']} ({nb['sources_count']} 个源)")
        print(f"     ID: {nb['id']}")
        print("-" * 60)
    print(f"[{len(notebooks)+1:2d}] ➕ 创建全新笔记本 (Create New Notebook)")
    print("-" * 60)

    try:
        choice_input = input("请选择您的操作序号: ").strip()
        choice = int(choice_input)
        if choice < 1 or choice > len(notebooks) + 1:
            print("❌ 错误：输入序号超出有效范围。")
            return
    except ValueError:
        print("❌ 错误：输入格式不合法。")
        return

    notebook_id = ""
    if choice == len(notebooks) + 1:
        new_title = input("\n请输入新笔记本的名称: ").strip()
        if not new_title:
            print("❌ 错误：笔记本名称不能为空。")
            return
        notebook_id = client.create_notebook(new_title)
        if not notebook_id:
            return
    else:
        selected_nb = notebooks[choice - 1]
        notebook_id = selected_nb["id"]
        print(f"\n已选择笔记本: '{selected_nb['title']}' ({notebook_id})")

    # 2. 选择上传源类型
    print("\n请选择要上传/添加的 Source 类型:")
    print(" [1] 📄 上传本地文件 (PDF, Docx, TXT, MD, Mp3, PNG 等)")
    print(" [2] 🔗 添加网页链接 (Web URL / YouTube URL)")
    print(" [3] 📝 添加纯文本/复制文本 (Pasted Text)")
    print(" [4] 🤖 粘贴 Google Drive 文件链接/ID (自动解析导入)")
    print(" [5] ☁️ 浏览并选择 Google Drive 网盘文件 (直接从云盘导入)")
    
    type_input = input("请输入类型序号: ").strip()
    if type_input == "1":
        file_path = input("\n请输入本地文件的完整路径: ").strip()
        # 清除 Windows 复制路径时可能带有的双引号
        file_path = file_path.replace('"', '').replace("'", "")
        if not file_path:
            print("❌ 错误：文件路径不能为空。")
            return
        client.upload_file(notebook_id, file_path)
    elif type_input == "2":
        url = input("\n请输入网页或 YouTube 的完整 URL: ").strip()
        if not url:
            print("❌ 错误：URL 不能为空。")
            return
        print(f"🔗 正在添加链接: {url} ... ", end="", flush=True)
        source_id = client.add_source_url(notebook_id, url)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
    elif type_input == "3":
        title = input("\n请输入文本源的标题: ").strip()
        if not title:
            print("❌ 错误：标题不能为空。")
            return
        print("请输入源文本内容 (按 Ctrl+Z 并在 Windows 上回车，或 Linux 上按 Ctrl+D 提交多行内容):")
        content = sys.stdin.read().strip()
        if not content:
            print("❌ 错误：内容不能为空。")
            return
        print(f"📝 正在提交文本源 ... ", end="", flush=True)
        source_id = client.add_source_text(notebook_id, title, content)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
    elif type_input == "4":
        user_input = input("\n请输入 Google Drive 的文件链接 (URL) 或文件 ID (File ID): ").strip()
        if not user_input:
            print("❌ 错误：输入不能为空。")
            return
            
        file_id, mime_type = client.parse_drive_url(user_input)
        if not file_id:
            print("❌ 错误：无法从输入中解析出有效的 Google Drive 文件 ID，请检查链接或输入！")
            return
            
        title = input("请输入此源的显示标题 (Title): ").strip()
        if not title:
            print("❌ 错误：标题不能为空。")
            return
            
        if mime_type:
            friendly_names = {
                "application/vnd.google-apps.document": "Google Docs (文档)",
                "application/vnd.google-apps.presentation": "Google Slides (幻灯片)",
                "application/vnd.google-apps.spreadsheet": "Google Sheets (表格)",
                "application/pdf": "PDF/其他云盘文件"
            }
            print(f"✨ 自动检测到云盘文件类型: {friendly_names.get(mime_type, mime_type)}")
        else:
            print("\n请选择 Google Drive 的文件类型:")
            print(" [1] 📄 Google Docs (谷歌文档) - 默认")
            print(" [2] 📊 Google Slides (幻灯片)")
            print(" [3] 📈 Google Sheets (电子表格)")
            print(" [4] 📕 PDF / 其他 Drive 内文件")
            
            mime_choice = input("请输入类型序号 [默认 1]: ").strip()
            mime_map = {
                "1": "application/vnd.google-apps.document",
                "2": "application/vnd.google-apps.presentation",
                "3": "application/vnd.google-apps.spreadsheet",
                "4": "application/pdf"
            }
            mime_type = mime_map.get(mime_choice, "application/vnd.google-apps.document")
        
        print(f"🤖 正在从 Google Drive 导入 '{title}' ... ", end="", flush=True)
        source_id = client.add_source_drive(notebook_id, file_id, title, mime_type)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
    elif type_input == "5":
        if not client.rclone_config:
            print("\n❌ 未检测到有效的 'rclone.conf' 配置文件，请参照 README 在脚本目录下提供该文件！")
            return
            
        print("\n☁️ 正在读取您的 Google Drive 网盘根目录 ...")
        current_folder_id = "root"
        folder_path = ["Root"]
        folder_history = []  # 保存 [(folder_id, folder_name)]
        
        while True:
            # 列出当前文件夹下的内容
            q = f"'{current_folder_id}' in parents and trashed = false"
            files = client.list_gdrive_files(q=q)
            
            print(f"\n📂 当前路径: {' / '.join(folder_path)}")
            print("-" * 70)
            if not files:
                print("   (空文件夹)")
            else:
                for idx, f in enumerate(files, start=1):
                    is_folder = f.get("mimeType") == "application/vnd.google-apps.folder"
                    prefix = "📁 [文件夹]" if is_folder else "📄 [文件]"
                    size_str = ""
                    if not is_folder and "size" in f:
                        size_mb = int(f["size"]) / 1024 / 1024
                        size_str = f" ({size_mb:.2f} MB)"
                    print(f"[{idx:2d}] {prefix} {f['name']}{size_str}")
            
            print("-" * 70)
            back_idx = len(files) + 1
            exit_idx = len(files) + 2
            
            if current_folder_id != "root":
                print(f"[{back_idx:2d}] ⬅️ 返回上级目录")
            print(f"[{exit_idx:2d}] ❌ 退出网盘浏览")
            print("-" * 70)
            
            sel_input = input("请输入您要操作的序号: ").strip()
            try:
                sel = int(sel_input)
                if sel == exit_idx:
                    print("已退出网盘浏览。")
                    return
                elif current_folder_id != "root" and sel == back_idx:
                    # 返回上级
                    current_folder_id, folder_name = folder_history.pop()
                    folder_path.pop()
                    continue
                elif 1 <= sel <= len(files):
                    selected = files[sel - 1]
                    is_folder = selected.get("mimeType") == "application/vnd.google-apps.folder"
                    if is_folder:
                        # 进入子文件夹
                        folder_history.append((current_folder_id, folder_path[-1]))
                        current_folder_id = selected["id"]
                        folder_path.append(selected["name"])
                        continue
                    else:
                        # 选中文件，开始导入！
                        file_id = selected["id"]
                        name = selected["name"]
                        mime = selected["mimeType"]
                        
                        print(f"\n🎯 选中文件: '{name}'")
                        confirm = input("确认导入该文件到当前 Notebook 吗？(Y/N) [默认 Y]: ").strip().lower()
                        if confirm in ("n", "no"):
                            continue
                            
                        # 区分云端原生格式（Google Docs, Slides, Sheets）与二进制文件（PDF/docx/mp3等）
                        cloud_formats = {
                            "application/vnd.google-apps.document",
                            "application/vnd.google-apps.presentation",
                            "application/vnd.google-apps.spreadsheet"
                        }
                        
                        if mime in cloud_formats:
                            print(f"🤖 检测到谷歌云端原生文档，正在直接触发云端导入...")
                            source_id = client.add_source_drive(notebook_id, file_id, name, mime)
                            if source_id:
                                print(f"✅ 成功! (ID: {source_id})")
                            else:
                                print("❌ 导入失败")
                        else:
                            print(f"📥 检测到二进制文件，将自动执行 [云端下载 -> 流式直传] ...")
                            # 创建临时文件
                            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
                            os.makedirs(temp_dir, exist_ok=True)
                            temp_path = os.path.join(temp_dir, name)
                            
                            success = client.download_gdrive_file(file_id, temp_path)
                            if success:
                                print(f"📤 正在启动 3-Step Resumable Upload 协议，流传到 NotebookLM...")
                                source_id = client.upload_file(notebook_id, temp_path)
                                if source_id:
                                    print(f"✅ 上传导入成功! (ID: {source_id})")
                                else:
                                    print("❌ 传输阶段失败")
                                # 删除临时文件
                                if os.path.exists(temp_path):
                                    os.remove(temp_path)
                            else:
                                print("❌ 下载阶段失败")
                        return
                else:
                    print("❌ 输入序号超出有效范围，请重新输入。")
            except ValueError:
                print("❌ 格式不合法，请输入数字序号。")
    else:
        print("❌ 错误：无效的类型序号。")


def main():
    parser = argparse.ArgumentParser(
        prog="notebooklm_uploader",
        description="Google NotebookLM 极速 Source 上传工具",
    )
    parser.add_argument("--to", metavar="NOTEBOOK_ID", help="指定要上传的目标笔记本 ID。若不指定则启动交互引导菜单")
    parser.add_argument("--file", metavar="FILE_PATH", help="上传本地文件 (如 PDF, Docx, MD, MP3 等)")
    parser.add_argument("--url", metavar="URL", help="添加网页链接 (如 https://example.com 或 YouTube 链接)")
    parser.add_argument("--text", metavar="TEXT", help="直接上传纯文本内容，需同时搭配 --title 参数使用")
    parser.add_argument("--title", metavar="TITLE", help="指定源的标题 (用于 --text 纯文本和 --gdrive 云端文档)")
    parser.add_argument("--gdrive", metavar="DRIVE_FILE_ID", help="添加 Google Drive 云端文件 (Google Docs, Slides, Sheets 或 PDF)，推荐同时搭配 --title")
    parser.add_argument("--mime", metavar="MIME_TYPE", default="application/vnd.google-apps.document", help="指定 Drive 云端文件的 MIME 类型 (默认: application/vnd.google-apps.document 为 Google Docs)")
    args = parser.parse_args()

    # 没有提供目标笔记本 ID，或是没有任何具体上传选项时，启动保姆级交互菜单
    if not args.to and not args.file and not args.url and not args.text and not args.gdrive:
        handle_interactive()
        return

    # CLI 传参模式
    if not args.to:
        print("❌ 错误：使用命令模式时，必须使用 --to <NOTEBOOK_ID> 指定目标笔记本。")
        sys.exit(1)

    try:
        client = NotebookLMUploaderClient()
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

    notebook_id = args.to

    if args.file:
        client.upload_file(notebook_id, args.file)
    elif args.url:
        print(f"🔗 正在添加链接: {args.url} ... ", end="", flush=True)
        source_id = client.add_source_url(notebook_id, args.url)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
            sys.exit(1)
    elif args.text:
        title = args.title or "Pasted Text Source"
        print(f"📝 正在添加文本源: '{title}' ... ", end="", flush=True)
        source_id = client.add_source_text(notebook_id, title, args.text)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
            sys.exit(1)
    elif args.gdrive:
        file_id, detected_mime = client.parse_drive_url(args.gdrive)
        if not file_id:
            print("❌ 错误：无法从 --gdrive 参数中解析出有效的 Google Drive 文件 ID，请检查链接或输入！")
            sys.exit(1)
        mime_type = args.mime if args.mime != "application/vnd.google-apps.document" else (detected_mime or args.mime)
        title = args.title or f"Drive Source {file_id}"
        print(f"🤖 正在从 Google Drive 导入 '{title}' ... ", end="", flush=True)
        source_id = client.add_source_drive(notebook_id, file_id, title, mime_type)
        if source_id:
            print(f"✅ 成功! (ID: {source_id})")
        else:
            print("❌ 失败")
            sys.exit(1)
    else:
        print("❌ 错误：请选择并传递一种上传方式: --file, --url, --text, 或 --gdrive。")
        sys.exit(1)


if __name__ == "__main__":
    main()
