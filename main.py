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
# SAFE CONVERSION LAYER
# ======================
def safe_float(x):
    try:
        if isinstance(x, dict):
            x = x.get("value", 0)
        return float(x)
    except:
        return 0.0


def safe_int(x):
    return int(safe_float(x))


# ======================
# APRS COORDS
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
    r.raise_for_status()
    return r.json()


# ======================
# BUILD WX PACKET (APRS STANDARD STYLE)
# ======================
def build_packet(data):
    outdoor = data.get("data", {}).get("outdoor", {})
    pressure = data.get("data", {}).get("pressure", {})
    wind = data.get("data", {}).get("wind", {})

    temp = safe_float(outdoor.get("temperature"))
    humidity = safe_float(outdoor.get("humidity"))
    baro = safe_float(pressure.get("relative"))

    wind_speed = safe_float(wind.get("wind_speed"))
    wind_dir = safe_float(wind.get("wind_direction"))

    lat = to_lat(LAT)
    lon = to_lon(LON)

    # APRS WX format (standard-ish, APRS.fi friendly)
    packet = (
        f"{CALLSIGN}>APRS,TCPIP*:!"
        f"{lat}/{lon}_"
        f"{safe_int(wind_dir):03d}/{safe_int(wind_speed):03d}"
        f"g000"
        f"t{safe_int(temp):02d}"
        f"r000p000"
        f"h{safe_int(humidity):02d}"
        f"b{int(baro * 10):05d}"
    )

    return packet


# ======================
# APRS SEND
# ======================
def send_aprs(packet):
    s = socket.socket()
    s.settimeout(10)

    s.connect((APRS_SERVER, APRS_PORT))

    login = f"user {CALLSIGN} pass {PASSCODE} vers ecowitt-aprs 1.0\n"
    s.send(login.encode())

    time.sleep(2)
    s.send((packet + "\n").encode())

    s.close()


# ======================
# MAIN ENDPOINT
# ======================
@app.route("/")
def run():
    try:
        data = get_ecowitt()
        packet = build_packet(data)
        send_aprs(packet)
        return f"OK -> {packet}"
    except Exception as e:
        return f"ERROR: {str(e)}"


# ======================
# START
# ======================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
