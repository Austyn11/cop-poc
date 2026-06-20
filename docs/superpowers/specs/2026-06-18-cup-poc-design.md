# GraphRAG 솔리드 모델링 POC — 머그컵 설계 스펙

**날짜:** 2026-06-18  
**목표:** 파라미터 DAG 기반 서브그래프로 파트 간 접합 관계 유지와 파트 독립 조합을 증명하는 POC

---

## 1. 핵심 목표

1. **접합 무결성**: 파라미터를 수정해도 body-handle 접합 부분이 깨지지 않는다.
2. **파트 독립성**: 몸통과 손잡이 피처를 독립적으로 선택하고 조합할 수 있다.

---

## 2. 전체 아키텍처

```
사용자 자연어 명령
      ↓
 LLM Parser (Claude API)
 "컵 높이를 90으로 바꿔줘" → {param: "height", value: 90}
      ↓
 Parameter DAG (Python)
 ┌──────────────┬───────────────┬──────────────────────────────┐
 │ body         │ handle        │ joint (브릿지)               │
 │ sub-graph    │ sub-graph     │ sub-graph                    │
 │              │               │                              │
 │ height       │ lowerRatio    │ lowerAttachZ                 │
 │ outerTopR    │ upperRatio    │  = height * lowerRatio       │
 │ outerBottomR │ sectionWidth  │ lowerOuterR                  │
 │ thickness    │ sectionHeight │  = outerRadiusAtZ(lowerAttachZ)│
 └──────────────┴───────────────│ lowerAttachX                 │
                                │  = -lowerOuterR + penDepth   │
                                └──────────────────────────────┘
      ↓ 위상 정렬(topological sort) → 순서대로 재계산
      ↓
 Code Generator (Jinja2 → JS)
 feature template (.js.j2) + 계산된 파라미터값 → Cascade Studio JS 코드
      ↓
 FastAPI Response
 {code: "...", state: {...}, diff: {changed: [...], recomputed: [...]}}
```

---

## 3. 피처 템플릿 구조

각 피처는 **Python 클래스(파라미터 선언 + 인터페이스)** + **Jinja2 JS 템플릿(모델링 코드)** 한 쌍으로 구성된다.

### 파일 구조

```
cup-poc/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes.py
│   ├── graph/
│   │   ├── model.py          # ParamNode, DAG 클래스
│   │   ├── cup_graph.py      # 컵 전용 그래프 정의 (노드/엣지/수식)
│   │   └── solver.py         # 위상 정렬 + 재계산 엔진
│   ├── features/
│   │   ├── base.py           # FeatureTemplate 추상 클래스
│   │   ├── body/
│   │   │   ├── tapered_body.py       # 파라미터 선언, outerRadiusAtZ 인터페이스 노출
│   │   │   ├── tapered_body.js.j2    # 테이퍼드 컵 몸통 Cascade Studio 코드
│   │   │   ├── cylinder_body.py
│   │   │   └── cylinder_body.js.j2
│   │   └── handle/
│   │       ├── bspline_handle.py     # 파라미터 선언, attachment 인터페이스 노출
│   │       ├── bspline_handle.js.j2  # BSpline 경로 손잡이 Cascade Studio 코드
│   │       ├── ring_handle.py
│   │       └── ring_handle.js.j2
│   ├── codegen/
│   │   └── renderer.py       # 템플릿 렌더링 + 코드 조합
│   └── llm/
│       └── parser.py         # Claude API 호출, 자연어 → 구조화 명령
├── requirements.txt
└── README.md
```

### 인터페이스 개념

- **body 템플릿**: `outerRadiusAtZ(z)` 함수를 인터페이스로 노출 → joint 서브그래프가 이를 통해 attachment 반지름 계산
- **handle 템플릿**: `lowerAttachZRatio`, `upperAttachZRatio` 파라미터를 소유 → joint 서브그래프가 attachment Z 좌표 계산에 사용
- **joint 서브그래프**: body와 handle 인터페이스를 연결하는 브릿지. handle이 없으면 joint 서브그래프는 계산하지 않음

### JS 템플릿 예시 (`tapered_body.js.j2`)

```js
// Body parameters
const height = {{ height }};
const outerBottomR = {{ outer_bottom_r }};
const outerTopR = {{ outer_top_r }};
const thickness = {{ thickness }};
const innerBottomR = {{ inner_bottom_r }};
const innerTopR = {{ inner_top_r }};
const bottomThickness = {{ bottom_thickness }};

// Body geometry
let profile = new Sketch([0, 0, 0])
  .LineTo([-outerBottomR, 0])
  ...
```

---

## 4. 지원 피처 조합 (POC 범위)

| body 템플릿  | handle 템플릿  | 설명                       |
|-------------|--------------|--------------------------|
| tapered     | bspline      | 모델1: 테이퍼드 컵 + BSpline 손잡이 |
| cylinder    | ring         | 모델2: 원통형 컵 + 링 손잡이       |
| tapered     | null         | 손잡이 없는 테이퍼드 컵            |
| cylinder    | null         | 손잡이 없는 원통형 컵              |

---

## 5. API 엔드포인트

### `POST /api/generate` — 자연어 명령 처리

**Request:**
```json
{
  "command": "컵 높이를 70에서 90으로 바꿔줘",
  "state": {
    "body_template": "tapered",
    "handle_template": "bspline",
    "params": { "height": 70, "outer_top_r": 40, "outer_bottom_r": 29, "thickness": 3 }
  }
}
```
`state`가 없으면 기본값으로 초기화한다.

**Response:**
```json
{
  "code": "const height = 90; const outerTopR = 40; ...",
  "state": {
    "body_template": "tapered",
    "handle_template": "bspline",
    "params": { "height": 90, ... }
  },
  "diff": {
    "changed": ["height"],
    "recomputed": ["lower_attach_z", "upper_attach_z", "lower_outer_r", "upper_outer_r", "lower_attach_x", "upper_attach_x"]
  }
}
```

### `POST /api/model` — 초기 모델 생성 / 직접 파라미터 지정

**Request:**
```json
{
  "body_template": "tapered",
  "handle_template": "bspline",
  "params": { "height": 70 }
}
```

**Response:**
```json
{
  "code": "...",
  "state": { ... }
}
```

---

## 6. 파라미터 DAG 상세

### body 서브그래프 (tapered 기준)

| 노드              | 타입       | 수식                                          |
|-----------------|----------|---------------------------------------------|
| `height`        | 사용자 입력  | —                                           |
| `outer_top_r`   | 사용자 입력  | —                                           |
| `outer_bottom_r`| 사용자 입력  | —                                           |
| `thickness`     | 사용자 입력  | —                                           |
| `inner_top_r`   | 파생       | `outer_top_r - thickness`                   |
| `inner_bottom_r`| 파생       | `outer_bottom_r - thickness`                |
| `bottom_thickness`| 파생     | `thickness`                                 |

### handle 서브그래프 (bspline 기준)

| 노드                    | 타입       | 수식  |
|-----------------------|----------|-----|
| `section_width`       | 사용자 입력  | —   |
| `section_height`      | 사용자 입력  | —   |
| `lower_attach_z_ratio`| 사용자 입력  | —   |
| `upper_attach_z_ratio`| 사용자 입력  | —   |
| `outward_depth_ratio` | 사용자 입력  | —   |

### joint 서브그래프 (tapered + bspline)

| 노드                  | 의존                                        | 수식                                                       |
|---------------------|-------------------------------------------|------------------------------------------------------------|
| `lower_attach_z`    | `height`, `lower_attach_z_ratio`           | `height * lower_attach_z_ratio`                            |
| `upper_attach_z`    | `height`, `upper_attach_z_ratio`           | `height * upper_attach_z_ratio`                            |
| `handle_span_z`     | `upper_attach_z`, `lower_attach_z`         | `upper_attach_z - lower_attach_z`                          |
| `lower_outer_r`     | `outer_bottom_r`, `outer_top_r`, `height`, `lower_attach_z` | `outer_bottom_r + (outer_top_r - outer_bottom_r) * (lower_attach_z / height)` |
| `upper_outer_r`     | `outer_bottom_r`, `outer_top_r`, `height`, `upper_attach_z` | `outer_bottom_r + (outer_top_r - outer_bottom_r) * (upper_attach_z / height)` |
| `penetration_depth` | `thickness`                               | `thickness * 0.75`                                         |
| `lower_attach_x`    | `lower_outer_r`, `penetration_depth`       | `-lower_outer_r + penetration_depth`                       |
| `upper_attach_x`    | `upper_outer_r`, `penetration_depth`       | `-upper_outer_r + penetration_depth`                       |
| `handle_mid_z`      | `lower_attach_z`, `upper_attach_z`         | `(lower_attach_z + upper_attach_z) / 2`                    |
| `handle_mid_outer_r`| `outer_bottom_r`, `outer_top_r`, `height`, `handle_mid_z` | `outerRadiusAtZ(handle_mid_z)`                             |
| `handle_outward_depth`| `outer_top_r`, `outward_depth_ratio`    | `outer_top_r * outward_depth_ratio`                        |

---

## 7. 데이터 흐름 상세

1. `POST /api/generate` 수신
2. `state.params`가 없으면 기본값으로 DAG 초기화
3. LLM Parser가 `command`를 `{param, value}` 리스트로 파싱
4. DAG에서 변경 노드 값 업데이트
5. 위상 정렬로 파생 노드 순서대로 재계산
6. `handle_template`이 null이면 joint 서브그래프 계산 생략
7. body 템플릿 + (handle 템플릿) + (joint 연결 코드) → Jinja2 렌더링
8. 조합된 JS 코드 문자열 반환

---

## 8. POC 범위 외

- 실제 GraphDB(Neo4j 등) 연동
- 3개 이상 파트 조합
- 3D 렌더링 / 파일 다운로드 (STEP, STL)
- 프론트엔드 UI
