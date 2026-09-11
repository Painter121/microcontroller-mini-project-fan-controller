import network
import ufirebase as firebase
from machine import Pin, SoftI2C
try:
    from i2c_lcd import I2cLcd
except ImportError:
    from lcd_i2c import I2cLcd
from ds3231 import DS3231
import time
import ujson
import gc
import _thread
import bluetooth

gc.collect()

led = Pin(25, Pin.OUT)
sensor = Pin(19, Pin.IN)
i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=100000)
lcd = I2cLcd(i2c, 0x27, 2, 16)
rtc = DS3231(i2c)

keyMatrix = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]
rowPins = [4, 5, 12, 13]
colPins = [14, 15, 32, 33]
row = [Pin(pin, Pin.OUT) for pin in rowPins]
column = [Pin(pin, Pin.IN, Pin.PULL_DOWN) for pin in colPins]

def scanKeypad():
    for r in range(4):
        row[r].value(1)
        for c in range(4):
            if column[c].value():
                row[r].value(0)
                return keyMatrix[r][c]
        row[r].value(0)
    return None

def now_sec():
    t = rtc.datetime()
    return t[4] * 3600 + t[5] * 60 + t[6]

def now_hms():
    t = rtc.datetime()
    return t[4], t[5], t[6]

def is_in_range(now, start, stop):
    if start == stop: return False
    if start < stop: return start <= now < stop
    else: return now >= start or now < stop

def format_sec(sec):
    return "%02d:%02d:%02d" % (sec // 3600, (sec % 3600) // 60, sec % 60)

lcd_hold_until_ms = 0

def pad16(text):
    return (str(text) + " " * 16)[:16]

def lcd_show(line1, line2="", duration_ms=2000):
    global lcd_hold_until_ms
    lcd.move_to(0, 0); lcd.putstr(pad16(line1))
    lcd.move_to(0, 1); lcd.putstr(pad16(line2))
    lcd_hold_until_ms = time.ticks_add(time.ticks_ms(), duration_ms)

def lcd_status(motion):
    h, m, s = now_hms()
    mot_txt = "Detect" if motion else "Normal"
    lcd.move_to(0, 0); lcd.putstr(pad16("%02d:%02d:%02d %s" % (h, m, s, mot_txt)))
    bulb_txt = "ON " if led.value() else "OFF"
    tmr_txt  = "ON " if data["timer"] == 1 else "OFF"
    lcd.move_to(0, 1); lcd.putstr(pad16("Bulb:%s TMR:%s" % (bulb_txt, tmr_txt)))

def show_time_input(func, buf):
    titles = {
        "1": "Set Time",
        "5": "Set Start 1",
        "6": "Set Stop 1",
        "8": "Set Start 2",
        "9": "Set Stop 2"
    }
    title = titles.get(func, "Input Time:")
    p = buf + "_" * (6 - len(buf))
    val_str = f"{p[0:2]}:{p[2:4]}:{p[4:6]}"
    lcd_show(title, val_str, 10000)

DATA_FILE = "data.json"
data = {
    "timer": 0, "light_bulb": 0,
    "start1": 0, "stop1": 0,
    "start2": 0, "stop2": 0
}

def save():
    try:
        with open(DATA_FILE, "w") as f:
            ujson.dump(data, f)
    except:
        pass

def load():
    global data
    try:
        with open(DATA_FILE) as f:
            loaded = ujson.load(f)
            for k in data.keys():
                if k in loaded: data[k] = loaded[k]
    except:
        save()

db_status_out = {"sensor": 0, "bulb": 0, "cur_h": 0, "cur_m": 0, "cur_s": 0}
db_control_in = None
need_control_sync = False

def firebase_thread():
    global db_control_in, need_control_sync
    while True:
        try:
            firebase.put("status", db_status_out, bg=0)
            if need_control_sync:
                ctrl_update = {
                    "timer": data["timer"],
                    "bulb": data["light_bulb"],
                    "sh1": data["start1"] // 3600, "sm1": (data["start1"] % 3600) // 60, "ss1": data["start1"] % 60,
                    "eh1": data["stop1"] // 3600,  "em1": (data["stop1"] % 3600) // 60,  "es1": data["stop1"] % 60,
                    "sh2": data["start2"] // 3600, "sm2": (data["start2"] % 3600) // 60, "ss2": data["start2"] % 60,
                    "eh2": data["stop2"] // 3600,  "em2": (data["stop2"] % 3600) // 60,  "es2": data["stop2"] % 60,
                    "set_rtc": 0, "cur_h": 0, "cur_m": 0, "cur_s": 0
                }
                firebase.put("control", ctrl_update, bg=0)
                need_control_sync = False
            else:
                firebase.get("control", "v_control", bg=0)
                if type(firebase.v_control) is dict:
                    db_control_in = firebase.v_control
        except:
            pass
        time.sleep(2)
        gc.collect()

_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"), bluetooth.FLAG_NOTIFY)
_UART_RX = (bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"), bluetooth.FLAG_WRITE)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX))

ble = bluetooth.BLE()
ble.active(True)
((tx, rx),) = ble.gatts_register_services((_UART_SERVICE,))
connections = set()

def bt_send(msg):
    for c in connections:
        ble.gatts_notify(c, tx, msg + "\n")

def handle_bt_command(cmd):
    global data, need_control_sync

    cmd = cmd.strip().upper()
    parts = cmd.split(",")
    func = parts[0].strip()

    if func == "2":
        status_txt = "Detect" if sensor.value() else "Normal"
        bt_send("Motion: " + status_txt)
        lcd_show("BT Status:", status_txt, 3000)
    elif func == "3":
        data["timer"] = 0; save(); need_control_sync = True
        bt_send("TIMER OFF")
        lcd_show("BT: Func 3", "TIMER OFF")
    elif func == "4":
        data["timer"] = 1; save(); need_control_sync = True
        bt_send("TIMER ON")
        lcd_show("BT: Func 4", "TIMER ON")
    elif func == "7":
        msg = f"T1: {format_sec(data['start1'])} - {format_sec(data['stop1'])}"
        bt_send(msg)
        lcd_show("T1: " + format_sec(data["start1"]), "To: " + format_sec(data["stop1"]), 4000)
    elif func == "10":
        msg = f"T2: {format_sec(data['start2'])} - {format_sec(data['stop2'])}"
        bt_send(msg)
        lcd_show("T2: " + format_sec(data["start2"]), "To: " + format_sec(data["stop2"]), 4000)
    elif func in ["1", "5", "6", "8", "9"] and len(parts) == 4:
        try:
            hh, mm, ss = int(parts[1].strip()), int(parts[2].strip()), int(parts[3].strip())
            if hh <= 23 and mm <= 59 and ss <= 59:
                sec_val = hh * 3600 + mm * 60 + ss
                time_str = "%02d:%02d:%02d" % (hh, mm, ss)
                if func == "1":
                    t = rtc.datetime()
                    rtc.datetime((t[0], t[1], t[2], hh, mm, ss, t[3]))
                    lcd_show("BT: Set Time", time_str)
                    bt_send("Set Time OK")
                elif func == "5":
                    data["start1"] = sec_val; save(); need_control_sync = True
                    lcd_show("BT: Start 1", time_str)
                    bt_send("Start 1 OK")
                elif func == "6":
                    data["stop1"] = sec_val; save(); need_control_sync = True
                    lcd_show("BT: Stop 1", time_str)
                    bt_send("Stop 1 OK")
                elif func == "8":
                    data["start2"] = sec_val; save(); need_control_sync = True
                    lcd_show("BT: Start 2", time_str)
                    bt_send("Start 2 OK")
                elif func == "9":
                    data["stop2"] = sec_val; save(); need_control_sync = True
                    lcd_show("BT: Stop 2", time_str)
                    bt_send("Stop 2 OK")
        except:
            bt_send("Error Parsing Time")
    elif func == "ON":
        data["light_bulb"] = 1; save(); need_control_sync = True
        bt_send("BULB ON")
        lcd_show("BT: Manual", "BULB ON")
    elif func == "OFF":
        data["light_bulb"] = 0; save(); need_control_sync = True
        bt_send("BULB OFF")
        lcd_show("BT: Manual", "BULB OFF")
    else:
        bt_send("UNKNOWN COMMAND")

def bt_irq(event, ble_data):
    if event == 1:
        connections.add(ble_data[0])
    elif event == 2:
        connections.discard(ble_data[0])
    elif event == 3:
        cmd = ble.gatts_read(rx).decode().strip()
        handle_bt_command(cmd)

ble.irq(bt_irq)
ble.gap_advertise(100000, adv_data=b'\x02\x01\x06\x05\x09ESP32')

def connect_wifi(ssid="YOUR_WIFI_SSID", password="YOUR_WIFI_PASSWORD"):
    wifi = network.WLAN(network.STA_IF)
    wifi.active(False)
    time.sleep(1)
    wifi.active(True)
    wifi.connect(ssid, password)
    lcd.clear()
    lcd.putstr("Connecting WiFi")
    while not wifi.isconnected():
        time.sleep(1)
    lcd.clear()
    lcd.putstr("WiFi Connected")
    lcd.move_to(0, 1)
    lcd.putstr("BLE Ready")
    time.sleep(2)

# Main Initialization
load()
connect_wifi()
firebase.setURL("https://<YOUR_FIREBASE_PROJECT>.asia-southeast1.firebasedatabase.app/")
_thread.start_new_thread(firebase_thread, ())

input_mode, input_func, input_buffer, last_sec = 0, "", "", -1

while True:
    now = now_sec()
    h, m, s = now_hms()

    raw_motion = sensor.value()

    in_p1 = is_in_range(now, data["start1"], data["stop1"])
    in_p2 = is_in_range(now, data["start2"], data["stop2"])

    if data["timer"] == 1:
        motion = raw_motion if (in_p1 or in_p2) else 0
    else:
        motion = raw_motion

    if motion == 1:
        led.value(1)
    else:
        led.value(1 if data["light_bulb"] == 1 else 0)

    key = scanKeypad()
    if key:
        if key == '*':
            input_mode, input_buffer, input_func = 1, "", ""
            lcd_show("Cmd: _", "", 10000)
        elif key == '#':
            if input_mode == 1:
                if input_buffer in ["2", "3", "4", "7", "10"]:
                    if input_buffer == "2":
                        lcd_show("Status:", "Detect" if motion else "Normal", 3000)
                    elif input_buffer == "3":
                        data["timer"] = 0; save(); need_control_sync = True
                        lcd_show("Func 3", "TIMER OFF")
                    elif input_buffer == "4":
                        data["timer"] = 1; save(); need_control_sync = True
                        lcd_show("Func 4", "TIMER ON")
                    elif input_buffer == "7":
                        lcd_show("T1: " + format_sec(data["start1"]), "To: " + format_sec(data["stop1"]), 4000)
                    elif input_buffer == "10":
                        lcd_show("T2: " + format_sec(data["start2"]), "To: " + format_sec(data["stop2"]), 4000)
                    input_mode = 0
                elif input_buffer in ["1", "5", "6", "8", "9"]:
                    input_func, input_buffer, input_mode = input_buffer, "", 2
                    show_time_input(input_func, input_buffer)
            elif input_mode == 2 and len(input_buffer) == 6:
                hh, mm, ss = int(input_buffer[0:2]), int(input_buffer[2:4]), int(input_buffer[4:6])
                if hh <= 23 and mm <= 59 and ss <= 59:
                    sec_val = hh * 3600 + mm * 60 + ss
                    if input_func == "1":
                        t = rtc.datetime()
                        rtc.datetime((t[0], t[1], t[2], hh, mm, ss, t[3]))
                        lcd_show("Set Time OK", format_sec(sec_val))
                    elif input_func == "5":
                        data["start1"] = sec_val; save(); need_control_sync = True
                        lcd_show("Start 1 OK", format_sec(sec_val))
                    elif input_func == "6":
                        data["stop1"] = sec_val; save(); need_control_sync = True
                        lcd_show("Stop 1 OK", format_sec(sec_val))
                    elif input_func == "8":
                        data["start2"] = sec_val; save(); need_control_sync = True
                        lcd_show("Start 2 OK", format_sec(sec_val))
                    elif input_func == "9":
                        data["stop2"] = sec_val; save(); need_control_sync = True
                        lcd_show("Stop 2 OK", format_sec(sec_val))
                    input_mode = 0
        else:
            if input_mode == 1 and len(input_buffer) < 2:
                input_buffer += key
                lcd_show("Cmd: " + input_buffer + "_", "", 10000)
            elif input_mode == 2 and len(input_buffer) < 6:
                input_buffer += key
                show_time_input(input_func, input_buffer)
        time.sleep(0.3)

    if time.ticks_diff(lcd_hold_until_ms, time.ticks_ms()) <= 0:
        if input_mode != 0:
            input_mode = 0
        if s != last_sec:
            last_sec = s
            lcd_status(motion)

    if db_control_in and not need_control_sync:
        if int(db_control_in.get("set_rtc", 0)) == 1:
            t = rtc.datetime()
            rtc.datetime((t[0], t[1], t[2], int(db_control_in.get("cur_h", 0)), int(db_control_in.get("cur_m", 0)), int(db_control_in.get("cur_s", 0)), t[3]))
            firebase.put("control/set_rtc", 0, bg=1)
            lcd_show("Web: Set Time", "Updated")
        else:
            data["timer"] = int(db_control_in.get("timer", data["timer"]))
            data["light_bulb"] = int(db_control_in.get("bulb", data["light_bulb"]))
            data["start1"] = int(db_control_in.get("sh1", 0)) * 3600 + int(db_control_in.get("sm1", 0)) * 60 + int(db_control_in.get("ss1", 0))
            data["stop1"] = int(db_control_in.get("eh1", 0)) * 3600 + int(db_control_in.get("em1", 0)) * 60 + int(db_control_in.get("es1", 0))
            data["start2"] = int(db_control_in.get("sh2", 0)) * 3600 + int(db_control_in.get("sm2", 0)) * 60 + int(db_control_in.get("ss2", 0))
            data["stop2"] = int(db_control_in.get("eh2", 0)) * 3600 + int(db_control_in.get("em2", 0)) * 60 + int(db_control_in.get("es2", 0))
            save()
        db_control_in = None

    db_status_out.update({"cur_h": h, "cur_m": m, "cur_s": s, "sensor": motion, "bulb": led.value()})
    time.sleep_ms(100)
