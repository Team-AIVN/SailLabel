# Label config ↔ prediction/task JSON tooling

XML 라벨 설정이 바뀌면 예측(prediction)/태스크 JSON도 같이 맞춰야 한다. 이 도구는
XML을 **정본**으로 삼아, 컨트롤 스펙(from_name/to_name/type/choices)을 파싱하고
예측 JSON을 생성·검증한다. Choice에 alias가 있으면 결과값은 alias를 쓴다
(에디터 Choice.jsx: `_resultValue = alias ?? value`).

- `config.xml`       — 현재 라벨 설정 정본(2컬럼: 왼쪽 이미지+표 독립 스크롤 / 오른쪽 입력 폼)
- `configspec.py`    — XML → 컨트롤 스펙 파서 + 예측 result 빌더 + 검증기
- `make_from_csv.py` — Unity 시뮬 CSV+PNG 데이터셋 → 태스크 JSON 생성
  - `<base>.csv`(선박 행) + `<base>.png`(장면)를 base name으로 1:1 매칭
  - 표 컬럼: 구분/위도/경도/길이(m)/너비(m)/속도(kn)/상대방위(°)/CPA(nm)/TCPA(s)
  - 상대방위 = 자선→타선 지리방위 − 자선 heading (0–360 정규화, 자선은 "-")
  - 시나리오(crossing/headon/overtaking, collision)별 예측 자동 채움 후 검증

## 사용
```
poetry run python make_from_csv.py <csv_dir> [out_dir]   # 태스크 JSON 생성(검증 통과분만)
```
표 컬럼은 LS `<Table>`가 행 dict 키에서 자동 도출하므로, 컬럼을 바꾸려면 XML이 아니라
`make_from_csv.py`의 행 dict 키/순서만 바꾸면 된다.
