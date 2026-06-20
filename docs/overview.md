# Cup POC — 코드 구조 및 작업 내역

## 개요

자연어 명령으로 머그컵 3D 모델 파라미터를 조작하는 POC 서버.
사용자가 "컵 높이 90으로 해줘" 같은 명령을 보내면, LLM이 의도를 파악해 파라미터 DAG를 업데이트하고,
[CascadeStudio](https://github.com/zalo/CascadeStudio) 용 JS 코드를 생성해 돌려준다.

CascadeStudio는 OpenCASCADE(OCCT)를 WebAssembly로 포팅한 브라우저 기반 CAD 환경이다.
생성된 JS 코드는 CascadeStudio의 API(`Sketch`, `Revolve`, `Cylinder`, `FilletEdges`, `Union`, `Difference` 등)를 사용한다.

```
사용자 명령
    │
    ▼
LLM (GPT-4o-mini)        ← app/llm/parser.py
    │ intent + changes
    ▼
파라미터 DAG 업데이트     ← app/graph/
    │ 재계산된 값
    ▼
JS 코드 렌더링            ← app/codegen/renderer.py + app/features/*/**.js.j2
    │
    ▼
GenerateResponse (code, state, diff, graph)
```

---

## 작업 내역 (구현된 기능 순서)

1. **파라미터 DAG + 솔버** — 노드 간 의존 관계를 DAG로 표현, 위상 정렬 기반 재계산
2. **Feature 템플릿 시스템** — body/handle 조합을 플러그인처럼 교체 가능하도록 추상화
3. **Jinja2 코드 렌더러** — DAG 값으로 JS 템플릿을 채워 최종 스크립트 생성
4. **LLM 파서** — 자연어 → `{intent, changes}` JSON 변환 (GPT-4o-mini)
5. **FastAPI 라우트** — `/api/generate` 엔드포인트, ModelState를 클라이언트와 주고받음
6. **op: "set" | "delta"** — 절댓값 설정과 상대 변화(+/-)를 구분
7. **비율 → 절댓값 리팩터** — 손잡이 부착 위치를 비율 파라미터에서 절댓값으로 전환
8. **필렛 포스트 프로세싱** — 엣지 선택 + 필렛 반경을 `post_processing` 목록에 누적, 코드 말미에 `FilletEdges` 삽입
9. **독립 바닥 두께** — `bottom_thickness` / `cylinder_bottom_thickness`를 벽 두께와 독립된 사용자 파라미터로 분리

---

## 디렉터리 구조

```
app/
├── main.py                  # FastAPI 앱 진입점
├── api/
│   └── routes.py            # /api/generate 엔드포인트
├── graph/
│   ├── model.py             # DAG / ParamNode 데이터 구조
│   ├── solver.py            # initialize / recompute (위상 정렬)
│   └── cup_graph.py         # body·handle 서브그래프 조립, 기본값 정의
├── features/
│   ├── base.py              # BodyFeature / HandleFeature 추상 인터페이스
│   ├── body/
│   │   ├── tapered_body.py          # 테이퍼드 몸통 feature
│   │   ├── tapered_body.js.j2       # 테이퍼드 몸통 JS 템플릿
│   │   ├── cylinder_body.py         # 원통형 몸통 feature
│   │   └── cylinder_body.js.j2      # 원통형 몸통 JS 템플릿
│   └── handle/
│       ├── bspline_handle.py        # BSpline 손잡이 feature
│       ├── bspline_handle.js.j2     # BSpline 손잡이 JS 템플릿
│       ├── ring_handle.py           # 링 손잡이 feature
│       └── ring_handle.js.j2        # 링 손잡이 JS 템플릿
├── codegen/
│   └── renderer.py          # Jinja2 렌더러, 섹션 조합
└── llm/
    └── parser.py            # OpenAI 호출, 자연어 → JSON 파싱
```

---

## 파일별 역할

### `app/main.py`
FastAPI 앱을 생성하고 CORS 미들웨어와 라우터를 등록한다. `.env`에서 환경변수를 로드하는 것도 여기서 한다. 서버 실행 시 진입점.

---

### `app/api/routes.py`
`/api/generate` POST 엔드포인트 하나를 담당한다.

요청 구조:
```
command   : 자연어 명령
state     : 현재 모델 상태 (body_template, handle_template, params, post_processing)
selection : 선택된 기하 요소 (type: "Edge", index: N)
```

처리 흐름:
1. `parse_command()` 호출 → `intent` 확인
2. `intent == "create"` : 새 DAG 생성, post_processing 초기화
3. `intent == "post_process"` : selection이 Edge면 `post_processing` 목록에 추가
4. `intent == "modify"` : 변경 파라미터에 set/delta 적용, `recompute()`, post_processing 유지
5. `render()` 호출 → JS 코드 생성
6. `GenerateResponse` 반환 (code, state, diff, graph)

`graph` 필드는 DAG 노드 전체를 `body / handle / joint` 서브그래프로 묶어 프론트엔드에 시각화 데이터를 제공한다.

---

### `app/graph/model.py`
DAG를 구성하는 두 클래스:

- **`ParamNode`** : 파라미터 하나를 표현. `is_user_facing=True`면 사용자가 직접 조작 가능. `formula`가 있으면 파생 노드.
- **`DAG`** : `{name → ParamNode}` 딕셔너리. `get / set / get_all / get_user_facing` 메서드 제공.

---

### `app/graph/solver.py`
DAG의 파생 노드 값을 계산한다.

- **`initialize(dag)`** : 처음 DAG를 만들었을 때 모든 파생 노드를 위상 정렬 순서로 한 번 계산.
- **`recompute(dag, changed_names)`** : 특정 노드가 변경됐을 때 그 영향을 받는 파생 노드만 순서대로 재계산. BFS로 영향 범위를 구하고 위상 정렬로 실행 순서를 결정한다.

---

### `app/graph/cup_graph.py`
"컵 모델 전체"의 DAG를 조립하는 조합 레이어.

- **`TAPERED_BODY_DEFAULTS` / `CYLINDER_BODY_DEFAULTS`** : 각 몸통 형태의 기본 파라미터 값.
- **`BSPLINE_HANDLE_DEFAULTS` / `RING_HANDLE_DEFAULTS`** : 손잡이 기본 값 (절댓값, 비율 없음).
- **`_build_tapered_body()` / `_build_cylinder_body()`** : body 서브그래프 노드를 DAG에 추가.
- **`_build_bspline_handle()` / `_build_ring_handle()`** : handle 서브그래프 노드를 DAG에 추가.
- **`build_dag(body_template, handle_template, params)`** : 위 빌더들을 호출하고, handle feature의 `build_joint_nodes()`를 통해 joint 서브그래프까지 완성한 DAG를 반환.

새 body나 handle 형태를 추가할 때 이 파일에 기본값과 빌더 함수만 추가하면 되고, 라우트나 렌더러는 수정할 필요가 없다.

---

### `app/features/base.py`
Body와 Handle feature의 추상 인터페이스:

- **`BodyFeature`** : `add_outer_r_node(dag, at_z, result)` — 특정 Z 높이에서 몸통 외면 반경을 계산하는 노드를 DAG에 추가한다. 테이퍼드는 선형 보간, 원통형은 상수.
- **`HandleFeature`** : `build_joint_nodes(dag, body)` — body 인터페이스를 주입받아 손잡이-몸통 연결에 필요한 joint 서브그래프를 DAG에 직접 조립한다.

이 인터페이스 덕분에 handle feature가 body의 구체적인 파라미터 이름을 몰라도 `add_outer_r_node`를 통해 기하 정보를 얻을 수 있다.

---

### `app/features/body/tapered_body.py`
테이퍼드(위아래 지름이 다른) 몸통 feature.

- 파라미터: `height, outer_top_r, outer_bottom_r, thickness, bottom_thickness`
- `add_outer_r_node()` : Z에 비례하는 선형 보간 공식으로 외면 반경 노드를 추가.
  `outer_bottom_r + (outer_top_r - outer_bottom_r) * (z / height)`

---

### `app/features/body/cylinder_body.py`
원통형 몸통 feature.

- 파라미터: `cylinder_height, cylinder_radius, cylinder_thickness, cylinder_bottom_thickness`
- `add_outer_r_node()` : Z와 무관하게 `cylinder_radius`를 상수로 반환하는 노드를 추가.

---

### `app/features/handle/bspline_handle.py`
BSpline 곡선 손잡이 feature. `build_joint_nodes()`에서 joint 서브그래프를 구성한다.

주요 joint 노드:
| 노드 | 설명 |
|------|------|
| `handle_span_z` | 손잡이가 걸치는 Z 범위 |
| `lower_outer_r` / `upper_outer_r` | 각 부착 Z에서 몸통 외면 반경 |
| `penetration_depth` | 손잡이가 몸통에 파고드는 깊이 (벽 두께 × 0.75) |
| `lower_attach_x` / `upper_attach_x` | 손잡이 부착 X 좌표 |
| `handle_mid_z` / `handle_mid_outer_r` | BSpline 중간 제어점 |

---

### `app/features/handle/ring_handle.py`
원형 링 손잡이 feature. `build_joint_nodes()`에서 joint 서브그래프를 구성한다.

주요 joint 노드:
| 노드 | 설명 |
|------|------|
| `ring_outer_r_at_attach` | 부착 Z에서 몸통 외면 반경 |
| `ring_attach_x` | 링 중심 X 좌표 (`ring_outer_r_at_attach + ring_outer_r - thickness × 0.75`) |

---

### `app/codegen/renderer.py`
Jinja2 환경을 열고 body + handle JS 템플릿을 DAG 값으로 렌더링해 하나의 CascadeStudio 스크립트 문자열로 조합한다.

출력 섹션 구조:
```
// === TAPERED BODY === (또는 CYLINDER BODY)
...body 코드...

// === BSPLINE HANDLE === (손잡이가 있을 경우)
...handle 코드...

// === UNION ===
let cup = Union([cupBody, cupHandle]);

// === POST PROCESSING ===            ← post_processing 목록에 항목이 있을 때만
cup = FilletEdges(cup, 2.0, [3], false);

// === RESULT ===
cup;
```

`post_processing` 목록에 있는 `{op: "fillet_edge", index, radius}` 항목이 POST PROCESSING 섹션에 순서대로 삽입된다.

---

### `app/llm/parser.py`
OpenAI API를 호출해 자연어 명령을 구조화된 JSON으로 변환한다.

반환 스키마:

```jsonc
// create
{"intent": "create", "body_template": "tapered"|"cylinder", "handle_template": "bspline"|"ring"|null, "changes": []}

// modify
{"intent": "modify", "changes": [{"param": "height", "op": "set"|"delta", "value": 90}]}

// post_process (selection이 있을 때)
{"intent": "post_process", "operation": "fillet_edge", "radius": 2.0}
```

`op` 규칙:
- `"set"` : 절댓값으로 지정 ("10mm로 바꿔줘")
- `"delta"` : 현재 값에서 더하기/빼기 ("5mm 더 크게", "3mm 줄여줘" → value=-3)

`selection` 컨텍스트(Edge index)가 있을 때만 `post_process` intent를 반환하도록 프롬프트에 명시되어 있다.

---

## 파라미터 목록 (사용자 조작 가능)

| 몸통 | 파라미터 | 기본값 | 단위 |
|------|----------|--------|------|
| 테이퍼드 | `height` | 70 | mm |
| | `outer_top_r` | 40 | mm |
| | `outer_bottom_r` | 29 | mm |
| | `thickness` | 3 | mm |
| | `bottom_thickness` | 3 | mm |
| 원통형 | `cylinder_height` | 90 | mm |
| | `cylinder_radius` | 40 | mm |
| | `cylinder_thickness` | 2.5 | mm |
| | `cylinder_bottom_thickness` | 2.5 | mm |

| 손잡이 | 파라미터 | 기본값 | 단위 |
|--------|----------|--------|------|
| BSpline | `section_width` | 14 | mm |
| | `section_height` | 8 | mm |
| | `lower_attach_z` | 12.6 | mm |
| | `upper_attach_z` | 56 | mm |
| | `handle_outward_depth` | 24 | mm |
| 링 | `ring_outer_r` | 19.5 | mm |
| | `ring_inner_r` | 10.5 | mm |
| | `ring_width` | 15 | mm |
| | `ring_attach_z` | 72 | mm |

---

## 테스트 파일

```
tests/
├── test_dag.py          # DAG / ParamNode 단위 테스트
├── test_solver.py       # initialize / recompute 로직 테스트
├── test_cup_graph.py    # build_dag() — 서브그래프 조립, 기본값, 재계산 통합 테스트
├── test_features.py     # 각 feature의 default_params와 템플릿 렌더링 스모크 테스트
├── test_renderer.py     # renderer.py 섹션 조합 및 post_processing 삽입 테스트
├── test_parser.py       # parse_command() mock 테스트 (intent / op / selection)
├── test_routes.py       # /api/generate 엔드포인트 통합 테스트 (81개)
└── test_health.py       # /health 응답 확인
```

실행:
```bash
source venv/bin/activate
python -m pytest tests/ -v
```
