import sys
if "lib" not in sys.path:
    sys.path.append("lib")

from machine import Pin, SoftI2C,PWM
from lcd_api import LcdApi
from i2c_lcd import I2cLcd
from ds3231 import DS3231
from time import sleep
import time
import os
import dht
import utime

#================= อุณหภูมิ =================
sensor = dht.DHT22(Pin(18))
sensor.measure()
temp = sensor.temperature()


# ================= I2C LCD =================
I2C_ADDR = 0x27
totalRows = 2
totalColumns = 16
i2c = SoftI2C(scl=Pin(22), sda=Pin(21), freq=100000)
lcd = I2cLcd(i2c, I2C_ADDR, totalRows, totalColumns)
# ================= RTC DS3231 =================
date = DS3231(i2c)
# ================= Keypad =================
keyMatrix = [
    ['1','2','3','A'],
    ['4','5','6','B'],
    ['7','8','9','C'],
    ['*','0','#','D']
]
rowPins = [12,13,14,15]
colPins = [26,27,32,33]
rows = [Pin(r, Pin.OUT) for r in rowPins]
cols = [Pin(c, Pin.IN, Pin.PULL_DOWN) for c in colPins]

# ================= DC-Motor =================
EN_pin = Pin(5, Pin.OUT)
PWM1 = PWM(Pin(16), freq=5000)
PWM2 = PWM(Pin(17), freq=5000)

# ================= Global Variables =================
data = {
    "startTime1": 0,
    "stopTime1": 0,
    "startTime2": 0,
    "stopTime2": 0,
    "startTemp": 0,
    "stopTemp": 0,
    "speed": 0,
    "percen_speed": 0,
    "fanDirection": "L",
    "timer": "off",
    "timeMode": "currentTime",
    "state": False
}

DATA_FILE = "data.txt"
display_toggle = True
last_switch = utime.ticks_ms()

# ===================== Functions =====================

def scanKeypad():
    for i, row in enumerate(rows):
        row.value(1)
        for j, col in enumerate(cols):
            if col.value() == 1:
                row.value(0)
                return keyMatrix[i][j]
        row.value(0)
    return None
    

def readNumber():
    lcd.clear()
    lcd.move_to(0, 0)
    lcd.putstr("[ Enter number ]")
    lcd.move_to(0, 1)

    while scanKeypad():
        sleep(0.01)
    num = ""
    while True:
        key = scanKeypad()
        if key:
            if key.isdigit():
                num += key
                lcd.putstr(key)
            elif key == '#':
                if num:
                    return int(num)
                else:
                    return 0
            while scanKeypad():
                sleep(0.01)
            sleep(0.02)

        
def back_space(x, y, amount, key=' '):
    lcd.move_to(x, y)
    for i in range(amount):
        lcd.putstr(key)
    lcd.move_to(x, y)        
        
      
def motor_left_spin(speed):
    EN_pin.value(1)
    PWM1.duty(0)
    PWM2.duty(int(speed))

def motor_right_spin(speed):
    EN_pin.value(1)
    PWM1.duty(int(speed))
    PWM2.duty(0)

    
def set_direction():
    lcd.clear()
    lcd.putstr(">>Fan Direction ")
    lcd.move_to(0, 1)
    lcd.putstr(" 1:Left 2:Right ")
    while True:
        key = scanKeypad()
        if key == '1':
            data["fanDirection"] = "L"
            lcd.clear()
            lcd.putstr("Direction: Left")
            sleep(1)
            break
        elif key == '2':
            data["fanDirection"] = "R"
            lcd.clear()
            lcd.putstr("Direction: Right")
            sleep(1)
            break

    
def motor_off():
    EN_pin.value(0)
    PWM1.duty(0)
    PWM2.duty(0)
    
def motor_on(direc):
    if direc == -1:
        motor_left_spin(data["speed"])
        data["fanDirection"] = "L"
    elif direc == 1:
        motor_right_spin(data["speed"])
        data["fanDirection"] = "R"

    
def motor_speed_set():
    lcd.clear()
    lcd.putstr("Set (1-100): ")
    number = readNumber()
    
    if number > 100:
        lcd.clear()
        lcd.putstr("Out of range.")
        lcd.move_to(0, 1)
        lcd.putstr("press '*' ")
        while True:
            key = scanKeypad()
            if key == '*':
                while scanKeypad():
                    sleep(0.01)
                break
            sleep(0.01)
    else:
        data["speed"] = (7.23 * number) + 300
        data["percen_speed"] = number
    
    if data["fanDirection"] == "R" and data["state"]:
        motor_right_spin(data["speed"])
    elif data["fanDirection"] == "L" and data["state"]:
        motor_left_spin(data["speed"])


def device_control(state):
    """เปิดหรือปิดพัดลมตามสถานะ"""
    if state == 1:
        if data["fanDirection"] == "L":
            motor_left_spin(data["speed"])
            data["status"] = "Left"
        else:
            motor_right_spin(data["speed"])
            data["status"] = "Right"
        data["state"] = True
    else:
        motor_off()
        data["state"] = False

def read_time_number():
    while scanKeypad():
        sleep(0.01)
    num = ""
    lcd.show_cursor()
    lcd.blink_cursor_on()
    while True:
        key = scanKeypad()
        if key:
            if key.isdigit() and len(num) < 2:
                num += key
                lcd.putstr(key)
                if len(num) == 2:
                    lcd.hide_cursor()
            elif (key == '#') and num:
                return int(num)
            while scanKeypad():
                sleep(0.01)
            sleep(0.02)

def show_temp():
    sensor.measure()
    temp = sensor.temperature()
    lcd.clear()
    lcd.putstr(f"Temp: {temp:.1f} C")
    lcd.move_to(0, 1)
    lcd.putstr(f"Set: {data['startTemp']}-{data['stopTemp']} C")
    sleep(2)
    while not scanKeypad():
        sleep(0.05)
 
        
def set_temp(mode):
    lcd.clear()
    lcd.putstr("  Set Temp (C): ")
    value = readNumber()
    if mode == "start":
        data["startTemp"] = value
    else:
        data["stopTemp"] = value
    lcd.clear()
    mode_name = "Start" if mode == "start" else "Stop"
    lcd.putstr(f"  [{mode_name} Temp] ")
    lcd.move_to(0, 1)
    lcd.putstr(f"   >> {value}C << ")
    sleep(1)
        
def get_time():
    while scanKeypad():
        sleep(0.01)

    lcd.move_to(4, 1)
    
    hour = read_time_number()
    while hour > 23:
        back_space(4, 1, 2, '0')
        hour = read_time_number()
    lcd.move_to(7, 1)
    
    minute = read_time_number()
    while minute > 59:
        back_space(7, 1, 2, '0')
        minute = read_time_number()
    lcd.move_to(10, 1)
    
    second = read_time_number()
    while second > 59:
        back_space(10, 1, 2, '0')
        second = read_time_number()
        
    lcd.hide_cursor()
    lcd.clear()
        
    return hour, minute, second


def setTime(mode):
    current = date.datetime()
    current_hour = current[4]
    current_minute = current[5]
    current_second = current[6]
    lcd.clear()
    
    lcd.putstr(f"Set Time {mode}  ")
        
    lcd.move_to(1, 1)
    lcd.putstr(f"  [{current_hour:02}:{current_minute:02}:{current_second:02}]  ")
    
    hour, minute, second = get_time()
    
    if mode == "now":
        current = date.datetime()
        new_date = [current[0], current[1], current[2], hour, minute, second, current[3]]
        date.datetime(new_date)
    elif mode == "start1":
        data["startTime1"] = (hour * 3600) + (minute * 60) + second
    elif mode == "stop1":
        data["stopTime1"] = (hour * 3600) + (minute * 60) + second
    elif mode == "start2":
        data["startTime2"] = (hour * 3600) + (minute * 60) + second
    elif mode == "stop2":
        data["stopTime2"] = (hour * 3600) + (minute * 60) + second


def time_convert(mode):
    time_value = 0
    if mode == "startTime1":
        time_value = data['startTime1']
    elif mode == "stopTime1":
        time_value = data['stopTime1']
    elif mode == "startTime2":
        time_value = data['startTime2']
    elif mode == "stopTime2":
        time_value = data['stopTime2']
        
    if time_value is None: 
        time_value = 0
        
    hour = time_value // 3600
    minute = (time_value % 3600) // 60
    second = time_value % 60
        
    return hour, minute, second

def showTime(mode):
    lcd.clear()
    if mode == "Time1":
        hour, minute, second = time_convert("startTime1")
        lcd.putstr(f"[1]  S:{hour:02}:{minute:02}:{second:02}")
        lcd.move_to(0, 1)
        hour, minute, second = time_convert("stopTime1")
        lcd.putstr(f"     E:{hour:02}:{minute:02}:{second:02}")
    elif mode == "Time2":
        hour, minute, second = time_convert("startTime2")
        lcd.putstr(f"[2]  S:{hour:02}:{minute:02}:{second:02}")
        lcd.move_to(0, 1)
        hour, minute, second = time_convert("stopTime2")
        lcd.putstr(f"     E:{hour:02}:{minute:02}:{second:02}")

    while not scanKeypad():
        sleep(0.05)

        
def device_timer():
    current = date.datetime()
    current_time = (current[4] * 3600) + (current[5] * 60) + current[6]
    sensor.measure()
    temp = sensor.temperature()

    if data['timer'] == "on":
        start1 = data['startTime1']
        stop1 = data['stopTime1']
        start2 = data['startTime2']
        stop2 = data['stopTime2']

        start_temp = data['startTemp']
        stop_temp = data['stopTemp']

        in_time1 = start1 <= current_time < stop1
        in_time2 = start2 <= current_time < stop2
        in_temp_range = start_temp <= temp < stop_temp

        should_run = (in_time1 or in_time2) and in_temp_range

        if should_run:
            if data["fanDirection"] == "L":
                motor_left_spin(data["speed"])
            else:
                motor_right_spin(data["speed"])
            data['state'] = True
            backup_data()
        elif data['state']:
            motor_off()
            data['state'] = False
            backup_data()
    else:
        if data['state']:
            motor_off()
            data['state'] = False




        
def getMode(key):
    modeMap = {
        '1': "SetTime",
        '2': "SetSpeed",
        '3': "SetDir",
        '4': "TimerOff",
        '5': "TimerOn",
        '6': "SetStartTime1",
        '7': "SetStopTime1",
        '8': "ShowTime1",
        '9': "SetStartTime2",
        '10': "SetStopTime2",
        '11': "ShowTime2",
        '12': "SetStartTemp",
        '13': "SetStopTemp",
        '14': "ShowTemp"
    }
    return modeMap.get(str(key), "")

def command(mode):
    if mode == "SetTime": #1
        setTime("now")
        data['timeMode'] = "currentTime"
    elif mode == "SetSpeed": #2
        motor_speed_set()
    elif mode == "SetDir": #3 
        set_direction()
    elif mode == "TimerOff": #4
        data['timer'] = "off" 
    elif mode == "TimerOn": #5
        data['timer'] = "on"
    elif mode == "SetStartTime1": #6
        setTime("start1")
    elif mode == "SetStopTime1": #7
        setTime("stop1")
    elif mode == "ShowTime1": #8
        showTime("Time1")
    elif mode == "SetStartTime2": #9
        setTime("start2")
    elif mode == "SetStopTime2": #10
        setTime("stop2")
    elif mode == "ShowTime2":  #11
        showTime("Time2")
    elif mode == "SetStartTemp":  #12
        set_temp("start")
    elif mode == "SetStopTemp":  #13
        set_temp("stop")
    elif mode == "ShowTemp":  #14
        show_temp()
    backup_data()
    

def display_status():
    global display_toggle, last_switch
    now_ms = utime.ticks_ms()
    sensor.measure()
    temp = sensor.temperature()
    current = date.datetime()
    # ตรวจสอบสลับหน้าจอทุก 5 วินาที
    if utime.ticks_diff(now_ms, last_switch) >= 5000:
        last_switch = now_ms
        display_toggle = not display_toggle
        lcd.clear()  
    # แสดงข้อมูลตาม toggle แต่เวลา/อุณหภูมิอัพเดตทุก loop
    if display_toggle:
        lcd.move_to(0, 0)
        lcd.putstr(f"   [{current[4]:02}:{current[5]:02}:{current[6]:02}]   ")
        lcd.move_to(0, 1)
        lcd.putstr(f"{temp:.1f}C Timer: {data['timer']}")
    else:
        lcd.move_to(0, 0)
        lcd.putstr(f"  Speed  : {data['percen_speed']}%")
        lcd.move_to(0, 1)
        lcd.putstr(f"Direction: {'Left' if data['fanDirection']=='L' else 'Right'}")

def backup_data():
    with open(DATA_FILE, "w") as f:
        f.write(str(data))

def load_data():
    global data
    if DATA_FILE in os.listdir():
        with open(DATA_FILE, "r") as f:
            content = f.read()
            try:
                data.update(eval(content))
            except:
                pass

load_data()
while True:
    key = scanKeypad()
    if key == '*':
        number = readNumber()
        if number:
            mode = getMode(str(number))
            if mode:
                command(mode)
            else:
                lcd.clear()
                lcd.putstr("Invalid Mode")
                sleep(1)
        sleep(0.05)
    device_timer()
    display_status()

    sleep(0.2)

# ถ้าtimer off ให้หมุนเลยแต่ถ้าonให้ตามเวลา