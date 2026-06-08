# 디스커버리 익스페디션 26SS — 힉스필드 광고 소재 제작 워크플로우

> 한 상품의 누끼컷을 기반으로, 소구점별 AI 광고 소재(이미지/영상)를 힉스필드로 생성하는 표준 절차.

---

## 1. 인풋 수집

### 1.1 상품 기본 정보 — DCSAI
- `get_product_codes_properties` (BRD_CD=X, PART_CD=...)
- 카테고리 / 소재 / 컬러 / 사이즈 / CAD URL 확인
- 주의: `CAD_PDF_URL`은 PLM Tech Pack(제작 사양서) → 마케팅 카피 미포함

### 1.2 마케팅 카피 — DX 26SS 스타일가이드
- 파일: `C:\Users\AD0899\higgsfield ads\DX 26SS WEAR STYLE GUIDE.xlsx`
- B열에서 PART_CD 검색 → E열에서 4구획 카피 추출
  - **POINT** / **DETAIL** / **FABRIC** / **FIT**

### 1.3 리뷰 데이터 — Crema
- **우선**: admin.cre.ma 콘솔에서 PART_CD 검색 → 리뷰 CSV 다운로드 (가장 안전·완전)
- **차선**: 상품 페이지 JSON-LD에서 노출 10건 + AI 요약 API
  - 페이지: `https://www.discovery-expedition.com/product-detail/{PART_CD}-{COLOR}?gf=A`
  - AI 요약: `GET https://api.discovery-expedition.com/DXM/v1/goods/{PART_CD}-{COLOR}/reviews/ai-summary`
  - 헤더: `Authorization: Bearer <guest token>`, `MallId: DXM`, `DeviceCode: PC`, `LanguageCode: KOR`
  - 게스트 토큰: 페이지 1회 GET 시 `Set-Cookie: accessToken=...` 자동 발급

### 1.4 트렌드 (선택)
- `WebSearch` 로 **"26SS [카테고리] 트렌드"** (한국어 쿼리 우선) 1~2회 빠른 조회 → 1줄 인사이트만 반영
  - 영문 쿼리(`K-fashion 26SS ...`)는 글로벌 런웨이 일반론 위주 → K-시장 정합도 낮음
  - 한국어 쿼리는 삼성물산·유니클로 등 K-리테일 26SS 전략, 한국 검색 데이터 등 타깃 시장 자료 반환
- 정식 분석은 분기 1회 사내 데이터팀 자료 → 별도 메모리 적립

### 1.5 누끼 이미지 — OneDrive
- 폴더: `C:\Users\AD0899\OneDrive - F&F\TFTI_ E-Biz 컨텐츠 공유-윈윈스튜디오_DX - 26 SS 누끼촬영\`
- 검색: `find ... -iname "*PART_CD*"` (차수 폴더가 다양해서 전수 검색)
- 파일명 패턴 (BKS 컬러 기준):
  - `_01_MS.jpg` — 정면
  - `_08_MS.jpg` — 후면
  - **`_09_S.jpg` — 3/4뷰 (실루엣/핏 표현 최적, 디폴트)**
  - `_10~13_S.jpg` — 디테일 (와펜/소매/넥)

### 1.6 비주얼 레퍼런스 (성과 우수 컷)
- 폴더: `C:\Users\AD0899\higgsfield ads\레퍼런스\`
- 카테고리 매핑: `RS`=반팔티 / `SH`=셔츠 / `TS`=티셔츠 / `WJ`=윈드자켓 / `KIDS`=키즈
- 카테고리 폴더 진입 → 비주얼 톤 분석(모델 vs 제품 스틸 vs 라이프스타일) → 동일 톤 유지

### 1.7 브랜드 가이드 (작성 예정)
- 사용자 작성 후 메모리에 적립 → 톤·금기·필수 키워드·컬러팔레트 반영

---

## 2. 소구점 도출 (디폴트 룰 — 추후 조정 가능)

| 순번 | 기준 |
|---|---|
| **1번** | 리뷰 키워드 빈도 **1위** ∩ 스타일가이드 **FABRIC/FIT** 강조점 |
| **2번** | 디자인/색상 차별점 (스타일가이드 POINT + 리뷰 디자인 키워드) |
| **3번** | 가성비/실용성 (리뷰의 가성비/데일리 언급) |
| **4번~** | 부가 키워드 (체형핏, 활동성, 시즌 적합성 등) |

---

## 3. 힉스필드 프롬프트 작성 가이드

- **로고/상표 추상화**: `small embroidered chest patch` (정확한 워드마크 재현 X)
- **컬러**: 영문 색상명 사용 (BKS→`black`, IND→`indigo`, IVD→`ivory`)
- **핏**: `semi-over fit`, `relaxed yet tailored silhouette`
- **소재**: `cooling-touch fabric`, `breathable cotton blend`, `UV-protective lightweight fabric`
- **브랜드 톤**: `Discovery Expedition`, `Korean premium outdoor`, `outdoor lifestyle`, `urban-meets-nature`
- **모델 유무**: 레퍼런스 톤에 맞춰 명시 (`no people` 또는 모델 사양)
- **금기**: `no text in image, no extra logos` 항상 명시 (한글 텍스트 깨짐·로고 변형 방지)
- **카피 영역**: `generous negative space [위치]` 명시

---

## 4. 힉스필드 생성

### 디폴트 설정
- 모델: **`nano_banana_2`** (4K, 로고/디테일 보존력 우수)
- `aspect_ratio`: **`3:4`** (Instagram 피드 + 카피 영역 확보)
- `quality`: **`high`**
- `count`: 1 (1차 생성) → 검증 후 베리에이션

### 절차
1. `mcp__claude_ai_higgsfield__media_upload` (filename, content_type=`image/jpeg`)
2. `curl -X PUT` 로 받은 presigned URL에 누끼 파일 업로드
3. `mcp__claude_ai_higgsfield__media_confirm` (media_id, type=`image`)
4. `mcp__claude_ai_higgsfield__generate_image` (model, prompt, `medias=[{value, role:"image"}]`, params)
5. `mcp__claude_ai_higgsfield__job_status` (jobId, `sync=true`) — 결과 URL 수신

---

## 5. 산출물 저장 규칙

- 위치: `C:\Users\AD0899\higgsfield ads\`
- 파일명: `{PART_CD}-{COLOR}_sogu{N}_v{M}.png` 예: `DXRS75063-BKS_sogu1_v1.png`
- 원본 PNG + 썸네일 WebP 둘 다 보관

---

## 6. 세션 시작 시 사용자에게 확인할 항목

1. PART_CD (+ 컬러)
2. 소구점 번호 (1~N)
3. 포맷 (이미지 N컷 / 영상)
4. 모델 유무 (레퍼런스 톤 자동 검토 후 디폴트 제시)
5. 잔여 크레딧 확인 (1장당 nano_banana_2 비용 사전 체크)
