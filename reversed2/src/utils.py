# ============================================================
# utils.py — tái dựng từ bytecode Python 3.13
# Tiện ích chung: nhận diện màn hình chứa cửa sổ game (theo PID),
# quản lý phiên người dùng, đường dẫn AppData, lưu/nạp login,
# băm mật khẩu, lấy UUID máy + vị trí IP, hộp thoại & tắt máy.
# ============================================================
import os
import sys
import ctypes
import hashlib
import json
import requests
import win32com.client
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

Tool_Name = "gta5vn-chat-go-premium"
Tool_Version = "1.0.0"
WEBSITE_URL = "https://cyphersoft.store/"

# Biến toàn cục dùng cho đa màn hình
SCREEN_ID = 1          # chỉ số màn hình mặc định
PID = None             # PID của tiến trình game (set khi đăng nhập)
CURRENT_USER = {"Username": None, "DeviceChangesToday": 0}


def get_dynamic_screen_id(pid):
    """Xác định chỉ số monitor (mss) mà cửa sổ của tiến trình `pid` đang nằm trên.
    Duyệt các cửa sổ top-level (EnumWindows) tìm đúng PID, lấy monitor
    gần nhất (MonitorFromWindow) rồi đối chiếu toạ độ với danh sách mss.
    """
    import mss

    user32 = ctypes.windll.user32
    main_hwnd = [None]

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def enum_window_callback(hwnd, _):
        found_pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
        if found_pid.value == pid and user32.IsWindowVisible(hwnd):
            main_hwnd[0] = hwnd
            return False
        return True

    try:
        user32.EnumWindows(EnumWindowsProc(enum_window_callback), 0)
        if not main_hwnd[0]:
            return SCREEN_ID

        MONITOR_DEFAULTTONEAREST = 2
        h_monitor = user32.MonitorFromWindow(main_hwnd[0], MONITOR_DEFAULTTONEAREST)

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", ctypes.c_ulong),
            ]

        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(h_monitor, ctypes.byref(monitor_info))
        m_left = monitor_info.rcMonitor.left
        m_top = monitor_info.rcMonitor.top
        with mss.mss() as sct:
            for i, monitor in enumerate(sct.monitors):
                if i == 0:
                    continue
                if monitor["left"] == m_left and monitor["top"] == m_top:
                    return i
        return SCREEN_ID
    except Exception as e:
        print("get_dynamic_screen_id error:", e)
        return SCREEN_ID


def set_pid(pid):
    global PID
    PID = pid


def set_current_user(username, device_changes_today):
    CURRENT_USER["Username"] = username
    CURRENT_USER["DeviceChangesToday"] = device_changes_today


def get_current_username():
    return CURRENT_USER["Username"]


def get_current_user_device_changes():
    return CURRENT_USER["DeviceChangesToday"]


def clear_current_user():
    CURRENT_USER["Username"] = None
    CURRENT_USER["DeviceChangesToday"] = 0


def config_path_AppData(filename):
    base_dir = os.path.join(os.getenv("APPDATA"), "Panda")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, filename)


def save_login(username, password, remember):
    config_file = config_path_AppData("config.json")
    with open(config_file, "w", encoding="utf-8") as file:
        json.dump({"username": username, "password": password, "remember": remember}, file)


def load_login():
    config_file = config_path_AppData("config.json")
    try:
        with open(config_file, "r", encoding="utf-8") as file:
            content = file.read()
            data = json.loads(content)
            return data.get("username", ""), data.get("password", ""), data.get("remember", False)
    except (FileNotFoundError, json.JSONDecodeError):
        return "", "", False


def hash_password_sha256(password, salt="gtav_autobot"):
    return hashlib.sha256((salt + password).encode()).hexdigest()


def check_password_sha256(password, hashed_password, salt="gtav_autobot"):
    return hash_password_sha256(password, salt) == hashed_password


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_system_uuid():
    wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2")
    svc = wmi
    query = "SELECT UUID FROM Win32_ComputerSystemProduct"
    result = svc.ExecQuery(query)
    for item in result:
        return item.UUID
    return None


def get_location():
    try:
        response = requests.get("http://ip-api.com/json/", timeout=5)
        data = response.json()
        city = data.get("city", "")
        country = data.get("country", "")
        ip = data.get("query", "")
        return f"{ip} - {city}, {country}"
    except Exception as e:
        return "Unknown"


def show_message(title, text, style=0, timeout=10):
    MB_TOPMOST = 262144
    MB_SETFOREGROUND = 65536
    ctypes.windll.user32.MessageBoxTimeoutW(
        0, text, title, style | MB_TOPMOST | MB_SETFOREGROUND, 0, timeout * 1000
    )


def force_shutdown():
    import time
    try:
        time.sleep(10)
        os._exit(0)
    except Exception as e:
        print(e)


def notice_and_shutdown(title, text):
    import threading
    threading.Thread(target=force_shutdown, daemon=True).start()
    threading.Thread(target=show_message(title, text, 16), daemon=True).start()


def get_current_time():
    try:
        response = requests.get(
            "https://timeapi.io/api/Time/current/zone?timeZone=Asia/Ho_Chi_Minh", timeout=5
        )
        data = response.json()
        return datetime.strptime(data["dateTime"][:16], "%Y-%m-%dT%H:%M")
    except Exception:
        return datetime.now()
