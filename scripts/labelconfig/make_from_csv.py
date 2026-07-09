"""Build task JSONs from the Unity sim CSV+PNG datasets.

Each dataset = <base>.csv (ship rows) + <base>.png (scene). Produces:
  data.image = azure-blob://<container>/images/<base>.png
  data.data  = [ {구분, 위도, 경도, 길이(m), 너비(m), 속도(kn), 상대방위(°), CPA(nm), TCPA(s)} ]
  predictions = one scenario-aware, config-valid prediction (filled arbitrarily)

Table columns are data-driven (LS <Table> derives columns from the row-dict keys), so
the XML <Table> tag itself doesn't change — only these keys/order do.

상대방위 (relative bearing): geographic bearing from own ship to the target minus own
ship's heading, normalized 0–360. Own ship row shows "-".
"""

import csv
import glob
import json
import math
import os

from configspec import ConfigSpec

HERE = os.path.dirname(__file__)
SPEC = ConfigSpec.from_xml(open(os.path.join(HERE, "config.xml")).read())
CONTAINER = "label-images"


def geo_bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def parse_rows(csv_path):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    own = next((r for r in rows if r["my_ship"] == "1"), None)
    out = []
    for r in rows:
        is_own = r["my_ship"] == "1"
        label = "자선" if is_own else f"타선{r['ship_id']}"
        if is_own or own is None:
            rel_bearing = "-"
        else:
            b = geo_bearing(float(own["latitude"]), float(own["longitude"]), float(r["latitude"]), float(r["longitude"]))
            rel_bearing = f"{(b - float(own['heading'])) % 360:.1f}"
        out.append({
            "구분": label,
            "위도": f"{float(r['latitude']):.6f}",
            "경도": f"{float(r['longitude']):.6f}",
            "길이(m)": r["length"],
            "너비(m)": r["width"],
            "속도(kn)": f"{float(r['knot']):.1f}",
            "상대방위(°)": rel_bearing,
            "CPA(nm)": f"{float(r['cpa']):.4f}",
            "TCPA(s)": f"{float(r['tcpa']):.1f}",
        })
    return out, len(rows)


def scenario_of(base):
    if "crossing" in base:
        return "crossing"
    if "headon" in base:
        return "headon"
    if "overtaking" in base:
        return "overtaking"
    return "crossing"


# Deterministic-ish variety without RNG: cycle by index.
TIME = ["주간", "석간 / 황혼", "조간 / 새벽"]
SKY = ["맑음", "흐림", "연무", "역광", "이슬비"]
RULE = {"crossing": "횡단 상태 (Crossing)", "headon": "마주치는 상태 (Head-on)", "overtaking": "추월 상태 (Overtaking)"}


def build_prediction(base, ship_count, idx):
    scen = scenario_of(base)
    collision = "collision" in base
    count_choice = {2: "2", 3: "3"}.get(ship_count, "4+")
    # own-ship responsibility: head-on & overtaking → give-way; crossing alternates.
    responsibility = "유지선 / 피추월선" if (scen == "crossing" and idx % 2 == 0) else "피항선 / 추월선"
    if collision:
        course = "우현 60도"; speed = "감속"; signal = "교신 시도 필요함"
    elif scen == "overtaking":
        course = "우현 30도"; speed = "속력 유지"; signal = "교신 시도 필요함"
    elif responsibility.startswith("유지선"):
        course = "유지"; speed = "속력 유지"; signal = "5회 이상 단음 음향신호"
    else:
        course = "우현 10도"; speed = "속력 유지"; signal = "필요없음"

    scen_kr = {"crossing": "횡단", "headon": "마주치는", "overtaking": "추월"}[scen]
    answers = {
        "timeOfDay": TIME[idx % len(TIME)],
        "skyCondition": SKY[idx % len(SKY)],
        "identifiedVesselCount": count_choice,
        "descriptionSummary": (
            f"{TIME[idx % len(TIME)]}, {SKY[idx % len(SKY)]}. 식별 선박 {ship_count}척, {scen_kr} 상황"
            f"{'으로 충돌 위험 높음.' if collision else '으로 접근 중.'}"
        ),
        "ownShipResponsibility": responsibility,
        "navigationRule": RULE[scen],
        "courseAlterationAngle": course,
        "speedAction": speed,
        "vesselContactSignal": signal,
        "adviceSummary": (
            f"자선은 {'유지선' if responsibility.startswith('유지선') else '피항선'}. {RULE[scen]} 적용, "
            f"{course} 및 {speed}"
            f"{'으로 CPA 1.0 NM 이상 확보, VHF 교신 권고.' if collision else '으로 안전 CPA 유지.'}"
        ),
    }
    pred = SPEC.build_prediction(answers)
    problems = SPEC.validate_prediction(pred)
    if problems:
        raise SystemExit(f"[{base}] invalid prediction: {problems}")
    return pred


def build_all(csv_dir):
    tasks = []  # (base, task_json, png_path)
    for i, csv_path in enumerate(sorted(glob.glob(os.path.join(csv_dir, "*.csv")))):
        base = os.path.splitext(os.path.basename(csv_path))[0]
        png = os.path.join(csv_dir, base + ".png")
        if not os.path.exists(png):
            print(f"  ! PNG 없음, 스킵: {base}")
            continue
        rows, ship_count = parse_rows(csv_path)
        task = {
            "data": {"image": f"azure-blob://{CONTAINER}/images/{base}.png", "data": rows},
            "predictions": [build_prediction(base, ship_count, i)],
        }
        tasks.append((base, task, png))
    return tasks


if __name__ == "__main__":
    import sys

    csv_dir = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "csvout")
    tasks = build_all(csv_dir)
    os.makedirs(os.path.join(out, "tasks"), exist_ok=True)
    for base, task, _png in tasks:
        with open(os.path.join(out, "tasks", base + ".json"), "w") as f:
            json.dump(task, f, ensure_ascii=False, indent=2)
    print(f"{len(tasks)}개 태스크 생성 (검증 통과) → {out}/tasks/")
