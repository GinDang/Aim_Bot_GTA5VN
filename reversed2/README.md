# Dich nguoc: DiscordSetup.exe -> gta5vn-chat-go-premium v1.0.0

> **Canh bao:** Day la tool gian lan game (auto/aimbot cho GTA5 RP, nghe Go/Da/Cong truong).
> Tai lieu nay chi nham muc dich PHAN TICH KY THUAT / reverse engineering.

## 1. Danh tinh

| Truong | Gia tri |
|---|---|
| Ten tool | `gta5vn-chat-go-premium` |
| Phien ban | `1.0.0` |
| Tac gia | CypherSoft |
| Website | https://cyphersoft.store/ |
| Dong goi | PyInstaller (one-file) |
| Python | 3.13 (`python313.dll`) |
| GUI | PySide6 (Qt) |
| Kich thuoc | 161,273,480 bytes |

Day la ban TIEN HOA cua `gta5vn-3-nghe` v1.0.1 (file truoc do), cung tac gia
va cung kien truc, nhung bo sung nhieu tinh nang moi (xem muc 4).

## 2. Quy trinh trich xuat

1. `file` / `strings` -> xac dinh PyInstaller + Python 3.13.
2. **extract2.py** -> doc PyInstaller cookie (magic @ 161273392), parse CArchive
   (overlayPos=365568, tocPos=161192912, **1437 entries**) -> giai nen ra `/data/ext2/`.
   Lay duoc `main` (CArchive type 's', marshal) va `PYZ.pyz` (8.7 MB).
3. **pyz2.py / pyz3.py** -> parse PYZ archive (tocPos @ offset 8 = 8720943,
   **1103 entries**), giai nen zlib + marshal tung code object.
4. Loc bo stdlib / thu vien ben thu ba (psutil, threadpoolctl, win32, numpy, cv2,
   pynput, PySide6, ...) -> con lai **11 module cua ung dung + entrypoint `main`**.
5. **disall2.py** -> `dis.dis()` toan bo -> ghi ra `disasm/*.dis.txt` (uy quyen tham chieu
   chinh xac 100%) va `raw/*.codeobj`.
6. Doc disassembly -> tai dung thu cong ra `src/*.py`.

## 3. Cau truc thu muc

```
reversed2/
  disasm/   # 12 file .dis.txt  - bytecode disassembly (CHINH XAC 100%, uy quyen)
  raw/      # 12 file .codeobj  - marshal code object tho
  src/      # 12 file .py       - ma nguon tai dung thu cong (xem muc 5)
  README.md
```

## 4. Tinh nang MOI so voi ban cu (gta5vn-3-nghe)

1. **`settings_window.py`** (MOI) - Cua so cai dat QDialog "Cai dat Nghe Go":
   - So vong chat cay (`wood_loops`, 1-999).
   - Muc tieu cua: bo qua / cua Van Go / cua Cui (`craft_target`).
   - Cau hinh ban (Shop): Go Tho / Van Go / Cui.
   - Luu tai `%APPDATA%\Panda\settings_woodcutting_gta5vn.json`.

2. **`cut_thread.py`** (MOI) - Tu dong dieu khien May Cua Go bang **template matching**
   (OpenCV `matchTemplate`, nguong 0.8): Go Tron -> Van Go -> (tuy chon) Cui,
   doi 27s moi lan che tao.

3. **`sell_thread.py`** (MOI) - Tu dong **ban** san pham tai Shop: mo shop (phim E),
   so khop nut mo shop + tab ban, tinh so luong theo `wood_loops`
   (log x1, plank x2, firewood x6).

4. **`tool_module.py`** (NANG CAP LON) - Ngoai OCR ky tu chat (whitelist EFY) nhu ban cu,
   ban nay bo sung **doc bo nho tien trinh game** (`ReadProcessMemory`):
   - `read_float`, `get_player_position`, `get_camera_position`.
   - Tinh toan vector/goc: `distance_2d`, `vector_angle`, `normalize_angle`,
     `get_camera_angle`, `get_angle_to_target`.
   - **Aimbot xoay camera**: `rotate_camera_towards_target` (dieu khien kieu PID:
     `KP`, `MAX_STEP`, `MIN_STEP`, `MOUSE_GAIN`), `move_mouse_horizontal`.
   - Tu dong di chuyen + chat: `hold_key_w`, `press_interact_key`,
     `get_nearest_available_tree`, vong lap `update` theo waypoint.

5. **`utils.py`** (NANG CAP) - Them `get_dynamic_screen_id(pid)` (nhan dien monitor
   chua cua so game qua `EnumWindows` + `MonitorFromWindow`) va `set_pid` -> ho tro da man hinh.

## 5. Do tin cay cua ban tai dung (rat quan trong)

- **`disasm/*.dis.txt` = CHINH XAC 100%** (xuat truc tiep tu bytecode that). Day la uy quyen.
- **`src/*.py` = tai dung THU CONG**, dung logic + cau truc, KHONG dam bao tung byte:
  - Khong co decompiler cho Python 3.13 (uncompyle6/decompyle3/pycdc deu chua ho tro),
    nen `src/` duoc viet tay tu disassembly.
  - Cac module MOI (`settings_window`, `cut_thread`, `sell_thread`) va `utils` da doc
    day du disassembly -> tai dung sat.
  - Cac module LON da tien hoa (`tool_module`, `main_app`, `login`): khung + danh sach ham
    bam sat disassembly, nhung mot so chi tiet (pointer chain/offset bo nho cu the trong
    `tool_module`, phan duoi `sell_tool`) can doi chieu them trong `*.dis.txt`.
  - Cac module on dinh (`account_manager`, `custom_widgets`, `press_key`, `ws_client`,
    `main`) gan nhu khong doi so voi ban truoc, da cap nhat chuoi danh tinh.
- => Muon kiem chung tuyet doi tung dong: doc file `.dis.txt` tuong ung.

## 6. 12 module + kich thuoc disassembly

| Module | disasm (bytes) | Ghi chu |
|---|---|---|
| main | 35,004 | entrypoint |
| account_manager | 41,456 | carryover |
| custom_widgets | 14,993 | carryover (ModernButton...) |
| cut_thread | 37,255 | **MOI** - auto may cua |
| login | 150,022 | dang nhap / kiem tra license |
| main_app | 253,735 | cua so chinh (da tien hoa) |
| press_key | 19,028 | carryover |
| sell_thread | 77,938 | **MOI** - auto ban shop |
| settings_window | 85,405 | **MOI** - cua so cai dat |
| tool_module | 308,183 | **NANG CAP LON** - memory + aimbot |
| utils | 93,377 | them get_dynamic_screen_id |
| ws_client | 47,075 | websocket client |
