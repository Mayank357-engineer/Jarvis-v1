
import serial
import time

PORT = "COM4"
BAUD = 115200

try:
    esp32 = serial.Serial(
        PORT,
        BAUD,
        timeout=2,
        dsrdtr=False
    )

    # Prevent serial connection from resetting ESP32
    esp32.dtr = False
    esp32.rts = False

    time.sleep(2)

    message = input("Enter message for LCD: ")

    esp32.write((message + "\n").encode("utf-8"))
    esp32.flush()

    print("Message sent:", message)

    time.sleep(1)
    esp32.close()

except Exception as e:
    print("Error:", e)
