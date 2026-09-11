# Microcontroller Mini Project — Fan Controller

มินิโปรเจกต์ MicroPython: อ่าน DHT22, ตั้งค่าผ่าน keypad 4×4, แสดงผล LCD I2C,
อ่านเวลา DS3231 และควบคุมความเร็ว/ทิศทางมอเตอร์ด้วย PWM พร้อมบันทึกค่าใน data.txt

ต้นฉบับ: `micro controller/codeProject.txt` เปลี่ยนนามสกุลเป็น main.py และเติม # หน้าบันทึกภาษาไทยท้ายไฟล์ที่ทำให้เกิด SyntaxError โดยไม่แก้ logic

| อุปกรณ์ | GPIO ในโค้ด |
|---|---|
| DHT22 | 18 |
| I2C SCL / SDA | 22 / 21 |
| Keypad rows | 12, 13, 14, 15 |
| Keypad columns | 26, 27, 32, 33 |
| Motor enable / PWM | 5 / 16, 17 |

เปิด main.py ใน Thonny แล้วใช้กับบอร์ด MicroPython ที่รองรับ Pin, SoftI2C และ PWM.duty
ต้องติดตั้ง lcd_api.py, i2c_lcd.py และ ds3231.py บนบอร์ดเพิ่มเติม
พบไลบรารี LCD ในต้นฉบับแต่ยังไม่ยืนยันที่มา จึงไม่ได้รวมไฟล์ไลบรารีบุคคลอื่น; ไม่พบ ds3231.py ในชุดงาน
ตรวจได้เฉพาะ Python syntax ยังไม่ได้ทดสอบกับฮาร์ดแวร์


Repository แยกตามวิชา/หัวข้องานเรียน คงโค้ดและเครดิตเดิมไว้ ดูที่มาไฟล์ใน [provenance.json](provenance.json)
