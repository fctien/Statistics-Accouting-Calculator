"""單位換算（unit conversion）：長度、質量、溫度、壓力、能量、面積、體積、速度、時間。

每個單位以「換算到 SI 基準單位」的係數表示：基準值 = a * x + b。
非溫度單位 b = 0；溫度為仿射（affine）換算，基準為 K。
基準單位：m、kg、K、Pa、J、m²、m³、m/s、s。
係數出處：國際協議的精確定義值（in = 0.0254 m、lb = 0.45359237 kg、
atm = 101325 Pa、gal(US) = 231 in³、BTU 用 IT 定義等）。
需注意的取捨：
    mmHg 為習慣定義 133.322387415 Pa（13595.1 kg/m³ × 9.80665 m/s² × 1 mm）；
        與 torr（101325/760 = 133.3223684 Pa）有約 1.4e-7 的相對差異，不可混用；
    cal／kcal 用熱化學卡 1 cal = 4.184 J（與 Excel CONVERT 的 "c" 一致，
        而非 IT 卡 4.1868 J）；
    BTU 用 IT 定義 1055.05585262 J（與 Excel "BTU" 一致）；
    yr 定義為 365 天（非 365.2425）；
    t 為公噸（1000 kg）；台斤 0.6 kg、兩 37.5 g、坪 400/121 m² 為定義值。
僅用 CPython 與 MicroPython 都支援的功能。
"""
from engine.result import err, is_finite, ok

# 類別：(id, 中文名, 英文名)
_CATEGORIES = (
    ("length", "長度", "Length"),
    ("mass", "質量", "Mass"),
    ("temperature", "溫度", "Temperature"),
    ("pressure", "壓力", "Pressure"),
    ("energy", "能量", "Energy"),
    ("area", "面積", "Area"),
    ("volume", "體積", "Volume"),
    ("speed", "速度", "Speed"),
    ("time", "時間", "Time"),
)

_IN = 0.0254
_FT = 12 * _IN
_LB = 0.45359237
_GAL = 231 * _IN ** 3          # 美制加侖 = 231 立方英吋
_CAL = 4.184                   # 熱化學卡
_BTU = 1055.05585262           # IT BTU
_MPH = 1609.344 / 3600.0
_NMI = 1852.0
_ACRE = 4046.8564224           # 國際英畝 = 4840 平方碼
_ABS_ZERO_C = 273.15

# (id, 中文名, 英文名, 類別, a, b)
_UNITS = (
    ("m", "公尺", "meter", "length", 1.0, 0.0),
    ("km", "公里", "kilometer", "length", 1000.0, 0.0),
    ("cm", "公分", "centimeter", "length", 0.01, 0.0),
    ("mm", "公釐", "millimeter", "length", 0.001, 0.0),
    ("um", "微米", "micrometer", "length", 1e-6, 0.0),
    ("in", "英吋", "inch", "length", _IN, 0.0),
    ("ft", "英呎", "foot", "length", _FT, 0.0),
    ("yd", "碼", "yard", "length", 3 * _FT, 0.0),
    ("mi", "英里", "mile", "length", 5280 * _FT, 0.0),
    ("nmi", "海里", "nautical mile", "length", _NMI, 0.0),
    ("kg", "公斤", "kilogram", "mass", 1.0, 0.0),
    ("g", "公克", "gram", "mass", 0.001, 0.0),
    ("mg", "毫克", "milligram", "mass", 1e-6, 0.0),
    ("t", "公噸", "metric ton", "mass", 1000.0, 0.0),
    ("lb", "磅", "pound", "mass", _LB, 0.0),
    ("oz", "盎司", "ounce", "mass", _LB / 16, 0.0),
    ("catty", "台斤", "Taiwan catty", "mass", 0.6, 0.0),
    ("tael", "兩", "Taiwan tael", "mass", 0.0375, 0.0),
    ("degC", "攝氏", "Celsius", "temperature", 1.0, _ABS_ZERO_C),
    ("degF", "華氏", "Fahrenheit", "temperature", 5.0 / 9.0,
     459.67 * (5.0 / 9.0)),
    ("K", "克耳文", "Kelvin", "temperature", 1.0, 0.0),
    ("Pa", "帕", "pascal", "pressure", 1.0, 0.0),
    ("kPa", "千帕", "kilopascal", "pressure", 1000.0, 0.0),
    ("MPa", "百萬帕", "megapascal", "pressure", 1e6, 0.0),
    ("bar", "巴", "bar", "pressure", 1e5, 0.0),
    ("atm", "大氣壓", "standard atmosphere", "pressure", 101325.0, 0.0),
    ("psi", "磅力每平方吋", "pound-force per square inch", "pressure",
     _LB * 9.80665 / (_IN * _IN), 0.0),
    ("mmHg", "毫米汞柱", "millimeter of mercury", "pressure",
     133.322387415, 0.0),
    ("J", "焦耳", "joule", "energy", 1.0, 0.0),
    ("kJ", "千焦耳", "kilojoule", "energy", 1000.0, 0.0),
    ("cal", "卡", "calorie (thermochemical)", "energy", _CAL, 0.0),
    ("kcal", "大卡", "kilocalorie", "energy", 1000 * _CAL, 0.0),
    ("Wh", "瓦時", "watt-hour", "energy", 3600.0, 0.0),
    ("kWh", "度（千瓦時）", "kilowatt-hour", "energy", 3.6e6, 0.0),
    ("BTU", "英制熱單位", "British thermal unit", "energy", _BTU, 0.0),
    ("m2", "平方公尺", "square meter", "area", 1.0, 0.0),
    ("km2", "平方公里", "square kilometer", "area", 1e6, 0.0),
    ("cm2", "平方公分", "square centimeter", "area", 1e-4, 0.0),
    ("ha", "公頃", "hectare", "area", 1e4, 0.0),
    ("ping", "坪", "Taiwan ping", "area", 400.0 / 121.0, 0.0),
    ("ft2", "平方英呎", "square foot", "area", _FT * _FT, 0.0),
    ("in2", "平方英吋", "square inch", "area", _IN * _IN, 0.0),
    ("acre", "英畝", "acre", "area", _ACRE, 0.0),
    ("m3", "立方公尺", "cubic meter", "volume", 1.0, 0.0),
    ("L", "公升", "liter", "volume", 0.001, 0.0),
    ("mL", "毫升", "milliliter", "volume", 1e-6, 0.0),
    ("gal", "加侖（美制）", "US gallon", "volume", _GAL, 0.0),
    ("ft3", "立方英呎", "cubic foot", "volume", _FT ** 3, 0.0),
    ("in3", "立方英吋", "cubic inch", "volume", _IN ** 3, 0.0),
    ("m/s", "公尺每秒", "meter per second", "speed", 1.0, 0.0),
    ("km/h", "公里每小時", "kilometer per hour", "speed", 1000.0 / 3600.0,
     0.0),
    ("mph", "英里每小時", "mile per hour", "speed", _MPH, 0.0),
    ("knot", "節", "knot", "speed", _NMI / 3600.0, 0.0),
    ("ft/s", "英呎每秒", "foot per second", "speed", _FT, 0.0),
    ("s", "秒", "second", "time", 1.0, 0.0),
    ("min", "分", "minute", "time", 60.0, 0.0),
    ("h", "小時", "hour", "time", 3600.0, 0.0),
    ("day", "日", "day", "time", 86400.0, 0.0),
    ("week", "週", "week", "time", 604800.0, 0.0),
    ("yr", "年（365 天）", "year (365 days)", "time", 365 * 86400.0, 0.0),
)

# 顯示用符號（sym）；未列出者與 id 相同
_SYM = {"um": "µm", "m2": "m²", "km2": "km²", "cm2": "cm²", "ft2": "ft²",
        "in2": "in²", "m3": "m³", "ft3": "ft³", "in3": "in³",
        "degC": "°C", "degF": "°F"}

_BY_ID = {}
for _u in _UNITS:
    _BY_ID[_u[0]] = _u


def list_units():
    """列出所有類別與單位（供 UI 下拉選單）。"""
    cats = []
    for cid, zh, en in _CATEGORIES:
        units = [{"id": u[0], "zh": u[1], "en": u[2],
                  "sym": _SYM.get(u[0], u[0])}
                 for u in _UNITS if u[3] == cid]
        cats.append({"id": cid, "zh": zh, "en": en, "units": units})
    return ok({"categories": cats})


def _lookup(uid):
    """依 id 查單位；未知或非字串回 None。"""
    if not isinstance(uid, str):
        return None
    return _BY_ID.get(uid)


def convert(value, from_id, to_id):
    """把 value 由 from_id 換成 to_id；回 ok({"value": 結果})。"""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not is_finite(value)):
        return err("VALUE 必須是有限數字", "VALUE")
    src = _lookup(from_id)
    if src is None:
        return err("未知的單位：%s" % (from_id,), "FROM")
    dst = _lookup(to_id)
    if dst is None:
        return err("未知的單位：%s" % (to_id,), "TO")
    if src[3] != dst[3]:
        return err("無法在不同類別間換算（%s 與 %s）" % (src[1], dst[1]), "TO")
    base = src[4] * value + src[5]
    if src[3] == "temperature" and base < 0:
        return err("溫度低於絕對零度", "VALUE")
    result = (base - dst[5]) / dst[4]
    if not is_finite(result):
        return err("計算結果超出範圍（溢位）", "VALUE")
    return ok({"value": float(result)})
