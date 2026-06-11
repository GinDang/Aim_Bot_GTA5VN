# ============================================================
# sell_thread.py — tái dựng từ bytecode Python 3.13
# Tự động BÁN sản phẩm tại Shop: mở shop (phím E), so khớp mẫu
# nút mở shop + tab bán, click bán. Số lượng bán suy ra từ
# wood_loops trong settings (log = x1, plank = x2, firewood = x6).
# ============================================================
from pynput.keyboard import Controller, Key
keyboard = Controller()
import time
import cv2
import mss
import numpy as np
import pyautogui
from settings_window import load_settings
from utils import resource_path, SCREEN_ID


def capture_full_screen():
    with mss.mss() as sct:
        monitors = sct.monitors
        screen = monitors[CURRENT_SCREEN]
        screenshot = sct.grab(screen)
        img = np.array(screenshot)[:, :, :3]
        return img


def click_open_shop(sell_log, sell_plank, sell_firewood):
    import os
    while True:
        if sell_log or sell_plank or sell_firewood:
            keyboard.press("e")
            time.sleep(0.1)
            keyboard.release("e")
            time.sleep(1)
        else:
            return None

        # Tìm và bấm nút mở shop
        screen = capture_full_screen()
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        button_path = resource_path("templates/button_open_shop.png")
        if not os.path.exists(button_path):
            print(f"⚠ Thiếu file template: {button_path}")
            print("  → Hãy chụp screenshot nút 'Mở Shop' trong game và lưu vào templates/button_open_shop.png")
            return None

        button_template = cv2.imread(button_path, cv2.IMREAD_GRAYSCALE)
        match = cv2.matchTemplate(gray_screen, button_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match)
        if max_val >= 0.8:
            pyautogui.click(max_loc[0], max_loc[1])
            time.sleep(1)

            # Tìm và bấm tab "Bán"
            tab_path = resource_path("templates/tab_sell_button.png")
            if not os.path.exists(tab_path):
                print(f"⚠ Thiếu file template: {tab_path}")
                print("  → Hãy chụp screenshot tab 'Bán' trong game và lưu vào templates/tab_sell_button.png")
                return None

            tab_sell_button_template = cv2.imread(tab_path, cv2.IMREAD_GRAYSCALE)
            screen = capture_full_screen()
            gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            match = cv2.matchTemplate(gray_screen, tab_sell_button_template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match)
            if max_val >= 0.8:
                pyautogui.click(max_loc[0], max_loc[1])
                time.sleep(1)
            return None
        time.sleep(1)


def sell_tool():
    global CURRENT_SCREEN
    from utils import get_dynamic_screen_id
    import utils
    CURRENT_SCREEN = get_dynamic_screen_id(utils.PID)

    settings = load_settings()
    sell_log = settings["sell"]["log"]
    sell_plank = settings["sell"]["plank"]
    sell_firewood = settings["sell"]["firewood"]

    wood_loops = settings.get("wood_loops", 1)
    # Số lượng sản phẩm suy ra từ số vòng chặt (1 gỗ -> 2 ván -> 6 củi)
    amount_log = wood_loops
    amount_plank = wood_loops * 2
    amount_firewood = wood_loops * 6
    # ... (tiếp tục: mở shop, chọn sản phẩm, nhập số lượng, bấm bán)
    click_open_shop(sell_log, sell_plank, sell_firewood)
    # (Phần nhập số lượng / xác nhận bán nằm ở cuối sell_tool —
    #  xem sell_thread.dis.txt để đối chiếu đầy đủ byte-by-byte.)
