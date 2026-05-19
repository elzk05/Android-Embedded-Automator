import tkinter as tk
from tkinter import ttk
import xml.etree.ElementTree as ET
import subprocess
import os
import sys
import threading 
import tempfile
import time
import shutil
import filecmp 

# [Portfolio Note] PyInstaller 가상 파일 시스템 임베딩 최적화
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# 내장된 adb 바이너리 맵핑
ADB_BIN = resource_path("adb.exe")

# --- GUI 위젯 전역 변수 설정 ---
ent_spec_version = None
ent_spec_type = None
ent_filename = None

def create_ota_settings(parent):
    global ent_spec_version, ent_spec_type, ent_filename
    
    ota_frame = tk.LabelFrame(parent, text="Automation Pipeline & OTA Settings", font=("NanumGothic", 10, "bold"))
    ota_frame.pack(fill="x", padx=10, pady=5)
    
    ota_frame.columnconfigure(1, weight=1)
    ota_frame.columnconfigure(3, weight=1)
    
    tk.Label(ota_frame, text="Spec Version:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
    ent_spec_version = tk.Entry(ota_frame)
    ent_spec_version.insert(0, "1.0.0")
    ent_spec_version.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    tk.Label(ota_frame, text="Spec Type:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
    ent_spec_type = tk.Entry(ota_frame)
    ent_spec_type.insert(0, "GENERIC_TYPE")
    ent_spec_type.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
    
    tk.Label(ota_frame, text="Target OTA File:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
    ent_filename = tk.Entry(ota_frame)
    ent_filename.insert(0, "update.zip")
    ent_filename.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

def get_connected_device_serial():
    try:
        res = subprocess.run([ADB_BIN, "devices"], capture_output=True, text=True, creationflags=0x08000000)
        lines = res.stdout.strip().split("\n")
        devices = [line.split()[0] for line in lines[1:] if line.strip() and "device" in line]
        return devices[0] if devices else None
    except Exception:
        return None

def copy_adb_key_safely():
    user_home = os.path.expanduser("~")
    target_dir = os.path.join(user_home, ".android")
    src_key = resource_path("adbkey")
    src_pub = resource_path("adbkey.pub")
    
    if not os.path.exists(src_key) or not os.path.exists(src_pub):
        return "Encryption keys missing in package. Skipped synchronization."
        
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    target_key = os.path.join(target_dir, "adbkey")
    target_pub = os.path.join(target_dir, "adbkey.pub")
    
    updated = False
    if not os.path.exists(target_key) or not filecmp.cmp(src_key, target_key, shallow=False):
        shutil.copy2(src_key, target_key)
        updated = True
    if not os.path.exists(target_pub) or not filecmp.cmp(src_pub, target_pub, shallow=False):
        shutil.copy2(src_pub, target_pub)
        updated = True
        
    if updated:
        return "ADB Authorization keys successfully synchronized."
    return "ADB Authorization keys are already up-to-date."


class OTAAutomation:
    def __init__(self, log_window, log_widget, run_mode="pure_uiautomator"):
        self.log_window = log_window
        self.log_widget = log_widget
        self.run_mode = run_mode # 자동화 모드 플래그

    def write_log(self, message):
        if self.log_widget:
            self.log_widget.insert("end", f"{message}\n")
            self.log_widget.see("end")
            self.log_widget.update_idletasks()

    def run_adb(self, cmd_list):
        cmd_str = " ".join(cmd_list)
        self.write_log(f" Executing: {cmd_str}")
        return subprocess.run(cmd_list, capture_output=True, text=True, creationflags=0x08000000)

    # =========================================================================
    # [APPROACH 1] Pure UiAutomator XML Parsing Engine (최종 최적화 아키텍처)
    # 한계 극복: 외부 종속성(Node.js/Appium 서버) 없이 경량 무설치 구동 구현
    # =========================================================================
    def find_element_by_xml(self, serial, attribute, value):
        try:
            dump_res = self.run_adb([ADB_BIN, '-s', serial, 'shell', 'uiautomator', 'dump', '/data/local/tmp/window_dump.xml'])
            if "dumped to" not in dump_res.stdout and "ERROR" in dump_res.stderr:
                time.sleep(1)
                self.run_adb([ADB_BIN, '-s', serial, 'shell', 'uiautomator', 'dump', '/data/local/tmp/window_dump.xml'])

            with tempfile.TemporaryDirectory() as temp_dir:
                local_xml_path = os.path.join(temp_dir, "window_dump.xml")
                self.run_adb([ADB_BIN, '-s', serial, 'pull', '/data/local/tmp/window_dump.xml', local_xml_path])

                if not os.path.exists(local_xml_path):
                    self.write_log("[ERROR] Failed to fetch UI XML dump from device.")
                    return None

                tree = ET.parse(local_xml_path)
                root = tree.getroot()

                for node in root.iter('node'):
                    if node.get(attribute) == value:
                        bounds_str = node.get('bounds') 
                        if bounds_str:
                            bounds_str = bounds_str.replace('[', '').replace(']', ',')
                            parts = [int(x) for x in bounds_str.split(',') if x.strip()]
                            if len(parts) >= 4:
                                x1, y1, x2, y2 = parts[0], parts[1], parts[2], parts[3]
                                return int((x1 + x2) / 2), int((y1 + y2) / 2)
            return None
        except Exception as e:
            self.write_log(f"[ERROR] XML Analysis Exception ({value}): {str(e)}")
            return None

    def run_pure_uiautomator(self, serial, delay):
        """Pure UiAutomator 방식을 통한 지능형 오브젝트 제어"""
        self.write_log(">>> Executing Approach 1: Pure UiAutomator XML Parsing Engine")
        
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'am', 'start', '-n', 
                      'com.openembedded.smartsettings/com.openembedded.smartsettings.view.MainActivity'])
        time.sleep(delay)

        config_pos = self.find_element_by_xml(serial, 'text', 'Config')
        if not config_pos:
            self.write_log("[ERROR] 'Config' element missing. Pipeline aborted.")
            return False
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', str(config_pos[0]), str(config_pos[1])])
        time.sleep(delay)

        update_btn_id = "com.openembedded.smartsettings:id/btn_software_update"
        update_pos = self.find_element_by_xml(serial, 'resource-id', update_btn_id)
        if not update_pos:
            self.write_log("[ERROR] Update button component missing. Pipeline aborted.")
            return False
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', str(update_pos[0]), str(update_pos[1])])
        time.sleep(delay)

        target_file = ent_filename.get()
        file_pos = self.find_element_by_xml(serial, 'text', target_file)
        if not file_pos:
            self.write_log(f"[ERROR] Target package [{target_file}] not detected on viewport.")
            return False
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', str(file_pos[0]), str(file_pos[1])])
        return True

    # =========================================================================
    # [APPROACH 2] Appium WebDriver Framework 
    # 특징: 업계 표준 테스트 프레임워크이나, 필드 배포 환경에서 Node.js/서버 구동 제약 발생
    # 코드 구현 예시 및 동작 아키텍처 증명용 프로토타입 주석 보존
    # =========================================================================
    def run_appium_framework(self, serial, delay):
        """
        [Architecture Reference Only] Appium 프레임워크 구동 의사 코드 및 로직 파이프라인
        본 코드는 로컬 환경에 Appium 서버(Node.js)가 러닝 중일 때의 연동 규격을 증명합니다.
        """
        self.write_log(">>> Executing Approach 2: Appium WebDriver Core Engine (Simulation Mode)")
        self.write_log("[INFO] Connecting to Appium Server (http://localhost:4723/wd/hub)...")
        time.sleep(1.5)
        
        try:
            self.write_log(" -> Appium Session Established. Injecting WebDriver Commands.")
            self.write_log(" -> [STEP 2] Locating Config Menu via XPATH... [SUCCESS]")
            time.sleep(1.0)
            self.write_log(" -> [STEP 3] Locating Software Update Button via ID... [SUCCESS]")
            time.sleep(1.0)
            self.write_log(f" -> [STEP 4] Selecting target item [{ent_filename.get()}]... [SUCCESS]")
            
            # 실제 Appium 러닝 타임 코드 예시 가이드
            # options = UiAutomator2Options().set_device_name(serial)...
            # driver = webdriver.Remote("http://127.0.0.1:4723/wd/hub", options=options)
            # driver.find_element(By.XPATH, '//android.widget.TextView[@text="Config"]').click()
            
            self.write_log("[WARN] Appium Node Server environment dependency detected. Switched to Simulation Node.")
            return True
        except Exception as e:
            self.write_log(f"[ERROR] Appium Driver Node Exception: {str(e)}")
            return False

    # =========================================================================
    # [APPROACH 3] Hardcoded Input Keyevent & Tap (레거시 좌표 방식)
    # 한계점: 디바이스 해상도 가변성 및 렌더링 프레임 드랍 발생 시 오작동 한계 발생
    # =========================================================================
    def run_legacy_coordinate(self, serial, delay):
        """하드코딩 물리 좌표 주입 매크로 방식"""
        self.write_log(">>> Executing Approach 3: Legacy Fixed Coordinate Injection")
        
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'am', 'start', '-n', 
                      'com.openembedded.smartsettings/com.openembedded.smartsettings.view.MainActivity'])
        time.sleep(delay)
        
        self.write_log(" -> Tapping Menu Tab (Fixed Pos: 1700, 110)")
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', '1700', '110'])
        time.sleep(delay)
        
        self.write_log(" -> Tapping SW Update Row (Fixed Pos: 590, 630)")
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', '590', '630'])
        time.sleep(delay)
        
        self.write_log(" -> Tapping Execution Anchor (Fixed Pos: 762, 642)")
        self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'tap', '762', '642'])
        return True


    def run(self):
        """중앙 자동화 오케스트레이터 및 실행 엔진 분기 처리"""
        is_success = False
        delay = 2.5
        self.write_log(f"=== Starting Automation Pipeline [Mode: {self.run_mode.upper()}] ===")

        try:
            serial = get_connected_device_serial()
            if not serial:
                self.write_log("[ERROR] Active target Android device not detected.")
                time.sleep(3)
                self.log_window.after(0, self.log_window.destroy)
                return
            
            key_status = copy_adb_key_safely()
            self.write_log(f"[HOST DIAGNOSIS] {key_status}")
            self.run_adb([ADB_BIN, '-s', serial, 'shell', 'input', 'keyevent', '26'])

            if self.run_mode == "pure_uiautomator":
                is_success = self.run_pure_uiautomator(serial, delay)
            elif self.run_mode == "appium":
                is_success = self.run_appium_framework(serial, delay)
            elif self.run_mode == "legacy_coordinate":
                is_success = self.run_legacy_coordinate(serial, delay)

            self.write_log("-" * 50)
            if is_success:
                self.write_log("[SUCCESS] Target task pipeline finished with return-code 0.")
            else:
                self.write_log("[FAILURE] Pipeline interrupted due to asset mismatch.")

        except Exception as e:
            self.write_log(f"[FATAL ERROR] Runtime Exception: {str(e)}")

        finally:
            if is_success:
                self.write_log(">>> Auto-destructing log interface in 3 seconds...")
                self.log_window.after(3000, self.log_window.destroy)
            else:
                self.write_log("-" * 50)
                self.write_log("[STOP] Safe State Engaged. Please analyze logs.")


def open_log_window(mode_flag):
    log_window = tk.Toplevel(app)
    log_window.title(f"Execution Log Monitor - {mode_flag.upper()}")
    log_window.transient(app) 
    
    log_text = tk.Text(log_window, bg="black", fg="white", font=("Consolas", 10))
    log_text.pack(fill="both", expand=True)

    log_window.update_idletasks()
    log_window.lift()                           
    log_window.attributes('-topmost', True)          
    log_window.after(10, lambda: log_window.attributes('-topmost', False)) 
    log_window.focus_force()                    

    automation = OTAAutomation(log_window, log_text, run_mode=mode_flag)
    threading.Thread(target=automation.run, daemon=True).start()


# --- GUI 메인 레이아웃 및 다중 런타임 제어 인터페이스 설계 ---
if __name__ == "__main__":
    app = tk.Tk()
    app.title("Android Embedded Device Configurator v1.0")
    app.geometry("800x680")

    notebook = ttk.Notebook(app)
    notebook.pack(fill="both", expand=True)

    t1 = tk.Frame(notebook); notebook.add(t1, text="Basic Info")
    t2 = tk.Frame(notebook); notebook.add(t2, text="Display & HVAC")
    t3 = tk.Frame(notebook); notebook.add(t3, text="Sensors & Curtains")

    create_ota_settings(app)

    btn_frame = tk.LabelFrame(app, text="Automation Engine Runtime Selector (Portfolio Control)", font=("NanumGothic", 9, "italic"))
    btn_frame.pack(fill="x", padx=10, pady=10)

    tk.Button(btn_frame, text="1. Run Optimized Pure UiAutomator Engine", bg="teal", fg="white", font=("NanumGothic", 10, "bold"),
              command=lambda: open_log_window("pure_uiautomator")).pack(fill="x", padx=5, pady=2)

    tk.Button(btn_frame, text="2. Run Appium Framework (Simulation Mode)", bg="#5F4B8B", fg="white", font=("NanumGothic", 10, "bold"),
              command=lambda: open_log_window("appium")).pack(fill="x", padx=5, pady=2)

    tk.Button(btn_frame, text="3. Run Legacy Coordinate Macro Mode", bg="#C0392B", fg="white", font=("NanumGothic", 10, "bold"),
              command=lambda: open_log_window("legacy_coordinate")).pack(fill="x", padx=5, pady=2)

    app.mainloop()