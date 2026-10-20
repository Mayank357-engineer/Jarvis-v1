
import serial
import time

ESP32_PORT = "COM4"
BAUD_RATE = 115200


def send_to_esp32(message):
    esp32 = None

    try:
        esp32 = serial.Serial(
            ESP32_PORT,
            BAUD_RATE,
            timeout=2,
            dsrdtr=False
        )

        esp32.dtr = False
        esp32.rts = False

        time.sleep(2)

        esp32.write((message + "\n").encode("utf-8"))
        esp32.flush()

        print(f"ESP32 message sent: {message}")
        return True

    except serial.SerialException as error:
        print(f"ESP32 connection error: {error}")
        return False

    finally:
        if esp32 is not None and esp32.is_open:
            esp32.close()
