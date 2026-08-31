import os
import sys
import json
import argparse
import time
import colorama
from colorama import Fore, Back, Style
from typing import Optional

from deepseek_client import DeepSeekClient, ChatEvent

colorama.init(autoreset=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    default_cfg = {
        "token": "",
        "thinking_enabled": True,
        "search_enabled": False,
        "last_session_id": None,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"{Fore.RED}[!] Lỗi lưu cấu hình: {e}{Style.RESET_ALL}")


def print_banner(user_info: dict, thinking: bool, search: bool):
    name = user_info.get("id_profile", {}).get("name") or "Người dùng"
    email = user_info.get("email") or "N/A"
    print(Fore.CYAN + "=" * 68 + Style.RESET_ALL)
    print(Fore.LIGHTCYAN_EX + "   🤖 DEEPSEEK CLI CHAT TOOL (REVERSE-ENGINEERED WEB API)" + Style.RESET_ALL)
    print(Fore.CYAN + "=" * 68 + Style.RESET_ALL)
    print(f" {Fore.GREEN}👤 Tài khoản :{Style.RESET_ALL} {name} ({email})")
    think_str = Fore.LIGHTGREEN_EX + "BẬT (DeepSeek-R1 Reasoning)" if thinking else Fore.LIGHTBLACK_EX + "TẮT (DeepSeek-V3 Standard)"
    print(f" {Fore.YELLOW}🧠 DeepThink :{Style.RESET_ALL} {think_str}")
    search_str = Fore.LIGHTGREEN_EX + "BẬT (Tìm kiếm web trực tiếp)" if search else Fore.LIGHTBLACK_EX + "TẮT"
    print(f" {Fore.BLUE}🌐 WebSearch :{Style.RESET_ALL} {search_str}")
    print(f" {Fore.MAGENTA}💡 Lệnh nhanh:{Style.RESET_ALL} /help, /new, /list, /think, /search, /status, /exit")
    print(Fore.CYAN + "=" * 68 + Style.RESET_ALL + "\n")


def print_help():
    print(Fore.YELLOW + "=== DANH SÁCH LỆNH HỖ TRỢ ===" + Style.RESET_ALL)
    print(f"  {Fore.GREEN}/new{Style.RESET_ALL}            : Tạo phiên trò chuyện mới (bắt đầu đoạn chat mới)")
    print(f"  {Fore.GREEN}/list{Style.RESET_ALL}           : Liệt kê các đoạn chat gần đây")
    print(f"  {Fore.GREEN}/load <id>{Style.RESET_ALL}      : Tải lại một đoạn chat cũ theo ID")
    print(f"  {Fore.GREEN}/think [on|off]{Style.RESET_ALL} : Bật / tắt chế độ suy nghĩ sâu (DeepSeek-R1)")
    print(f"  {Fore.GREEN}/search [on|off]{Style.RESET_ALL}: Bật / tắt tính năng tìm kiếm Web thời gian thực")
    print(f"  {Fore.GREEN}/status{Style.RESET_ALL}         : Xem thông tin phiên hiện tại, tài khoản và trạng thái")
    print(f"  {Fore.GREEN}/token <token>{Style.RESET_ALL}  : Đổi Bearer Token tài khoản DeepSeek")
    print(f"  {Fore.GREEN}/clear{Style.RESET_ALL}          : Xóa màn hình console")
    print(f"  {Fore.GREEN}/exit{Style.RESET_ALL} hoặc {Fore.GREEN}/quit{Style.RESET_ALL} : Thoát chương trình\n")


class DeepSeekCLI:
    def __init__(self, token: Optional[str] = None):
        self.config = load_config()
        if token:
            self.config["token"] = token

        self.token = self.config.get("token") or os.environ.get("DEEPSEEK_TOKEN")
        if not self.token:
            print(Fore.YELLOW + "╔══════════════════════════════════════════════════════════════════╗" + Style.RESET_ALL)
            print(Fore.YELLOW + "║           🔑 HƯỚNG DẪN LẤY DEEPSEEK BEARER TOKEN                 ║" + Style.RESET_ALL)
            print(Fore.YELLOW + "╠══════════════════════════════════════════════════════════════════╣" + Style.RESET_ALL)
            print(f"║ 1. Mở {Fore.CYAN}https://chat.deepseek.com{Style.RESET_ALL} và đăng nhập vào tài khoản.     ║")
            print(f"║ 2. Nhấn {Fore.GREEN}F12{Style.RESET_ALL} mở DevTools -> chuyển sang tab {Fore.GREEN}Network{Style.RESET_ALL}.                 ║")
            print(f"║ 3. Gửi 1 tin nhắn bất kỳ hoặc F5 tải lại trang.                  ║")
            print(f"║ 4. Tìm request {Fore.CYAN}current{Style.RESET_ALL} hoặc {Fore.CYAN}completion{Style.RESET_ALL}.                            ║")
            print(f"║ 5. Trong {Fore.GREEN}Request Headers{Style.RESET_ALL}, copy phần sau chữ {Fore.MAGENTA}Bearer {Style.RESET_ALL}ở Authorization. ║")
            print(Fore.YELLOW + "╚══════════════════════════════════════════════════════════════════╝" + Style.RESET_ALL + "\n")
            while not self.token:
                self.token = input(Fore.GREEN + "👉 Dán Bearer Token vào đây: " + Style.RESET_ALL).strip()
            self.config["token"] = self.token
            save_config(self.config)

        self.client = DeepSeekClient(self.token)
        self.thinking_enabled = self.config.get("thinking_enabled", True)
        self.search_enabled = self.config.get("search_enabled", False)
        self.current_session_id = None
        self.parent_message_id = None
        self.user_info = {}

    def init_client(self):
        try:
            print(Fore.LIGHTBLACK_EX + "Đang kết nối tới DeepSeek API và xác thực token..." + Style.RESET_ALL)
            self.user_info = self.client.get_user_info()
        except PermissionError:
            print(Fore.RED + "[!] Token không hợp lệ hoặc đã hết hạn. Vui lòng nhập lại token mới." + Style.RESET_ALL)
            self.token = ""
            while not self.token:
                self.token = input(Fore.GREEN + "👉 Nhập Bearer Token mới: " + Style.RESET_ALL).strip()
            self.config["token"] = self.token
            save_config(self.config)
            self.client = DeepSeekClient(self.token)
            self.user_info = self.client.get_user_info()
        except Exception as e:
            print(Fore.YELLOW + f"[!] Cảnh báo kiểm tra thông tin tài khoản: {e}" + Style.RESET_ALL)

    def create_new_session(self):
        try:
            self.current_session_id = self.client.create_session()
            self.parent_message_id = None
            self.config["last_session_id"] = self.current_session_id
            save_config(self.config)
            print(Fore.GREEN + "✔ Đã tạo phiên chat mới: " + Fore.CYAN + self.current_session_id + Style.RESET_ALL + "\n")
        except Exception as e:
            print(Fore.RED + f"[!] Lỗi tạo phiên chat: {e}" + Style.RESET_ALL)

    def run_single(self, prompt: str):
        if not self.current_session_id:
            self.current_session_id = self.client.create_session()
        self._send_and_stream(prompt)

    def _send_and_stream(self, prompt: str):
        if not self.current_session_id:
            self.create_new_session()

        print("\n" + Fore.LIGHTBLACK_EX + "Đang tính toán Proof-of-Work và gửi yêu cầu..." + Style.RESET_ALL)
        t_start = time.perf_counter()

        in_thinking = False
        thinking_elapsed = None
        response_text = ""
        last_resp_msg_id = None
        token_usage = 0

        try:
            for event in self.client.stream_chat(
                prompt=prompt,
                session_id=self.current_session_id,
                parent_message_id=self.parent_message_id,
                thinking_enabled=self.thinking_enabled,
                search_enabled=self.search_enabled,
            ):
                if event.event_type == "think_start":
                    in_thinking = True
                    print("\n" + Fore.YELLOW + "┌─ 🧠 [Quá trình suy nghĩ / DeepThink]" + Style.RESET_ALL)
                    print(Fore.LIGHTBLACK_EX + "│ ", end="", flush=True)

                elif event.event_type == "think_chunk":
                    chunk = event.data
                    formatted = chunk.replace("\n", "\n" + Fore.LIGHTBLACK_EX + "│ " + Style.RESET_ALL)
                    print(Fore.LIGHTBLACK_EX + formatted + Style.RESET_ALL, end="", flush=True)

                elif event.event_type == "think_done":
                    thinking_elapsed = event.data
                    print("\n" + Fore.YELLOW + f"└─ ⏱ Đã suy nghĩ xong trong {thinking_elapsed:.2f}s" + Style.RESET_ALL + "\n")
                    in_thinking = False

                elif event.event_type == "resp_start":
                    if in_thinking:
                        print("\n" + Fore.YELLOW + "└─ ⏱ Hoàn tất suy nghĩ" + Style.RESET_ALL + "\n")
                        in_thinking = False
                    print(Fore.LIGHTGREEN_EX + "🤖 DeepSeek:" + Style.RESET_ALL + "\n")

                elif event.event_type == "resp_chunk":
                    chunk = event.data
                    response_text += chunk
                    print(Fore.WHITE + chunk + Style.RESET_ALL, end="", flush=True)

                elif event.event_type == "title":
                    title = event.data
                    print("\n" + Fore.LIGHTBLACK_EX + f"📌 Tiêu đề đoạn chat: {title}" + Style.RESET_ALL)

                elif event.event_type == "finish":
                    fin_data = event.data
                    token_usage = fin_data.get("tokens", 0)
                    last_resp_msg_id = fin_data.get("response_message_id")

            if in_thinking:
                print("\n" + Fore.YELLOW + "└─ ⏱ Hoàn tất suy nghĩ" + Style.RESET_ALL + "\n")

            if last_resp_msg_id:
                self.parent_message_id = last_resp_msg_id

            t_total = time.perf_counter() - t_start
            print("\n\n" + Fore.LIGHTBLACK_EX + f"[⚡ Hoàn thành trong {t_total:.2f}s | Token tích lũy: {token_usage}]" + Style.RESET_ALL + "\n")

        except KeyboardInterrupt:
            print("\n" + Fore.YELLOW + "[!] Đã hủy yêu cầu hiện tại." + Style.RESET_ALL + "\n")
        except Exception as e:
            print("\n" + Fore.RED + f"[!] Lỗi trong quá trình tạo phản hồi: {e}" + Style.RESET_ALL + "\n")

    def interactive_loop(self):
        print_banner(self.user_info, self.thinking_enabled, self.search_enabled)

        # Resume last session or create new
        last_id = self.config.get("last_session_id")
        if last_id:
            self.current_session_id = last_id
            print(Fore.LIGHTBLACK_EX + "Tiếp tục phiên trước đó: " + Fore.CYAN + self.current_session_id + Style.RESET_ALL + "\n")
        else:
            self.create_new_session()

        while True:
            try:
                prompt_label = Fore.GREEN + "Bạn" + Style.RESET_ALL + " > "
                user_input = input(prompt_label).strip()

                if not user_input:
                    continue

                # Command handler
                if user_input.startswith("/"):
                    parts = user_input.split()
                    cmd = parts[0].lower()
                    args = parts[1:]

                    if cmd in ("/exit", "/quit", "/q"):
                        print(Fore.CYAN + "Tạm biệt! Cảm ơn bạn đã sử dụng DeepSeek CLI." + Style.RESET_ALL)
                        break

                    elif cmd in ("/help", "/h", "/?"):
                        print_help()

                    elif cmd in ("/new", "/n"):
                        self.create_new_session()

                    elif cmd in ("/list", "/sessions"):
                        print(Fore.LIGHTBLACK_EX + "Đang tải danh sách các đoạn chat..." + Style.RESET_ALL)
                        sessions = self.client.list_sessions(limit=15)
                        if not sessions:
                            print(Fore.YELLOW + "Chưa có đoạn chat nào." + Style.RESET_ALL + "\n")
                        else:
                            print("\n" + Fore.YELLOW + "=== CÁC ĐOẠN CHAT GẦN ĐÂY ===" + Style.RESET_ALL)
                            for idx, s in enumerate(sessions, 1):
                                sid = s.get("id")
                                title = s.get("title") or "Chưa có tiêu đề"
                                is_curr = " (HIỆN TẠI)" if sid == self.current_session_id else ""
                                print(f" {idx:2d}. {Fore.CYAN}{sid}{Style.RESET_ALL} : {Fore.WHITE}{title}{Fore.GREEN}{is_curr}{Style.RESET_ALL}")
                            print()

                    elif cmd in ("/load", "/switch"):
                        if not args:
                            print(Fore.RED + "[!] Cách dùng: /load <session_id>" + Style.RESET_ALL)
                        else:
                            self.current_session_id = args[0]
                            self.parent_message_id = None
                            self.config["last_session_id"] = self.current_session_id
                            save_config(self.config)
                            print(Fore.GREEN + "✔ Đã chuyển sang phiên chat: " + Fore.CYAN + self.current_session_id + Style.RESET_ALL + "\n")

                    elif cmd == "/think":
                        if args:
                            self.thinking_enabled = args[0].lower() in ("on", "1", "true", "yes", "bat")
                        else:
                            self.thinking_enabled = not self.thinking_enabled
                        self.config["thinking_enabled"] = self.thinking_enabled
                        save_config(self.config)
                        status_str = Fore.GREEN + "BẬT (DeepSeek-R1)" if self.thinking_enabled else Fore.RED + "TẮT (DeepSeek-V3)"
                        print(f"🧠 Chế độ suy nghĩ sâu (DeepThink): {status_str}" + Style.RESET_ALL + "\n")

                    elif cmd == "/search":
                        if args:
                            self.search_enabled = args[0].lower() in ("on", "1", "true", "yes", "bat")
                        else:
                            self.search_enabled = not self.search_enabled
                        self.config["search_enabled"] = self.search_enabled
                        save_config(self.config)
                        status_str = Fore.GREEN + "BẬT" if self.search_enabled else Fore.RED + "TẮT"
                        print(f"🌐 Tính năng tìm kiếm Web (WebSearch): {status_str}" + Style.RESET_ALL + "\n")

                    elif cmd == "/token":
                        if args:
                            new_tok = args[0].strip()
                        else:
                            new_tok = input("Nhập Bearer Token mới: ").strip()
                        if new_tok:
                            self.token = new_tok
                            self.config["token"] = new_tok
                            save_config(self.config)
                            self.client = DeepSeekClient(self.token)
                            self.init_client()
                            print(Fore.GREEN + "✔ Đã cập nhật token thành công." + Style.RESET_ALL + "\n")

                    elif cmd == "/status":
                        name = self.user_info.get("id_profile", {}).get("name") or "N/A"
                        email = self.user_info.get("email") or "N/A"
                        print("\n" + Fore.YELLOW + "=== TRẠNG THÁI HIỆN TẠI ===" + Style.RESET_ALL)
                        print(f" • Người dùng      : {name} ({email})")
                        print(f" • Session ID      : {self.current_session_id}")
                        print(f" • DeepThink (R1)  : {'BẬT' if self.thinking_enabled else 'TẮT'}")
                        print(f" • Web Search      : {'BẬT' if self.search_enabled else 'TẮT'}")
                        print(f" • PoW Solver      : Native x86_64 JIT (ctypes VirtualAlloc)")
                        print()

                    elif cmd in ("/clear", "/cls"):
                        os.system("cls" if os.name == "nt" else "clear")
                        print_banner(self.user_info, self.thinking_enabled, self.search_enabled)

                    else:
                        print(Fore.RED + f"[!] Lệnh không xác định: {cmd}. Gõ /help để xem hướng dẫn." + Style.RESET_ALL + "\n")

                    continue

                # Normal prompt
                self._send_and_stream(user_input)

            except KeyboardInterrupt:
                print("\n\n" + Fore.CYAN + "Nhấn /exit hoặc Ctrl+C lần nữa để thoát." + Style.RESET_ALL + "\n")
            except EOFError:
                break


def main():
    parser = argparse.ArgumentParser(description="DeepSeek Web API CLI Chat Tool")
    parser.add_argument("-p", "--prompt", type=str, help="Gửi một câu hỏi đơn lẻ và in kết quả ra màn hình")
    parser.add_argument("-t", "--token", type=str, help="Bearer Token DeepSeek")
    parser.add_argument("--think", action="store_true", default=None, help="Bật chế độ suy nghĩ R1")
    parser.add_argument("--no-think", action="store_false", dest="think", help="Tắt chế độ suy nghĩ R1")
    parser.add_argument("--search", action="store_true", default=None, help="Bật Web Search")
    parser.add_argument("--no-search", action="store_false", dest="search", help="Tắt Web Search")
    parser.add_argument("-s", "--session", type=str, help="ID của phiên trò chuyện cụ thể")

    args = parser.parse_args()

    cli = DeepSeekCLI(token=args.token)
    cli.init_client()

    if args.think is not None:
        cli.thinking_enabled = args.think
    if args.search is not None:
        cli.search_enabled = args.search
    if args.session:
        cli.current_session_id = args.session

    if args.prompt:
        cli.run_single(args.prompt)
    else:
        cli.interactive_loop()


if __name__ == "__main__":
    main()
