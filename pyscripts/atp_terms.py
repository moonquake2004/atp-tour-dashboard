"""
Curated Chinese terminology for the ATP dashboard.

The ATP source is English-only.  Player names come from Wikidata (property P536,
the ATP player id) matched by name; everything else — countries, tournaments and
challenger host cities — is curated here, because a machine translation of a
place name is worse than no translation at all.

Challenger events are named "<city> challenger" by the feed, so the city table
plus a suffix produces their Chinese names.
"""

from __future__ import annotations

import re

# Country names as the feed prints them (full names, not IOC codes).
COUNTRY_ZH = {
    "Argentina": "阿根廷", "Australia": "澳大利亚", "Austria": "奥地利",
    "Belarus": "白俄罗斯", "Belgium": "比利时", "Bolivia": "玻利维亚",
    "Bosnia and Herzeg.": "波黑", "Brazil": "巴西", "Bulgaria": "保加利亚",
    "Canada": "加拿大", "Chile": "智利", "China": "中国",
    "Chinese Taipei": "中华台北", "Colombia": "哥伦比亚", "Croatia": "克罗地亚",
    "Czech Republic": "捷克", "Denmark": "丹麦", "Dominican Rep.": "多米尼加",
    "Ecuador": "厄瓜多尔", "Estonia": "爱沙尼亚", "Finland": "芬兰",
    "France": "法国", "Georgia": "格鲁吉亚", "Germany": "德国",
    "Great Britain": "英国", "Greece": "希腊", "Hong Kong": "中国香港",
    "Hungary": "匈牙利", "India": "印度", "Italy": "意大利",
    "Japan": "日本", "Jordan": "约旦", "Kazakhstan": "哈萨克斯坦",
    "Lithuania": "立陶宛", "Luxembourg": "卢森堡", "Mexico": "墨西哥",
    "Monaco": "摩纳哥", "Netherlands": "荷兰", "Norway": "挪威",
    "Paraguay": "巴拉圭", "Peru": "秘鲁", "Poland": "波兰",
    "Portugal": "葡萄牙", "RSA": "南非", "Romania": "罗马尼亚",
    "Russia": "俄罗斯", "Serbia": "塞尔维亚", "Slovakia": "斯洛伐克",
    "South Korea": "韩国", "Spain": "西班牙", "Sweden": "瑞典",
    "Switzerland": "瑞士", "Tunisia": "突尼斯", "Turkey": "土耳其",
    "USA": "美国", "Ukraine": "乌克兰", "Uruguay": "乌拉圭",
    "Uzbekistan": "乌兹别克斯坦",
}

# Tour-level and non-tour events, keyed by the name the feed uses.
TOURNAMENT_ZH = {
    "Australian Open": "澳大利亚网球公开赛",
    "French Open": "法国网球公开赛",
    "Wimbledon": "温布尔登网球锦标赛",
    "US Open": "美国网球公开赛",
    "Indian Wells": "印第安维尔斯大师赛",
    "Miami": "迈阿密大师赛",
    "Monte Carlo": "蒙特卡洛大师赛",
    "Madrid": "马德里大师赛",
    "Rome": "罗马大师赛",
    "Rome 2": "罗马大师赛",
    "Canada": "加拿大大师赛",
    "Toronto": "多伦多大师赛",
    "Montreal": "蒙特利尔大师赛",
    "Cincinnati": "辛辛那提大师赛",
    "Shanghai": "上海大师赛",
    "Paris": "巴黎大师赛",
    "Paris Masters": "巴黎大师赛",
    "Masters Cup ATP": "ATP 年终总决赛",
    "ATP Finals": "ATP 年终总决赛",
    "Tour Finals": "ATP 年终总决赛",
    "Next Gen Finals": "新生代总决赛",
    "United Cup": "联合杯",
    "Davis Cup": "戴维斯杯",
    "Davis Cup Finals": "戴维斯杯决赛圈",
    "Laver Cup": "拉沃尔杯",
    "Olympics": "奥运会",
    "Acapulco": "阿卡普尔科公开赛",
    "Adelaide": "阿德莱德公开赛",
    "Auckland": "奥克兰公开赛",
    "Barcelona": "巴塞罗那公开赛",
    "Basel": "巴塞尔公开赛",
    "Beijing": "中国网球公开赛",
    "Brisbane": "布里斯班国际赛",
    "Bucharest": "布加勒斯特公开赛",
    "Buenos Aires": "布宜诺斯艾利斯公开赛",
    "Dallas": "达拉斯公开赛",
    "Delray Beach": "德尔雷海滩公开赛",
    "Doha": "多哈公开赛",
    "Dubai": "迪拜公开赛",
    "Eastbourne": "伊斯特本公开赛",
    "Geneva": "日内瓦公开赛",
    "Halle": "哈雷公开赛",
    "Hamburg": "汉堡公开赛",
    "Hertogenbosch": "斯海尔托亨博斯公开赛",
    "Hong Kong ATP": "香港网球公开赛",
    "Houston": "休斯敦公开赛",
    "Kitzbuhel": "基茨比厄尔公开赛",
    "Mallorca": "马略卡公开赛",
    "Marrakech": "马拉喀什公开赛",
    "Marseille": "马赛公开赛",
    "Montpellier": "蒙彼利埃公开赛",
    "Munich": "慕尼黑公开赛",
    "Queen's Club": "女王俱乐部锦标赛",
    "Rio de Janeiro": "里约热内卢公开赛",
    "Rotterdam": "鹿特丹公开赛",
    "Santiago": "圣地亚哥公开赛",
    "Stockholm": "斯德哥尔摩公开赛",
    "Stuttgart": "斯图加特公开赛",
    "Tokyo": "日本网球公开赛",
    "Vienna": "维也纳公开赛",
    "Washington": "华盛顿公开赛",
    "Winston-Salem": "温斯顿-塞勒姆公开赛",
    "Umag": "乌马格公开赛",
    "Gstaad": "格施塔德公开赛",
    "Bastad": "巴斯塔德公开赛",
    "Newport": "纽波特公开赛",
    "Los Cabos": "洛斯卡沃斯公开赛",
    "Cordoba": "科尔多瓦公开赛",
    "Buenos Aires 3": "布宜诺斯艾利斯挑战赛",
    "Austrian Bundesliga": "奥地利网球联赛",
    "Swiss Nationalliga A": "瑞士网球国家联赛 A",
    "Ultimate Tennis Showdown": "终极网球对决",
    "Boodles Tennis Challenge": "布多斯网球挑战赛",
    "Hurlingham - exhibition": "赫林汉姆表演赛",
    "Incheon - exhibition": "仁川表演赛",
    "Kooyong - exh.": "库扬表演赛",
    "UTR Pro Tennis Series": "UTR 职业网球系列赛",
    "UTR Pro Tennis Series 3": "UTR 职业网球系列赛 3",
    "UTR Pro Tennis Series 5": "UTR 职业网球系列赛 5",
    "UTR Pro Tennis Series 9": "UTR 职业网球系列赛 9",
    "San Luis Potosi chall.": "圣路易斯波托西挑战赛",
    "Tallahassee chall.": "塔拉哈西挑战赛",
}

# Host cities used by challenger events; the feed writes "<city> challenger".
CITY_ZH = {
    "abidjan": "阿比让", "aix en provence": "普罗旺斯地区艾克斯", "alicante": "阿利坎特",
    "asuncion": "亚松森", "bangalore": "班加罗尔", "barletta": "巴列塔",
    "baton rouge": "巴吞鲁日", "birmingham": "伯明翰", "bordeaux": "波尔多",
    "brasília": "巴西利亚", "bratislava": "布拉迪斯拉发", "brazzaville": "布拉柴维尔",
    "bucaramanga": "布卡拉曼加", "buenos aires": "布宜诺斯艾利斯", "busan": "釜山",
    "cagliari": "卡利亚里", "campinas": "坎皮纳斯", "canberra": "堪培拉",
    "cap cana": "卡普卡纳", "cattolica": "卡托利卡", "centurion": "森图里昂",
    "cervia": "切尔维亚", "cesenatico": "切塞纳蒂科", "chennai": "金奈",
    "cherbourg": "瑟堡", "chisinau": "基希讷乌", "cleveland": "克利夫兰",
    "concepcion": "康塞普西翁", "dublin": "都柏林", "francavilla": "弗兰卡维拉",
    "fujairah": "富查伊拉", "glasgow": "格拉斯哥", "gwangju": "光州",
    "heilbronn": "海尔布隆", "hersonissos": "赫尔索尼索斯", "ilkley": "伊尔克利",
    "istanbul": "伊斯坦布尔", "itajai": "伊塔雅伊", "jiujiang": "九江",
    "kigali": "基加利", "koblenz": "科布伦茨", "kosice": "科希策",
    "lille": "里尔", "little rock": "小石城", "lugano": "卢加诺",
    "lyon": "里昂", "manama": "麦纳麦", "mauthausen": "毛特豪森",
    "menorca": "梅诺卡", "metepec": "梅特佩克", "mexico city": "墨西哥城",
    "miyazaki": "宫崎", "monza": "蒙扎", "morelia": "莫雷利亚",
    "morelos": "莫雷洛斯", "murcia": "穆尔西亚", "neapol": "那不勒斯",
    "new delhi": "新德里", "nonthaburi": "暖武里", "nottingham": "诺丁汉",
    "noumea": "努美阿", "oeiras": "奥埃拉什", "ostrava": "俄斯特拉发",
    "parma": "帕尔马", "pau": "波城", "perugia": "佩鲁贾",
    "phan thiet": "潘切", "phoenix": "凤凰城", "piracicaba": "皮拉西卡巴",
    "plovdiv": "普罗夫迪夫", "poznan": "波兹南", "prostejov": "普罗斯捷约夫",
    "pune": "浦那", "quimper": "坎佩尔", "rosario": "罗萨里奥",
    "royan": "鲁瓦扬", "saint brieuc": "圣布里厄", "san diego": "圣迭戈",
    "san miguel de tucuman": "圣米格尔-德图库曼", "santa cruz": "圣克鲁斯",
    "santos": "桑托斯", "sao leopoldo": "圣莱奥波尔多", "sao paulo": "圣保罗",
    "sarasota": "萨拉索塔", "savannah": "萨凡纳", "shymkent": "希姆肯特",
    "soma bay": "索马湾", "split": "斯普利特", "targu mures": "特尔古穆列什",
    "tenerife": "特内里费", "thionville": "蒂永维尔", "tigre": "蒂格雷",
    "tunis": "突尼斯", "tyler": "泰勒", "valencie": "瓦伦西亚",
    "vicenza": "维琴察", "wuning": "武宁", "wuxi": "无锡",
    "yokkaichi": "四日市", "zadar": "扎达尔", "zagreb": "萨格勒布",
    "tiburon": "蒂伯龙", "rennes": "雷恩", "szczecin": "什切青",
    "biella": "比耶拉", "guangzhou": "广州", "bangalore 2": "班加罗尔",
    "bangalore 3": "班加罗尔", "abidjan 2": "阿比让", "asuncion 2": "亚松森",
    "bratislava 2": "布拉迪斯拉发", "brisbane 3": "布里斯班", "canberra 2": "堪培拉",
    "centurion 2": "森图里昂", "hersonissos 2": "赫尔索尼索斯", "istanbul 4": "伊斯坦布尔",
    "kigali 2": "基加利", "nonthaburi 2": "暖武里", "nottingham 5": "诺丁汉",
    "oeiras 2": "奥埃拉什", "oeiras 5": "奥埃拉什", "oeiras 6": "奥埃拉什",
    "parma 3": "帕尔马", "phan thiet 2": "潘切", "shymkent 2": "希姆肯特",
    "tenerife 2": "特内里费", "tigre 2": "蒂格雷", "wuning 2": "武宁",
    "guangzhou 2": "广州", "sao paulo 2": "圣保罗",
    "brisbane": "布里斯班", "cordoba": "科尔多瓦", "madrid": "马德里",
    "rome": "罗马", "santiago": "圣地亚哥", "sao paulo": "圣保罗",
    "buenos aires 3": "布宜诺斯艾利斯",
}

# Round codes used by the feed.
ROUND_ZH = {
    "F": "决赛", "SF": "半决赛", "QF": "1/4 决赛", "R16": "16 强",
    "R32": "32 强", "R64": "64 强", "R128": "128 强",
    "1R": "第一轮", "2R": "第二轮", "3R": "第三轮", "4R": "第四轮",
    "RR": "小组赛", "BR": "铜牌战", "Q1": "资格赛首轮", "Q2": "资格赛次轮",
    "Q3": "资格赛决胜轮", "W": "冠军",
}

SURFACE_ZH = {
    "Hard": "硬地", "Clay": "红土", "Grass": "草地",
    "Indoors": "室内", "Carpet": "地毯", "Not set": "未标注",
}

LEVEL_ZH = {
    "Grand Slam": "大满贯", "Tour Finals": "年终总决赛", "ATP Tour": "巡回赛",
    "Challenger": "挑战赛", "Team Cup": "团体赛", "Olympics": "奥运会",
}

# 逐日赛果里球员名是缩写（"Sinner J." / "A. Abarca"），无法与 Wikidata 匹配，
# 因此中文名只覆盖排名榜与档案里的完整姓名；其余显示英文原名。
ABBREVIATED_NOTE = "缩写姓名不做翻译，直接显示英文原名。"


def country_zh(name: str) -> str:
    return COUNTRY_ZH.get((name or "").strip(), "")


def tournament_zh(name: str) -> str:
    """
    Chinese name for an event.

    Curated first; otherwise a "<city> challenger" label is rebuilt from the city
    table so every challenger gets a readable Chinese name.
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    if raw in TOURNAMENT_ZH:
        return TOURNAMENT_ZH[raw]
    # The calendar page abbreviates ("Szczecin chall."), the results page spells it
    # out; both are normalised to the same form before lookup.
    raw = re.sub(r"\bchall\.$", "challenger", raw, flags=re.I)

    lowered = raw.lower()
    if "challenger" in lowered or lowered.endswith("chall."):
        label = lowered.replace("challenger", "").replace("chall.", "").strip()
        # The city table contains both plain and numbered variants ("brisbane",
        # "brisbane 3"), so the whole label is tried before the number is split
        # off — and whatever number was in the label is preserved either way.
        number = ""
        parts = label.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].isdigit():
            number = parts[1]
        zh = CITY_ZH.get(label) or CITY_ZH.get(parts[0] if number else label)
        if zh:
            suffix = f" {number}" if number else ""
            return f"{zh}{suffix}挑战赛"
    return ""


def surface_zh(name: str) -> str:
    return SURFACE_ZH.get((name or "").strip(), "")


def round_zh(code: str) -> str:
    return ROUND_ZH.get((code or "").strip().upper(), "")


def level_zh(name: str) -> str:
    return LEVEL_ZH.get((name or "").strip(), "")


# ---------------------------------------------------------------------------
# Curated transliterations
#
# Wikidata has no Chinese label for a minority of ranked players — mostly
# lower-ranked ones and recent debutants.  The names below follow the
# transliteration conventions Chinese tennis media use for each source language.
# Anything not listed simply falls back to the English name.
# ---------------------------------------------------------------------------

PLAYER_ZH = {
    "Daniel Merida Aguilar": "丹尼尔·梅里达·阿吉拉尔",
    "Adolfo Daniel Vallejo": "阿道弗·丹尼尔·巴列霍",
    "Hamad Medjedovic": "哈马德·梅杰多维奇",
    "Martin Damm": "马丁·达姆",
    "Bu Yunchaokete": "布云朝克特",
    "Marcelo Tomas Barrios Vera": "马塞洛·托马斯·巴里奥斯·维拉",
    "Nicolai Budkov Kjaer": "尼古拉·布德科夫·凯尔",
    "Max Alcala Gurri": "马克斯·阿尔卡拉·古里",
    "Daniil Glinka": "丹尼尔·格林卡",
    "Matej Dodig": "马捷伊·多迪格",
    "Gonzalo Bueno": "贡萨洛·布埃诺",
    "Elmer Moller": "埃尔默·默勒",
    "Joel Schwaerzler": "约埃尔·施韦茨勒",
    "Andre Ilagan": "安德烈·伊拉甘",
    "Laslo Djere": "拉斯洛·杰雷",
    "Remy Bertola": "雷米·贝尔托拉",
    "Felix Balshaw": "费利克斯·巴尔肖",
    "Lautaro Midon": "劳塔罗·米东",
    "Andres Andrade": "安德烈斯·安德拉德",
    "Braden Shick": "布雷登·希克",
    "Alejandro Moro Canas": "亚历杭德罗·莫罗·卡尼亚斯",
    "Carlos Sanchez Jover": "卡洛斯·桑切斯·霍韦尔",
    "Nishesh Basavareddy": "尼谢什·巴萨瓦雷迪",
    "Learner Tien": "勒纳·田",
    "Joao Fonseca": "若昂·丰塞卡",
    "Jakub Mensik": "雅库布·门希克",
    "Rafael Jodar": "拉斐尔·霍达尔",
    "Martin Landaluce": "马丁·兰达卢塞",
    "Arthur Gea": "阿蒂尔·热亚",
    "Raphael Collignon": "拉斐尔·科利尼翁",
    "Luca Van Assche": "卢卡·范阿舍",
    "Thiago Agustin Tirante": "蒂亚戈·阿古斯丁·蒂兰特",
    "Juan Manuel Cerundolo": "胡安·曼努埃尔·塞伦多洛",
    "Roman Andres Burruchaga": "罗曼·安德烈斯·布鲁查加",
    "Fabian Marozsan": "法比安·马罗赞",
}


def player_zh(name: str) -> str:
    """Curated Chinese name for a player Wikidata does not cover."""
    raw = (name or "").strip()
    if not raw:
        return ""
    if raw in PLAYER_ZH:
        return PLAYER_ZH[raw]
    # Fall back to a token-set comparison so name order does not matter.
    key = _tokens(raw)
    for candidate, value in PLAYER_ZH.items():
        if _tokens(candidate) == key:
            return value
    return ""


def _tokens(value: str) -> frozenset:
    import re
    import unicodedata

    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return frozenset(t for t in re.split(r"[^a-z0-9]+", text.lower()) if t)
