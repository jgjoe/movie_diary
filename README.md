# Movie Diary

**일기를 쓰면 감정을 분석해 지금 볼 만한 영화를 골라주는 서비스 — 상시 서버 비용 없이 운영합니다**

[![Live](https://img.shields.io/badge/live-GitHub%20Pages-success)](https://jgjoe.github.io/movie_diary/)
[![Backend](https://img.shields.io/badge/backend-Cloud%20Run%20(scale--to--zero)-4285F4?logo=googlecloud&logoColor=white)](#설계-판단)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows)

오늘 쓴 일기를 Gemini가 읽어 감정을 파악하고, 그 감정에 맞는 영화를 TMDB에서 찾아 추천합니다.
추천으로 끝내지 않고 일기와 추천 기록이 남아 지난 감정을 다시 볼 수 있습니다.

기획·프론트·백엔드·배포를 혼자 만들었고, **프론트는 GitHub Pages, 백엔드는 Cloud Run에 올려 상시 서버 비용 없이 운영**합니다.

---

## 주요 기능

| 기능 | 내용 |
|---|---|
| **감정 분석** | 일기에서 핵심 감정을 읽고 그에 맞는 메시지를 함께 제시 |
| **맞춤 영화 추천** | 감정에 맞는 작품을 TMDB에서 선별 |
| **OTT 필터** | 구독 중인 OTT(넷플릭스·왓챠 등)에 있는 작품만 보기 |
| **다시 추천** | 마음에 들지 않으면 새 추천 세트를 다시 요청 |
| **내 일기장** | 작성한 일기와 추천 기록을 로컬에 보관해 다시 열람 |
| **상세 정보** | 줄거리·평점·캐스팅과 지금 볼 수 있는 OTT 링크 |

## 설계 판단

### 외부 API를 두 곳 호출한다 → async를 기본 지원하는 프레임워크를 골랐다

감정 분석(Gemini)과 영화 조회(TMDB)가 **둘 다 네트워크 대기**입니다.
한 요청이 두 번의 외부 대기를 순차로 물기 때문에, 대기 구간에서 다른 요청을 처리할 수 있는 구조가 필요했습니다.
그래서 **async를 기본 지원하는 FastAPI**를 골랐고, Gemini 호출은 `generate_content_async`로 비동기 처리합니다.

**아직 절반만 했습니다.** TMDB 조회는 여전히 동기 `requests` 호출이라 그 구간에서는 이벤트 루프가 막힙니다.
`httpx`가 이미 의존성에 있으므로 비동기 클라이언트로 바꾸는 것이 다음 정리 대상입니다.

### 상시 서버를 두지 않았다

개인 서비스에 24시간 인스턴스를 띄우면 트래픽이 없어도 비용이 계속 나갑니다.
**요청이 있을 때만 실행되는 Cloud Run**에 백엔드를 올려 상시 비용을 없앴습니다.
대신 첫 요청은 인스턴스를 올리는 시간이 붙습니다 — 개인 프로젝트에서 비용과 지연 중 비용을 택한 결과입니다.

### API 키를 프론트에 두지 않았다

Gemini·TMDB 키는 **서버 환경변수로만 보관**하고 브라우저 번들에 넣지 않았습니다.
프론트는 백엔드를 통해서만 외부 API에 닿습니다.

### 모델 가용성이 변한다는 전제

LLM 모델 이름은 계속 바뀌고 특정 모델이 계정·리전에서 안 열릴 수 있습니다.
**사용 가능한 모델을 우선순위대로 자동 선택**하도록 해서 모델 하나가 막혀도 서비스가 멈추지 않게 했습니다.

### 외부 데이터가 비어 있을 수 있다는 전제

TMDB 응답에는 포스터·줄거리·OTT 정보가 빠진 항목이 섞여 있습니다.
누락 필드와 응답 형식 차이를 걸러 **추천 결과가 깨진 카드로 나오지 않도록** 처리했습니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| 프론트 | React 19, Vite, Tailwind CSS, Framer Motion, Lucide React |
| 백엔드 | Python, FastAPI (async) |
| AI | Google Gemini (사용 가능 모델 자동 선택) |
| 데이터 | TMDB API |
| 배포 | 백엔드 Google Cloud Run · 프론트 GitHub Pages |
| 자동화 | GitHub Actions (프론트 자동 배포) |

## 실행 방법

`.env`에 API 키가 필요합니다.

```bash
# 백엔드
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
```

```bash
# 프론트
cd frontend && npm install && npm run dev
```

필요한 키: `GEMINI_API_KEY`(Google AI Studio), `TMDB_API_KEY`(TMDB)

## 범위와 조건

- 사용자 수·응답 시간 등 **운영 지표는 측정하지 않았습니다.** 측정 근거가 있는 프로젝트는 [benefit-compass](https://github.com/jgjoe/benefit-compass)(60문항 평가셋)와 [Fridge-D-Day](https://github.com/jgjoe/Fridge-D-Day)(55장 회귀 기준선)입니다.
- 일기와 추천 기록은 브라우저 로컬에 저장되며 서버에 보관하지 않습니다. 기기를 바꾸면 이어지지 않습니다.
- 감정 분석 결과는 LLM 출력이므로 같은 글에도 표현이 달라질 수 있습니다.

## 만든 사람

**Jigwan Joe** — Backend · Frontend

- GitHub: [@jgjoe](https://github.com/jgjoe)
- Email: jigwan.joe@gmail.com
