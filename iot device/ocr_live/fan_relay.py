"""
Raspberry Pi CPU fan relay control via GPIO.

Turns fan ON when CPU temperature >= 50 C and OFF when < 45 C (hysteresis). Runs in a background thread.
"""

import threading

TEMP_ON_C = 50.0
TEMP_OFF_C = 45.0
POLL_INTERVAL_SEC = 10
RELAY_PIN = 27

_fan_thread = None
_fan_stop = threading.Event()
_gpio_ok = False
_fan_enabled = False


def _read_cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return None


def _fan_loop():
    import RPi.GPIO as GPIO
    last_on = None
    GPIO_ON = GPIO.LOW
    GPIO_OFF = GPIO.HIGH
    while not _fan_stop.wait(timeout=POLL_INTERVAL_SEC):
        if not _fan_enabled or not _gpio_ok:
            continue
        temp = _read_cpu_temp_c()
        if temp is None:
            continue
        if last_on:
            want_on = temp >= TEMP_OFF_C
        else:
            want_on = temp >= TEMP_ON_C
        if want_on != last_on:
            last_on = want_on
            GPIO.output(RELAY_PIN, GPIO_ON if want_on else GPIO_OFF)
            print(f"[Fan relay] CPU {temp:.1f}°C -> {'ON' if want_on else 'OFF'}")


def init_fan_relay(gpio=RELAY_PIN):
    global _fan_thread, _fan_stop, _gpio_ok, _fan_enabled
    if _fan_thread is not None:
        return _fan_enabled
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio, GPIO.OUT)
        GPIO.output(gpio, GPIO.HIGH)
    except Exception:
        return False
    _gpio_ok = True
    _fan_stop.clear()
    _fan_enabled = True
    _fan_thread = threading.Thread(target=_fan_loop, daemon=True)
    _fan_thread.start()
    print(f"[Fan relay] Started (GPIO {gpio}, ON >= {TEMP_ON_C}°C, OFF < {TEMP_OFF_C}°C)")
    return True


def cleanup_fan_relay():
    global _fan_thread, _fan_stop, _gpio_ok, _fan_enabled
    _fan_enabled = False
    _fan_stop.set()
    if _fan_thread is not None:
        _fan_thread.join(timeout=POLL_INTERVAL_SEC + 2)
        _fan_thread = None
    if _gpio_ok:
        try:
            import RPi.GPIO as GPIO
            GPIO.output(RELAY_PIN, GPIO.HIGH)
            GPIO.cleanup()
        except Exception:
            pass
        _gpio_ok = False
    print("[Fan relay] Stopped")
