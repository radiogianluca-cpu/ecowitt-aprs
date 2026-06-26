from flask import Flask
import requests
import socket
import os

app = Flask(__name__)

# ======================
# CONFIG (Lettura variabili ambiente)
# ======================
CALLSIGN = os.getenv("CALLSIGN")
PASSCODE = os.getenv("APRS_PASSCODE")

LAT = float(os.getenv("LAT", 0.0))
LON = float(os.getenv("LON", 0.0))

APRS_SERVER = "rotate.aprs2.net"
APRS_PORT = 14580

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
# FETCH ECOWITT
# ======================
def get_ecowitt():
    # RIPRISTINATO: L'URL originale corretto che usavi prima
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
# 🌧️ FIX PIOGGIA
# ======================
def safe_rain(data):
    d = data.get("data", {})

    return (
        d.get("rainfall_piezo") or
        d.get("rain_piezo") or
        d.get("rain") or
        d.get("rainfall") or
        {}
    )


# ======================
# BUILD APRS PACKET (OTTIMIZZATO SENZA DOPPIA CONVERSIONE)
# ======================
def build_packet(data):
    outdoor = data.get("data", {}).get("outdoor", {})
    pressure = data.get("data", {}).get("pressure", {})
    wind = data.get("data", {}).get("wind", {})

    # 🌡️ PRENDIAMO IL VALORE FAHRENHEIT DIRETTO PER EVITARE SCARTI
    raw_temp = to_float(outdoor.get("temperature") or outdoor.get("tempf"))
    
    # Se per qualche motivo il dato Ecowitt fosse in Celsius (es. sotto i 60), lo converte, altrimenti usa il nativo
    if raw_temp < 60: 
        temp_f = round((raw_temp * 9 / 5) + 32)
    else:
        temp_f = round(raw_temp)

    humidity = to_float(outdoor.get("humidity"))
    baro = normalize_pressure(pressure.get("relative"))

    # 🌬️ VENTO
    wind_speed = to_float(wind.get("wind_speed"))
    wind_dir = to_float(wind.get("wind_direction"))
    wind_gust = to_float(wind.get("wind_gust"))

    # 🌧️ PIOGGIA
    rain = data.get("data", {}).get("rainfall_piezo", {})

    rain_1h = int(to_float(rain.get("1_hour")) * 100)
    rain_24h = int(to_float(rain.get("24_hours")) * 100)

    # 📍 COORDINATE
    lat = to_lat(LAT)
    lon = to_lon(LON)

    symbol = "_"

    packet = (
        f"{CALLSIGN}>APRS,TCPIP*:"
        f"={lat}/{lon}{symbol}"
        f"{round(wind_dir):03d}/{round(wind_speed):03d}"
        f"g{round(wind_gust):03d}"
        f"t{temp_f:03d}" # Invierà esattamente l'arrotondamento del valore nativo Ecowitt
        f"r{rain_1h:03d}"
        f"p{rain_24h:03d}"
        f"h{round(humidity):02d}"
        f"b{round(baro * 10):05d}"
    )

    return packet

# ======================
# SEND APRS
# ======================
def send_aprs(packet):
    s = socket.socket()
    s.settimeout(10)

    s.connect((APRS_SERVER, APRS_PORT))

    login = f"user {CALLSIGN} pass {PASSCODE} vers ecowitt-aprs 1.0\n"

    s.send(login.encode())
    s.send((packet + "\n").encode())

    s.close()


# ======================
# ROOT
# ======================
@app.route("/")
def home():
    return "ECOWITT APRS OK - use /run"


# ======================
# SEND WX
# ======================
@app.route("/run")
def run():
    try:
        data = get_ecowitt()
        packet = build_packet(data)
        send_aprs(packet)
        return "OK"
    except Exception:
        return "ERR"


# ======================
# DEBUG
# ======================
@app.route("/debug")
def debug():
    try:
        data = get_ecowitt()
        d = data.get("data", {})

        return {
            "keys_top_level": list(d.keys()),
            "outdoor": d.get("outdoor"),
            "wind": d.get("wind"),
            "pressure": d.get("pressure"),
            "rainfall": d.get("rainfall"),
            "rain": d.get("rain"),
            "rain_piezo": d.get("rain_piezo"),
            "rainfall_piezo": d.get("rainfall_piezo"),
            "config_coords": {"lat": LAT, "lon": LON},
        }

    except Exception as e:
        return {"error": str(e)}

# ======================
# DEBUG ISOLATO (CORRETTO)
# ======================
@app.route("/debug-test")
def debug_test():
    try:
        # RIPRISTINATO: URL originale corretto anche qui
        url = "https://api.ecowitt.net/api/v3/device/real_time"
        params = {
            "application_key": APP_KEY,
            "api_key": API_KEY,
            "mac": MAC,
            "call_back": "all"
        }
        
        r = requests.get(url, params=params, timeout=15)
        
        try:
            json_data = r.json()
            return {
                "RISPOSTA_CORRETTA_JSON": True,
                "HTTP_STATUS": r.status_code,
                "DATA": json_data
            }
        except Exception:
            return {
                "RISPOSTA_CORRETTA_JSON": False,
                "HTTP_STATUS": r.status_code,
                "TESTO_GREZZO_SERVER": r.text[:500],
                "CHIAVI_CARICATE": {
                    "HAS_APP_KEY": bool(APP_KEY),
                    "HAS_API_KEY": bool(API_KEY),
                    "HAS_MAC": bool(MAC)
                }
            }

    except Exception as e:
        return {"errore_di_connessione": str(e)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
