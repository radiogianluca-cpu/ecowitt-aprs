from flask import Flask
import requests
import socket
import time
import os
from datetime import datetime

app = Flask(__name__)

# ======================
# CONFIG
# ======================
CALLSIGN = "IU0VXM-13"
PASSCODE = "21164"

APRS_SERVER = "rotate.aprs2.net"
APRS_PORT = 14580

LAT = 41.97917
LON = 12.04167

APP_KEY = os.getenv("ECOWITT_APP_KEY")
API_KEY = os.getenv("ECOWITT_API_KEY")
MAC = os.getenv("ECOWITT_MAC")


# ======================
# UTIL
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


def to_float(x):
    try:
        return float(x)
    except:
        return 0.0


def normalize_temp(outdoor):
    return to_float(outdoor.get("temperature"))


def normalize_pressure(p):
    return to_float(p)


def get_ecowitt():
    url = "https://api.ecowitt.net/api/v3/device/real_time"

    params = {
        "application_key": APP_KEY,
        "api_key": API_KEY,
        "mac": MAC,
        "call_back": "all"
    }

    r = requests.get(url, params=params, timeout=10)
    return r.json()


# ======================
# PACKET BUILDER
# ======================
def build_packet(data):
    outdoor = data.get("data", {}).get("outdoor", {})
    pressure = data.get("data", {}).get("pressure", {})
    wind = data.get("data", {}).get("wind", {})
    rain_data = data.get("data", {})

    # 🌡 temp / humidity / pressure
    temp = normalize_temp(outdoor)
    humidity = to_float(outdoor.get("humidity"))
    baro = normalize_pressure(pressure.get("relative"))

    # 🌬 wind
    wind_speed = to_float(wind.get("wind_speed"))
    wind_dir = to_float(wind.get("wind_direction"))

    # 🌧 RAIN (PIEZO SAFE)
    rain = (
        rain_data.get("rainfall", {}) or
        rain_data.get("rain", {}) or
        rain_data.get("rain_piezo", {}) or
        {}
    )

    rain_1h = int(to_float(
        rain.get("rain_rate") or
        rain.get("hourly") or
        rain.get("hourlyRain") or
        0
    ))

    rain_24h = int(to_float(
        rain.get("daily") or
        rain.get("dailyRain") or
        rain.get("24h") or
        0
    ))

    rain_midnight = int(to_float(
        rain.get("event") or
        rain.get("midnight") or
        rain.get("total") or
        0
    ))

    # APRS format values
    lat = to_lat(LAT)
    lon = to_lon(LON)

    temp_f = int((temp * 9/5) + 32)

    # ======================
    # APRS WX PACKET
    # ======================
    packet = (
        f"{CALLSIGN}>APRS,TCPIP*:"
        f"={lat}/{lon}_"
        f"{int(wind_dir):03d}/{int(wind_speed):03d}"
        f"g000"
        f"t{temp_f:03d}"
        f"r{rain_1h:03d}"
        f"p{rain_24h:03d}"
        f"P{rain_midnight:03d}"
        f"h{int(humidity):02d}"
        f"b{int(baro * 10):05d}"
    )

    return packet


# ======================
# SEND APRS
# ======================
def send_aprs(packet):
    s = socket.socket()
    s.connect((APRS_SERVER, APRS_PORT))

    login = f"user {CALLSIGN} pass {PASSCODE} vers ecowitt 1.0\n"
    s.send(login.encode())

    time.sleep(2)
    s.send((packet + "\n").encode())
    s.close()


# ======================
# ENDPOINTS
# ======================
@app.route("/")
def home():
    return "ECOWITT APRS OK"


@app.route("/run")
def run():
    try:
        data = get_ecowitt()
        packet = build_packet(data)
        send_aprs(packet)

        # IMPORTANT: output minimal per cron-job.org
        return "OK"

    except Exception:
        return "ERR"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
