
import requests
import json
import time
from typing import Generator, Optional, Dict, Any, List
from dataclasses import dataclass
from pow_solver import default_solver


@dataclass
class ChatEvent:
    event_type: str
    data: Any


class DeepSeekClient:
    BASE_URL = "https://chat.deepseek.com"
    HIF_URL = "https://hif-leim.deepseek.com/query"

    def __init__(self, token: str):
        self.token = token.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
            "x-client-platform": "web",
            "x-client-version": "2.4.0",
            "x-client-locale": "en_US",
            "x-client-timezone-offset": "25200",
            "x-app-version": "20241129.0",
            "x-client-bundle-id": "com.deepseek.chat",
        })
        self._refresh_hif_token()

    def _refresh_hif_token(self):
        """Fetches dynamic anti-bot token if available."""
        try:
            r = self.session.get(self.HIF_URL, timeout=4)
            if r.status_code == 200:
                val = r.json().get("data", {}).get("biz_data", {}).get("value")
                if val:
                    self.session.headers["x-hif-leim"] = val
        except Exception:
            pass

    def get_user_info(self) -> Dict[str, Any]:
        """Fetches current logged-in user profile."""
        r = self.session.get(f"{self.BASE_URL}/api/v0/users/current")
        if r.status_code == 401:
            raise PermissionError("Token không hợp lệ hoặc đã hết hạn (401 Unauthorized).")
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lỗi API: {data.get('msg')}")
        return data.get("data", {}).get("biz_data", {})

    def create_session(self, agent: str = "chat") -> str:
        """Creates a new chat session and returns session_id."""
        r = self.session.post(f"{self.BASE_URL}/api/v0/chat_session/create", json={"agent": agent})
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Không thể tạo phiên chat: {data.get('msg')}")
        session_id = data["data"]["biz_data"]["chat_session"]["id"]
        return session_id

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists recent chat sessions."""
        params = {"lte_cursor.pinned": "false"}
        r = self.session.get(f"{self.BASE_URL}/api/v0/chat_session/fetch_page", params=params)
        r.raise_for_status()
        data = r.json()
        sessions = data.get("data", {}).get("biz_data", {}).get("chat_sessions", [])
        return sessions[:limit]

    def create_and_solve_pow(self, target_path: str = "/api/v0/chat/completion") -> str:
        """Requests PoW challenge and returns solved Base64 header string."""
        r = self.session.post(
            f"{self.BASE_URL}/api/v0/chat/create_pow_challenge",
            json={"target_path": target_path}
        )
        r.raise_for_status()
        res_json = r.json()
        challenge_data = res_json.get("data", {}).get("biz_data", {}).get("challenge")
        if not challenge_data:
            raise RuntimeError("Không nhận được challenge từ máy chủ DeepSeek.")
        return default_solver.solve_to_header(challenge_data)

    def stream_chat(
        self,
        prompt: str,
        session_id: str,
        parent_message_id: Optional[int] = None,
        thinking_enabled: bool = True,
        search_enabled: bool = False,
    ) -> Generator[ChatEvent, None, None]:
        """
        Sends message to DeepSeek and yields streaming events:
        - ChatEvent("think_start", None)
        - ChatEvent("think_chunk", str)
        - ChatEvent("think_done", elapsed_secs)
        - ChatEvent("resp_start", None)
        - ChatEvent("resp_chunk", str)
        - ChatEvent("title", str)
        - ChatEvent("finish", {"tokens": int, "response_message_id": int})
        """
        pow_header = self.create_and_solve_pow("/api/v0/chat/completion")

        headers = {
            "x-ds-pow-response": pow_header,
            "Referer": f"{self.BASE_URL}/a/chat/s/{session_id}",
        }

        payload = {
            "chat_session_id": session_id,
            "parent_message_id": parent_message_id,
            "model_type": "default",
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking_enabled,
            "search_enabled": search_enabled,
            "action": None,
            "preempt": False
        }

        r = self.session.post(
            f"{self.BASE_URL}/api/v0/chat/completion",
            json=payload,
            headers=headers,
            stream=True,
            timeout=120
        )

        if r.status_code != 200:
            err_text = r.text
            try:
                err_json = json.loads(err_text)
                err_msg = err_json.get("msg") or err_text
            except Exception:
                err_msg = err_text
            raise RuntimeError(f"Lỗi gửi tin nhắn ({r.status_code}): {err_msg}")

        current_mode = None
        response_msg_id = None
        accumulated_tokens = 0

        for raw_line in r.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="ignore")

            if line.startswith("event: "):
                event_name = line[7:].strip()
                if event_name == "title":
                    pass
                continue

            if line.startswith("data: "):
                raw_json = line[6:].strip()
                try:
                    data = json.loads(raw_json)
                except Exception:
                    continue

                # 1. Initial fragment setup
                if "v" in data and isinstance(data["v"], dict) and "response" in data["v"]:
                    resp = data["v"]["response"]
                    response_msg_id = resp.get("message_id")
                    frags = resp.get("fragments", [])
                    for frag in frags:
                        ftype = frag.get("type")
                        fcontent = frag.get("content", "")
                        if ftype == "THINK":
                            current_mode = "THINK"
                            yield ChatEvent("think_start", None)
                            if fcontent:
                                yield ChatEvent("think_chunk", fcontent)
                        elif ftype == "RESPONSE":
                            current_mode = "RESPONSE"
                            yield ChatEvent("resp_start", None)
                            if fcontent:
                                yield ChatEvent("resp_chunk", fcontent)

                # 2. Fragment transition or properties
                elif "p" in data:
                    p = data.get("p", "")
                    v = data.get("v")
                    op = data.get("o", "")

                    if "elapsed_secs" in p and current_mode == "THINK":
                        yield ChatEvent("think_done", v)

                    elif p == "response/fragments" and op == "APPEND" and isinstance(v, list):
                        for frag in v:
                            ftype = frag.get("type")
                            fcontent = frag.get("content", "")
                            if ftype == "RESPONSE":
                                current_mode = "RESPONSE"
                                yield ChatEvent("resp_start", None)
                                if fcontent:
                                    yield ChatEvent("resp_chunk", fcontent)

                    elif p == "response/fragments/-1/content" or op == "APPEND":
                        if isinstance(v, str):
                            if current_mode == "THINK":
                                yield ChatEvent("think_chunk", v)
                            else:
                                yield ChatEvent("resp_chunk", v)

                    elif p == "response" and op == "BATCH" and isinstance(v, list):
                        for item in v:
                            if item.get("p") == "accumulated_token_usage":
                                accumulated_tokens = item.get("v", 0)

                    elif p == "response/status" and v == "FINISHED":
                        yield ChatEvent("finish", {
                            "tokens": accumulated_tokens,
                            "response_message_id": response_msg_id
                        })

                # 3. Delta chunks
                elif "v" in data and isinstance(data["v"], str):
                    chunk = data["v"]
                    if chunk != "FINISHED":
                        if current_mode == "THINK":
                            yield ChatEvent("think_chunk", chunk)
                        else:
                            yield ChatEvent("resp_chunk", chunk)

                # 4. Title event payload
                elif "content" in data and isinstance(data["content"], str):
                    yield ChatEvent("title", data["content"])
