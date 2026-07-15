from flask import Flask, render_template, request, jsonify
import ephem
import math
from datetime import datetime, timedelta
import requests
from timezonefinder import TimezoneFinder
import pytz

app = Flask(__name__)

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Glyph symbols for display
ZODIAC_SYMBOLS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
}

PLANET_SYMBOLS = {
    "Moon": "☽",
}

PLANETS = {
    "Moon": ephem.Moon,
}

# Tertiary progression: one day after birth = one sidereal month of life
SIDEREAL_MONTH_DAYS = 27.321661   # Tertiary I
# Minor progression: one sidereal month after birth = one year of life (converse of Tertiary I)
TROPICAL_YEAR_DAYS  = 365.242190  # Tertiary II


def ecliptic_longitude(planet_class, ephem_date):
    body = planet_class()
    body.compute(ephem_date)
    ecl = ephem.Ecliptic(body, epoch=ephem_date)
    return math.degrees(ecl.lon) % 360


def longitude_to_zodiac(lon_deg):
    sign_index = int(lon_deg / 30) % 12
    degree_in_sign = lon_deg % 30
    degrees = int(degree_in_sign)
    minutes = int((degree_in_sign - degrees) * 60)
    seconds = int(((degree_in_sign - degrees) * 60 - minutes) * 60)
    sign = ZODIAC_SIGNS[sign_index]
    return sign, degrees, minutes, seconds


def to_ephem_date(dt_utc):
    return ephem.Date(dt_utc.strftime("%Y/%m/%d %H:%M:%S"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/geocode")
def geocode():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 6, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": "TertiaryProgressionApp/1.0", "Accept-Language": "en"},
            timeout=5,
        )
        data = resp.json()
        results = [
            {
                "name": item["display_name"],
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            }
            for item in data
        ]
        return jsonify(results)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/timezone")
def get_timezone():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        return jsonify({"timezone": tz_name or "UTC"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    required = ["lat", "lon", "birth_date", "birth_time", "progression_date"]
    missing = [f for f in required if f not in data or str(data[f]).strip() == ""]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return jsonify({"error": "Could not determine timezone for this location"}), 400

    local_tz = pytz.timezone(tz_name)

    try:
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        # Ambiguous due to DST — ask client to specify; default to DST=False (standard time)
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive, is_dst=False)
    except pytz.exceptions.NonExistentTimeError:
        # Clocks skipped this hour (spring forward) — shift forward
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive + timedelta(hours=1), is_dst=True)

    birth_utc = birth_local.astimezone(pytz.utc)

    prog_time_str = data.get("progression_time", "12:00") or "12:00"
    try:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive, is_dst=False)
    except pytz.exceptions.NonExistentTimeError:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive + timedelta(hours=1), is_dst=True)

    prog_utc = prog_local.astimezone(pytz.utc)

    elapsed_days = (prog_utc - birth_utc).total_seconds() / 86400.0
    if elapsed_days < 0:
        return jsonify({"error": "Progression date must be after birth date"}), 400

    def compute_planets(progressed_utc):
        ephem_date = to_ephem_date(progressed_utc)
        planets_out = []
        for name, planet_class in PLANETS.items():
            try:
                lon = ecliptic_longitude(planet_class, ephem_date)
                sign, deg, mins, secs = longitude_to_zodiac(lon)
                planets_out.append(
                    {
                        "planet": name,
                        "symbol": PLANET_SYMBOLS.get(name, ""),
                        "longitude": round(lon, 4),
                        "sign": sign,
                        "sign_symbol": ZODIAC_SYMBOLS.get(sign, ""),
                        "degrees": deg,
                        "minutes": mins,
                        "seconds": secs,
                        "position": f"{deg}° {mins:02d}' {secs:02d}\" {sign}",
                    }
                )
            except Exception as exc:
                planets_out.append({"planet": name, "error": str(exc)})
        return planets_out

    # Tertiary I: 1 sidereal month of life = 1 day after birth
    t1_offset = elapsed_days / SIDEREAL_MONTH_DAYS
    t1_utc = birth_utc + timedelta(days=t1_offset)

    # Tertiary II (Minor progression): 1 year of life = 1 sidereal month after birth
    age_years = elapsed_days / TROPICAL_YEAR_DAYS
    t2_offset = age_years * SIDEREAL_MONTH_DAYS
    t2_utc = birth_utc + timedelta(days=t2_offset)

    # UTC offset at birth time for display
    utc_offset = birth_local.utcoffset()
    offset_hours = int(utc_offset.total_seconds() // 3600)
    offset_mins = int((utc_offset.total_seconds() % 3600) // 60)
    offset_str = f"UTC{offset_hours:+03d}:{offset_mins:02d}"

    return jsonify(
        {
            "timezone": tz_name,
            "utc_offset_at_birth": offset_str,
            "birth_local": birth_local.strftime("%Y-%m-%d %H:%M %Z"),
            "birth_utc": birth_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "progression_date": data["progression_date"],
            "elapsed_days": round(elapsed_days, 4),
            "tertiary1": {
                "label": "Tertiary I (Sidereal Month)",
                "offset_days": round(t1_offset, 6),
                "progressed_chart_date_utc": t1_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "planets": compute_planets(t1_utc),
            },
            "tertiary2": {
                "label": "Tertiary II (Minor Progression)",
                "offset_days": round(t2_offset, 6),
                "progressed_chart_date_utc": t2_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "planets": compute_planets(t2_utc),
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
