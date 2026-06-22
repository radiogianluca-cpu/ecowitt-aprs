import requests
import socket
import os
import time

# ======================
# CONFIG
# ======================
CALLSIGN = os.getenv("CALLSIGN")
PASSCODE = os.getenv("APRS_PASSCODE")

APRS_SERVER = "rotate.aprs2.net"
APRS_PORT = 14580

LAT = 41.97917
LON = 12.04167

APP_KEY = os.getenv("ECOWITT_APP_KEY")
API_KEY = os.getenv("ECOWITT_API_KEY")
MAC = os.getenv("ECOWITT_MAC")


# ======================
# SAFE CONVERSION
# ======================
def to_float(x):
    try:
        if isinstance(x, dict):
            x = x.get("value", 0)
        return float(x)
    except:
        return 0.0


def to_int(x):
    return int(to_float(x))


# ======================
# TEMP NORMALIZATION
# ======================
def normalize_temp(outdoor):
    temp = outdoor.get("temperature") or outdoor.get("tempf")
    temp = to_float(temp)

    if temp > 60:
        temp = (temp - 32) * 5 / 9

    return temp


# ======================
# PRESSURE NORMALIZATION
# ======================
def normalize_pressure(p):
    p = to_float(p)

    if p < 900:
        p = p * 33.8639

    return p


# ======================
# COORDINATES
# ======================
def to_lat(lat):
    hemi = "N" if lat >= 0 else "S"
    lat = abs(lat)
    d = int(lat)
    m = (lat - d) * 60
    return f"{d:02d}{m:05.2f}{hemi}"


def to_lon(lon):
    hemi = "E" if lon >= 0 else "W"
    lon = abs(lon)
    d = int(lon)
    m = (lon - d) * 60
    return f"{d:03d}{m:05.2f}{hemi}"


# ======================
# FETCH ECOWITT
# ======================
def get_ecowitt():
    url = "https://api.ecowitt.net/api/v3/device/real_time"

    params = {
        "application_key": APP_KEY,
        "api_key": API_KEY,
        "mac": MAC,
        "call_back": "all"
    }

    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()

    return r.json()


# ======================
# APRS PACKET
# ======================
def build_packet(data):
    outdoor = data.get("data", {}).get("outdoor", {})
    pressure = data.get("data", {}).get("pressure", {})
    wind = data.get("data", {}).get("wind", {})

    temp = normalize_temp(outdoor)
    humidity = to_float(outdoor.get("humidity"))
    baro = normalize_pressure(pressure.get("relative"))

    wind_speed = to_float(wind.get("wind_speed"))
    wind_dir = to_float(wind.get("wind_direction"))
    wind_gust = to_float(wind.get("wind_gust"))

    rain = data.get("data", {}).get("rainfall_piezo", {})

    rain_1h = int(to_float(rain.get("1_hour")) * 100)
    rain_24h = int(to_float(rain.get("24_hours")) * 100)

    lat = to_lat(LAT)
    lon = to_lon(LON)

    temp_f = int((temp * 9/5) + 32)

    symbol = "_"

    packet = (
        f"{CALLSIGN}>APRS,TCPIP*:"
        f"={lat}/{lon}{symbol}"
        f"{to_int(wind_dir):03d}/{to_int(wind_speed):03d}"
        f"g{to_int(wind_gust):03d}"
        f"t{temp_f:03d}"
        f"r{rain_1h:03d}"
        f"p{rain_24h:03d}"
        f"h{to_int(humidity):02d}"
        f"b{int(baro * 10):05d}"
    )

    return packet


# ======================
# SEND APRS (MIGLIORATO)
# ======================
def send_aprs(packet):
    try:
        s = socket.socket()
        s.settimeout(10)

        s.connect((APRS_SERVER, APRS_PORT))

        login = (
            f"user {CALLSIGN} pass {PASSCODE} vers ecowitt-aprs 1.0\n"
        )

        s.send(login.encode())
        s.send((packet + "\n").encode())

    finally:
        s.close()


# ======================
# MAIN LOOP (WORKER)
# ======================
def main_loop():
    print("APRS Worker started...")

    while True:
        try:
            data = get_ecowitt()
            packet = build_packet(data)

            send_aprs(packet)

            print("Sent:", packet)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(60)  # ogni 60 secondi


# ======================
# START
# ======================
if __name__ == "__main__":
    main_loop()
