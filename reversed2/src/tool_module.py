# ============================================================
# tool_module.py — tái dựng chính xác từ bytecode Python 3.13
# (tool_module.dis.txt — 308 KB, 7468 dòng disassembly)
#
# Module chính điều khiển bot chặt gỗ tự động trong GTA5 RP:
#   - Đọc bộ nhớ tiến trình game (ReadProcessMemory)
#   - Aimbot xoay camera về phía cây gần nhất
#   - State machine: FIND_TREE → MOVING → FARMING → GO_TO_SAWMILL
#     → SAWING → GO_TO_SHOP → SELLING → RETURN_TO_FOREST → ...
#   - OCR nhận diện ký tự chat (E/F/Y) bằng Tesseract
#   - Template matching (OpenCV) phát hiện gốc cây
# ============================================================
import os
import cv2
import numpy as np
import pyautogui
import time
import threading
import mss
import pytesseract
import math
import random
import ctypes
import struct
import win32process
from pynput.keyboard import Controller, Key
import keyboard

from utils import show_message, resource_path, PID, SCREEN_ID
import utils
from press_key import press_key
from PySide6.QtCore import QObject, Signal

from settings_window import load_settings
from cut_thread import cut_tool
from sell_thread import sell_tool

from utils import get_dynamic_screen_id


class Communicator(QObject):
    update_signal = Signal()


comm = Communicator()


class ToolBot:

    def __init__(self):
        self.is_running = False
        self.threads = []
        self.keyboard = Controller()
        pyautogui.FAILSAFE = False
        # Ưu tiên Tesseract cài hệ thống, fallback sang bản đóng gói
        tesseract_system = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(tesseract_system):
            pytesseract.pytesseract.tesseract_cmd = tesseract_system
        else:
            pytesseract.pytesseract.tesseract_cmd = resource_path('Tesseract-OCR/tesseract.exe')

        self.PROCESS_VM_READ = 16
        self.PROCESS_QUERY_INFORMATION = 1024
        self.kernel32 = ctypes.windll.kernel32
        self.handle = None
        self.modules = None
        self.base_addr = None

        # Bán kính đến nơi
        self.ARRIVE_RADIUS = 1.5
        self.phase = 'FIND_TREE'
        self.target_tree = None
        self.farming_idle_time = 0
        self.cut_template = None
        self.cut_template_2 = None

        self.dynamic_screen_id = get_dynamic_screen_id(utils.PID)

        # Settings
        self.settings = load_settings()
        self.target_loops = self.settings.get('wood_loops', 3)
        self.current_loops = 0

        # Routes (waypoints) — SAWMILL
        self.SAWMILL_ROUTE = [
            (-585.18, 5455.3),
            (-561.59, 5437.63),
            (-553.83, 5423.4),
            (-552.12, 5403.28),
            (-554.96, 5388.9),
            (-566.4, 5374.68),
            (-574.35, 5364.98),
        ]

        # Route đến Shop từ rừng
        self.SHOP_ROUTE_FROM_FOREST = [
            (-585.18, 5455.3),
            (-561.59, 5437.63),
            (-553.83, 5423.4),
            (-552.12, 5403.28),
            (-554.96, 5388.9),
            (-566.4, 5374.68),
            (-564.61, 5361.98),
            (-569.88, 5347.65),
            (-577.56, 5323.81),
            (-573.85, 5314.94),
        ]

        # Route đến Shop từ máy cưa
        self.SHOP_ROUTE_FROM_SAWMILL = [
            (-570.2, 5348.65),
            (-576.39, 5329.75),
            (-577.23, 5320.34),
            (-573.85, 5314.94),
        ]

        # Route về rừng từ Shop
        self.RETURN_ROUTE_FROM_SHOP = [
            (-577.57, 5322.62),
            (-563.56, 5365.72),
            (-555.06, 5388.13),
            (-550.53, 5406.88),
            (-552.23, 5423.23),
        ]

        # Route về rừng từ máy cưa
        self.RETURN_ROUTE_FROM_SAWMILL = [
            (-570.03, 5356.87),
            (-565.03, 5364.0),
            (-554.47, 5389.29),
            (-551.88, 5421.99),
            (-552.23, 5423.23),
        ]

        self.current_route = []
        self.current_route_index = 0

        # Danh sách toạ độ cây (waypoints)
        self.tree_list = [
            (-561.38, 5421.25),
            (-577.8, 5426.52),
            (-615.28, 5424.35),
            (-614.58, 5433.21),
            (-619.62, 5428.62),
            (-630.8, 5465.69),
            (-628.97, 5470.09),
            (-658.5, 5490.23),
            (-663.47, 5495.28),
            (-666.98, 5496.98),
            (-639.11, 5503.61),
            (-634.73, 5505.23),
            (-620.44, 5498.37),
            (-591.13, 5495.29),
            (-583.27, 5492.53),
            (-572.85, 5507.89),
            (-567.49, 5504.15),
            (-556.4, 5512.19),
            (-541.09, 5493.47),
            (-537.27, 5492.27),
            (-537.33, 5484.39),
            (-560.75, 5461.54),
            (-563.19, 5457.79),
            (-572.97, 5467.28),
            (-577.82, 5469.75),
            (-579.93, 5471.33),
            (-594.07, 5451.26),
            (-591.03, 5449.26),
            (-586.37, 5447.86),
        ]

        # Cooldown map: {tree_tuple: timestamp}
        self.tree_cooldowns = {tree: 0 for tree in self.tree_list}

        self.last_check_pos = None
        self.last_check_time = 0
        self.STUCK_TIME_THRESHOLD = 3.0
        self.STUCK_DIST_THRESHOLD = 0.5

    # ==================== capture_screen ====================
    # Defaults: size=1
    def capture_screen(self, size=1):
        with mss.mss() as sct:
            monitor = sct.monitors[self.dynamic_screen_id]
            center_x = monitor['left'] + monitor['width'] // 2
            center_y = monitor['top'] + monitor['height'] // 2

            region = {
                'top': center_y + 10,
                'left': center_x - size // 2,
                'width': size,
                'height': size,
            }

            screenshot = np.array(sct.grab(region))
            gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

        return thresh

    # ==================== capture_screen_for_cut ====================
    # Defaults: dynamic_screen_id=1, region_width=250, region_height=70
    def capture_screen_for_cut(self, dynamic_screen_id=1, region_width=250, region_height=70):
        with mss.mss() as sct:
            monitors = sct.monitors

            if self.dynamic_screen_id >= len(monitors):
                self.dynamic_screen_id = 1

            screen = monitors[self.dynamic_screen_id]
            left = screen['left'] + 10
            top = screen['top'] + 10

            screenshot = sct.grab({'left': left, 'top': top, 'width': region_width, 'height': region_height})
            img = np.array(screenshot)[:, :, :3]

        return img

    # ==================== extract_char ====================
    def extract_char(self, image):
        custom_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=EFY'
        details = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)

        max_confidence, char = -1, None

        for i in range(len(details['text'])):
            word = details['text'][i].strip()
            confidence = int(details['conf'][i])

            if not word.isalpha():
                continue
            if len(word) != 1:
                continue
            if not confidence > 50:
                continue

            if confidence > max_confidence:
                max_confidence, char = confidence, word

        return char

    # ==================== type_detected_char ====================
    def type_detected_char(self, char):
        if not char:
            return

        lowercase_char = char.lower()
        amount_type = random.randint(15, 25)
        for _ in range(amount_type):
            press_key(lowercase_char, fast_mode=True)

    # ==================== read_float ====================
    def read_float(self, addr):
        buf = ctypes.create_string_buffer(4)
        read = ctypes.c_size_t()
        self.kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(addr), buf, 4, ctypes.byref(read)
        )
        return struct.unpack('f', buf.raw)[0]

    # ==================== get_player_position ====================
    def get_player_position(self):
        offset_player_block = 30435232
        x = self.read_float(self.base_addr + offset_player_block + 0)
        y = self.read_float(self.base_addr + offset_player_block + 4)
        return (x, y)

    # ==================== get_camera_position ====================
    def get_camera_position(self):
        offset_camera_block = 36891888
        x = self.read_float(self.base_addr + offset_camera_block + 0)
        y = self.read_float(self.base_addr + offset_camera_block + 4)
        return (x, y)

    # ==================== distance_2d ====================
    def distance_2d(self, a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    # ==================== vector_angle ====================
    def vector_angle(self, vx, vy):
        return math.atan2(vy, vx)

    # ==================== normalize_angle ====================
    def normalize_angle(self, angle):
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    # ==================== get_camera_angle ====================
    def get_camera_angle(self):
        px, py = self.get_player_position()
        cx, cy = self.get_camera_position()
        # Bytecode: STORE_FAST_STORE_FAST 101 (vy, vx)
        # vx (local 5) = cx - px, vy (local 6) = cy - py
        vx = cx - px
        vy = cy - py
        if abs(vx) < 1e-06 and abs(vy) < 1e-06:
            return None
        return self.vector_angle(vx, vy)

    # ==================== get_angle_to_target ====================
    def get_angle_to_target(self, target):
        px, py = self.get_player_position()
        tx, ty = target
        cam_angle = self.get_camera_angle()
        if cam_angle is None:
            return None
        target_angle = self.vector_angle(tx - px, ty - py)
        return self.normalize_angle(target_angle - cam_angle)

    # ==================== move_mouse_horizontal ====================
    def move_mouse_horizontal(self, dx):
        ctypes.windll.user32.mouse_event(1, int(dx), 0, 0, 0)

    # ==================== rotate_camera_towards_target ====================
    def rotate_camera_towards_target(self, target):
        delta = self.get_angle_to_target(target)
        if delta is None:
            return False

        deg_delta = math.degrees(delta)

        # Nếu gần 180 độ (quay ngược) -> coi như đã đến
        if abs(deg_delta) >= 175:
            return True

        # Tính error_deg
        if deg_delta > 0:
            error_deg = 180.0 - deg_delta
        else:
            error_deg = -180.0 - deg_delta

        error_rad = math.radians(error_deg)

        KP = 0.4
        step = error_rad * KP

        MAX_STEP = 0.15
        MIN_STEP = 0.005

        if step > 0:
            step = max(MIN_STEP, min(MAX_STEP, step))
        else:
            step = min(-MIN_STEP, max(-MAX_STEP, step))

        MOUSE_GAIN = 500
        mouse_dx = step * MOUSE_GAIN

        self.move_mouse_horizontal(mouse_dx)
        return False

    # ==================== hold_key_w ====================
    # Defaults: down=True, run=True
    def hold_key_w(self, down=True, run=True):
        if down:
            keyboard.press('w')
            if run:
                self.keyboard.press(Key.shift)
                return
            else:
                self.keyboard.release(Key.shift)
                return
        else:
            self.keyboard.release(Key.shift)
            keyboard.release('w')
            return

    # ==================== press_interact_key ====================
    # Defaults: min_delay=0.08, max_delay=0.15
    def press_interact_key(self, min_delay=0.08, max_delay=0.15):
        time_random = random.uniform(min_delay, max_delay)
        keyboard.press('e')
        time.sleep(time_random)
        keyboard.release('e')

    # ==================== get_nearest_available_tree ====================
    def get_nearest_available_tree(self):
        px, py = self.get_player_position()
        current_time = time.time()
        nearest_tree = None
        min_dist = float('inf')

        for tree in self.tree_list:
            if current_time < self.tree_cooldowns[tree]:
                continue
            dist = self.distance_2d((px, py), tree)
            if dist < min_dist:
                min_dist = dist
                nearest_tree = tree

        return nearest_tree

    # ==================== update (STATE MACHINE) ====================
    def update(self):
        # ---- PHASE: FIND_TREE ----
        if self.phase == 'FIND_TREE':
            self.target_tree = self.get_nearest_available_tree()
            if self.target_tree:
                print(f'Targeting tree at: {self.target_tree}')
                self.phase = 'MOVING'
                return
            else:
                time.sleep(1)
                return

        # ---- PHASE: MOVING ----
        if self.phase == 'MOVING':
            if not self.target_tree:
                self.phase = 'FIND_TREE'
                return

            self.rotate_camera_towards_target(self.target_tree)
            self.hold_key_w(True)

            px, py = self.get_player_position()
            dist = self.distance_2d((px, py), self.target_tree)

            # Đến nơi
            if dist < self.ARRIVE_RADIUS:
                self.hold_key_w(False)
                time.sleep(0.5)
                self.press_interact_key()
                self.farming_idle_time = time.time()
                self.last_check_pos = None
                self.has_started_farming = False
                self.phase = 'FARMING'
                return

            # Stuck detection
            current_time = time.time()
            if not self.last_check_pos:
                self.last_check_pos = (px, py)
                self.last_check_time = current_time

            if current_time - self.last_check_time >= self.STUCK_TIME_THRESHOLD:
                moved_dist = self.distance_2d((px, py), self.last_check_pos)
                if moved_dist < self.STUCK_DIST_THRESHOLD:
                    print('⚠ Bị kẹt! Bỏ qua cây này.')
                    self.hold_key_w(False)
                    self.tree_cooldowns[self.target_tree] = current_time + 30
                    self.last_check_pos = None
                    self.phase = 'FIND_TREE'
                    return
                else:
                    self.last_check_pos = (px, py)
                    self.last_check_time = current_time
                    return
            return

        # ---- PHASE: FARMING ----
        if self.phase == 'FARMING':
            screenshot = self.capture_screen(40)
            screenshot_for_E = self.capture_screen_for_cut()

            max_val = 0
            threshold = 0.7

            # Template matching cho gốc cây
            if self.cut_template is not None:
                result = cv2.matchTemplate(screenshot_for_E, self.cut_template, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            else:
                max_val = 0

            # Template thứ 2 (nếu có)
            if self.cut_template_2 is not None:
                result_2 = cv2.matchTemplate(screenshot_for_E, self.cut_template_2, cv2.TM_CCOEFF_NORMED)
                min_val_2, max_val_2, min_loc_2, max_loc_2 = cv2.minMaxLoc(result_2)
                max_val = max(max_val, max_val_2)

            if screenshot is None:
                return

            detected_char = self.extract_char(screenshot)

            # Debug: in score mỗi 1 giây để chẩn đoán
            if not hasattr(self, '_last_debug_time'):
                self._last_debug_time = 0
            if time.time() - self._last_debug_time > 1.0:
                self._last_debug_time = time.time()
                print(f'  [DEBUG] template_score={max_val:.3f} (threshold={threshold}) | OCR={detected_char} | screen={screenshot_for_E.shape}')

            # Phát hiện template cây -> bấm tương tác
            if max_val >= threshold:
                self.has_started_farming = True
                self.farming_idle_time = time.time()
                self.press_interact_key()
                time.sleep(0.2)

            # Phát hiện ký tự OCR -> gõ phím
            if detected_char:
                self.has_started_farming = True
                self.farming_idle_time = time.time()
                self.type_detected_char(detected_char)

            # Không thấy template + không thấy ký tự -> idle timeout
            if max_val < threshold and not detected_char:
                if time.time() - self.farming_idle_time > 2.0:
                    if self.has_started_farming:
                        # Đã chặt xong cây này
                        self.current_loops += 1
                        print(f'✅ Xong cây! ({self.current_loops}/{self.target_loops}). Bỏ qua trong vòng 2 phút...')
                        self.tree_cooldowns[self.target_tree] = time.time() + 120

                        # Kiểm tra đã đủ số lượng chưa
                        if self.current_loops >= self.target_loops:
                            print('Đã chặt đủ số lượng gỗ!')

                            sell_any = (
                                self.settings['sell']['log']
                                or self.settings['sell']['plank']
                                or self.settings['sell']['firewood']
                            )
                            craft_target = self.settings.get('craft_target', 'none')

                            if craft_target == 'none':
                                if sell_any:
                                    print('Setting: Bỏ qua máy cưa. Đi thẳng đến Shop.')
                                    self.current_route = self.SHOP_ROUTE_FROM_FOREST
                                    self.phase = 'GO_TO_SHOP'
                                else:
                                    print('Không cưa cũng không bán. Tiếp tục chặt...')
                                    self.current_loops = 0
                                    self.phase = 'FIND_TREE'
                            else:
                                print('Setting: Đi cưa gỗ. Chạy đến Máy cưa.')
                                self.current_route = self.SAWMILL_ROUTE
                                self.phase = 'GO_TO_SAWMILL'

                            self.current_route_index = 0
                            return
                        else:
                            # Chưa đủ -> tìm cây tiếp
                            self.phase = 'FIND_TREE'
                            return
                    else:
                        # Chưa bắt đầu farming mà đã timeout -> cây không có
                        print('⚠ Không thấy gốc cây. Chuyển mục tiêu khác (không tính vào tiến độ)!')
                        self.tree_cooldowns[self.target_tree] = time.time() + 120
                        self.phase = 'FIND_TREE'
                        return
            return

        # ---- PHASE: GO_TO_SAWMILL / GO_TO_SHOP / RETURN_TO_FOREST ----
        if self.phase in ('GO_TO_SAWMILL', 'GO_TO_SHOP', 'RETURN_TO_FOREST'):
            current_wp = self.current_route[self.current_route_index]
            self.rotate_camera_towards_target(current_wp)

            px, py = self.get_player_position()
            dist = self.distance_2d((px, py), current_wp)
            is_last_waypoint = self.current_route_index == len(self.current_route) - 1

            # Waypoint cuối + gần -> đi chậm (không shift)
            if is_last_waypoint and dist < 5.0:
                self.hold_key_w(True, run=False)
            else:
                self.hold_key_w(True, run=True)

            # Đến waypoint
            if dist < self.ARRIVE_RADIUS:
                self.current_route_index += 1
                self.last_check_pos = None

                # Đã đi hết route
                if self.current_route_index >= len(self.current_route):
                    self.hold_key_w(False)

                    if self.phase == 'GO_TO_SAWMILL':
                        print('Đã đến vị trí Máy Cưa!')
                        self.phase = 'SAWING'
                        return

                    if self.phase == 'GO_TO_SHOP':
                        print('Đã đến Shop NPC!')
                        self.phase = 'SELLING'
                        return

                    if self.phase == 'RETURN_TO_FOREST':
                        print('Đã về tới Rừng! Tiếp tục chu trình farm...')
                        self.current_loops = 0
                        self.last_check_pos = None
                        self.last_check_time = time.time()
                        self.phase = 'FIND_TREE'

                return

            # Stuck detection cho route
            current_time = time.time()
            if not self.last_check_pos:
                self.last_check_pos = (px, py)
                self.last_check_time = current_time

            if current_time - self.last_check_time >= self.STUCK_TIME_THRESHOLD:
                moved_dist = self.distance_2d((px, py), self.last_check_pos)
                if moved_dist < self.STUCK_DIST_THRESHOLD:
                    print('⚠ Bị kẹt khi đang di chuyển! Nhả phím để gỡ kẹt...')
                    self.hold_key_w(False)
                    time.sleep(0.5)
                    self.last_check_pos = None
                    return
                else:
                    self.last_check_pos = (px, py)
                    self.last_check_time = current_time
                    return
            return

        # ---- PHASE: SAWING ----
        if self.phase == 'SAWING':
            self.hold_key_w(False)
            self.last_check_pos = None

            # Bấm E để mở máy cưa
            keyboard.press('e')
            time.sleep(0.1)
            keyboard.release('e')
            time.sleep(1)

            print('Đang chế tạo...')
            cut_tool()

            # Check có bán không
            sell_any = (
                self.settings['sell']['log']
                or self.settings['sell']['plank']
                or self.settings['sell']['firewood']
            )

            if sell_any:
                print('Cưa xong. Chuẩn bị chạy đến Shop.')
                self.current_route = self.SHOP_ROUTE_FROM_SAWMILL
                self.current_route_index = 0
                self.phase = 'GO_TO_SHOP'
                return
            else:
                print('Cưa xong (Setting không bán). Quay lại rừng...')
                self.current_route = self.RETURN_ROUTE_FROM_SAWMILL
                self.current_route_index = 0
                self.phase = 'RETURN_TO_FOREST'
                return

        # ---- PHASE: SELLING ----
        if self.phase == 'SELLING':
            self.hold_key_w(False)
            self.last_check_pos = None

            sell_tool()

            print('Đã bán xong. Chạy theo route về rừng...')
            self.current_route = self.RETURN_ROUTE_FROM_SHOP
            self.current_route_index = 0
            self.phase = 'RETURN_TO_FOREST'
            return

    # ==================== start_tool ====================
    def start_tool(self):
        self.is_running = True
        print('Woodcutting Tool Starting.')

        # Reload settings
        self.settings = load_settings()
        self.target_loops = self.settings.get('wood_loops', 3) + 1
        self.current_loops = 0

        # Load templates
        template_path_1 = resource_path('templates/chatcay.png')
        template_path_2 = resource_path('templates/chatcay_2.png')
        self.cut_template = cv2.imread(template_path_1)
        self.cut_template_2 = cv2.imread(template_path_2)

        if self.cut_template is None:
            print(f'⚠ Không load được template: {template_path_1}')
        else:
            print(f'✅ Template 1 loaded: {self.cut_template.shape}')
        if self.cut_template_2 is None:
            print(f'⚠ Không load được template 2: {template_path_2}')
        else:
            print(f'✅ Template 2 loaded: {self.cut_template_2.shape}')

        # Refresh dynamic screen id
        self.dynamic_screen_id = get_dynamic_screen_id(utils.PID)

        while self.is_running:
            self.update()
            time.sleep(0.02)
            if not self.is_running:
                break

    # ==================== start_tool_thread ====================
    def start_tool_thread(self):
        self.stop_all_threads()

        try:
            self.handle = self.kernel32.OpenProcess(
                self.PROCESS_VM_READ | self.PROCESS_QUERY_INFORMATION,
                False,
                utils.PID
            )

            if not self.handle:
                print(f'❌ Lỗi OpenProcess (Mã lỗi: {self.kernel32.GetLastError()}). Chạy bằng quyền Admin nhé!')
                return

            self.modules = win32process.EnumProcessModules(self.handle)
            self.base_addr = self.modules[0]
        except Exception as e:
            print(f'Lỗi đọc memory: {e}')
            return

        # Phần dưới nằm NGOÀI try/except theo bytecode gốc (L4 trở đi)
        self.is_running = True
        tool_thread = threading.Thread(target=self.start_tool, daemon=True)
        self.threads = [tool_thread]

        for thread in self.threads:
            thread.start()

    # ==================== stop_all_threads ====================
    def stop_all_threads(self):
        self.is_running = False
        print('Dừng Tool')
        self.hold_key_w(False)

        for thread in self.threads:
            try:
                thread.join(timeout=2)
            except Exception as e:
                pass

        self.threads.clear()

        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None

    # ==================== cleanup ====================
    def cleanup(self):
        self.stop_all_threads()
        print('Đã dọn dẹp tài nguyên')
