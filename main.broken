from flask import Flask
import requests
import socket
import time
import os

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
# UTILS
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


# ======================
# ECOwitt FETCH
# ======================
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
# SAFE GET (ANTI BREAK)
# ======================
def pick(*values):
    for v in values:
        try:
            if v is None:
                continue
            return float(v)
        except:
            continue
    return 0.0


# ======================
# PACKET BUILDER (IMMUNE)
# ======================
def build_packet(data):

    d = data.get("data", data)

    # ----------------------
    # 🌡 OUTDOOR
    # ----------------------
    outdoor = (
        d.get("outdoor") or
        d.get("wh65") or
        d.get("wh40") or
        d.get("piezo") or
        d
    )

    temp = pick(
        outdoor.get("temperature"),
        outdoor.get("temp"),
        d.get("temperature")
    )

    humidity = pick(
        outdoor.get("humidity"),
        d.get("humidity")
    )

    # ----------------------
    # 🌬 WIND
    # ----------------------
    wind = d.get("wind") or d

    wind_speed = pick(
        wind.get("wind_speed"),
        wind.get("speed"),
        d.get("wind_speed")
    )

    wind_dir = pick(
        wind.get("wind_direction"),
        wind.get("dir"),
        d.get("wind_direction")
    )

    # ----------------------
    # 🌡 PRESSURE
    # ----------------------
    pressure = d.get("pressure") or d

    baro = pick(
        pressure.get("relative"),
        pressure.get("pressure"),
        d.get("pressure")
    )

    # ----------------------
    # 🌧 RAIN (PIEZO SAFE)
    # ----------------------
    rain = (
        d.get("rainfall") or
        d.get("rain") or
        d.get("rain_piezo") or
        d
    )

    rain_1h = int(pick(
        rain.get("rain_rate"),
        rain.get("hourly"),
        rain.get("last_hour")
    ))

    rain_24h = int(pick(
        rain.get("daily"),
        rain.get("dailyRain")
    ))

    rain_midnight = int(pick(
        rain.get("event"),
        rain.get("midnight")
    ))

    # ----------------------
    # 📍 COORDINATE
    # ----------------------
    lat = to_lat(LAT)
    lon = to_lon(LON)

    temp_f = int((temp * 9/5) + 32)

    # ----------------------
    # 📡 APRS WX PACKET
    # ----------------------
    packet = (
        f"{CALLSIGN}>APRS,TCPIP*:="
        f"{lat}/{lon}_"
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
# ENDPOINT
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
        return "OK"
    except Exception:
        return "ERR"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
