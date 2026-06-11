# ============================================================
# cut_thread.py — tái dựng từ bytecode Python 3.13
# Tự động điều khiển "Máy Cưa Gỗ": dùng so khớp mẫu (template
# matching) trên toàn màn hình để bấm công thức ván/củi + nút chế tạo.
# Gỗ Tròn -> Ván Gỗ -> (tuỳ chọn) Củi.
# ============================================================
import mss
import numpy as np
import cv2
import pyautogui
import time
from pynput.keyboard import Controller, Key
from utils import resource_path, SCREEN_ID
from settings_window import load_settings

keyboard = Controller()

# Nạp trước các template (ảnh xám)
recipe_plank = cv2.imread(resource_path("templates/recipe_plank.png"), cv2.IMREAD_GRAYSCALE)
recipe_firewood = cv2.imread(resource_path("templates/recipe_firewood.png"), cv2.IMREAD_GRAYSCALE)
mat_log = cv2.imread(resource_path("templates/mat_log.png"), cv2.IMREAD_GRAYSCALE)
mat_plank = cv2.imread(resource_path("templates/mat_plank.png"), cv2.IMREAD_GRAYSCALE)
btn_craft = cv2.imread(resource_path("templates/btn_craft.png"), cv2.IMREAD_GRAYSCALE)


def capture_full_screen(screen_id=1):
    with mss.mss() as sct:
        monitors = sct.monitors
        screen_id = SCREEN_ID if SCREEN_ID < len(monitors) else 0
        screen = monitors[CURRENT_SCREEN]
        screenshot = sct.grab(screen)
        img = np.array(screenshot)[:, :, :3]
        return img


def click_template(template_img, threshold=0.8):
    screen = capture_full_screen()
    gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    match = cv2.matchTemplate(gray_screen, template_img, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(match)
    if max_val >= threshold:
        h, w = template_img.shape
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        pyautogui.click(center_x, center_y)
        return True
    return False


def check_template(template_img, threshold=0.8):
    screen = capture_full_screen()
    gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    match = cv2.matchTemplate(gray_screen, template_img, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(match)
    return max_val >= threshold


def cut_tool():
    global CURRENT_SCREEN
    from utils import get_dynamic_screen_id
    import utils
    CURRENT_SCREEN = get_dynamic_screen_id(utils.PID)

    print("B\u1eaft \u0111\u1ea7u x\u1eed l\u00fd M\u00e1y C\u01b0a G\u1ed7...")
    time.sleep(2)
    settings = load_settings()
    craft_target = settings.get("craft_target", "firewood")

    # --- Bước 1: Gỗ Tròn -> Ván Gỗ ---
    print("\u0110ang ch\u1ebf t\u1ea1o V\u00e1n G\u1ed7...")
    while True:
        if not check_template(mat_log):
            print("\u0110\u00e3 h\u1ebft G\u1ed7 Tr\u00f2n.")
            break
        click_template(recipe_plank)
        time.sleep(0.5)
        if click_template(btn_craft):
            print("\u0110\u00e3 b\u1ea5m ch\u1ebf t\u1ea1o V\u00e1n G\u1ed7. \u0110\u1ee3i 27s...")
            time.sleep(27)
        else:
            time.sleep(1)

    # --- Bước 2 (tuỳ chọn): Ván Gỗ -> Củi ---
    if craft_target == "firewood":
        print("M\u1ee5c ti\u00eau l\u00e0 C\u1ee7i. \u0110ang ti\u1ebfp t\u1ee5c ch\u1ebf t\u1ea1o C\u1ee7i...")
        while True:
            if not check_template(mat_plank):
                print("\u0110\u00e3 h\u1ebft V\u00e1n G\u1ed7. Ho\u00e0n th\u00e0nh!")
                break
            click_template(recipe_firewood)
            time.sleep(0.5)
            if click_template(btn_craft):
                print("\u0110\u00e3 b\u1ea5m ch\u1ebf t\u1ea1o C\u1ee7i. \u0110\u1ee3i 27s...")
                time.sleep(27)
            else:
                time.sleep(1)

    print("\u0110\u00f3ng m\u00e1y c\u01b0a.")
    time.sleep(0.5)
    keyboard.press(Key.esc)
    time.sleep(0.1)
    keyboard.release(Key.esc)
    return True
