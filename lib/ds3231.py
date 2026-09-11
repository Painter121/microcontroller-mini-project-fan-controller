"""
MicroPython DS3231 Real-Time Clock (RTC) Driver
Supports reading and setting datetime as:
[year, month, day, weekday, hour, minute, second]
"""
from machine import I2C

def bcd2dec(bcd):
    return (bcd // 16) * 10 + (bcd % 16)

def dec2bcd(dec):
    return (dec // 10) * 16 + (dec % 10)

class DS3231:
    DS3231_I2C_ADDR = 0x68

    def __init__(self, i2c):
        self.i2c = i2c

    def datetime(self, dt=None):
        if dt is None:
            # Read datetime from DS3231 registers (0x00 to 0x06)
            buf = self.i2c.readfrom_mem(self.DS3231_I2C_ADDR, 0x00, 7)
            sec = bcd2dec(buf[0] & 0x7F)
            minute = bcd2dec(buf[1] & 0x7F)
            hour = bcd2dec(buf[2] & 0x3F)
            weekday = bcd2dec(buf[3] & 0x07)
            day = bcd2dec(buf[4] & 0x3F)
            month = bcd2dec(buf[5] & 0x1F)
            year = bcd2dec(buf[6]) + 2000
            return [year, month, day, weekday, hour, minute, second]
        else:
            # Set datetime: [year, month, day, hour, minute, second, weekday]
            year = dt[0] % 100
            month = dt[1]
            day = dt[2]
            hour = dt[3]
            minute = dt[4]
            sec = dt[5]
            weekday = dt[6] if len(dt) > 6 else 1
            buf = bytearray([
                dec2bcd(sec),
                dec2bcd(minute),
                dec2bcd(hour),
                dec2bcd(weekday),
                dec2bcd(day),
                dec2bcd(month),
                dec2bcd(year)
            ])
            self.i2c.writeto_mem(self.DS3231_I2C_ADDR, 0x00, buf)
