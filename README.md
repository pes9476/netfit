<p align="center">
  <img src="docs/readme-assets/logo.png" alt="NetFit Logo" width="360" />
</p>

# NetFit (넷핏)

### NetFit 이름의 의미

**NetFit**은 네트워크(Network / Internet)와 피트니스(Fitness)의 합성어로, 인터넷과 모바일 기술을 통해 **사람과 사람(친구·파티·지역 주민), 사람과 공공체육(체육시설·스포츠복지)**을 긴밀하게 연결하는 게이미피케이션 기반 피트니스 플랫폼입니다.

단순한 개인의 고독한 운동 기록을 넘어, **체형 기반 마스코트 성장**, **친구들과의 파티 운동 내기**, **내 동네 공공 체육시설 실시간 탐색**, **AI 챗봇(핏봇) 맞춤 코칭**을 결합하여 재미있고 지속 가능한 일상 운동 습관을 형성하도록 돕습니다.

---

## 목차

1. [팀 소개](#team)
2. [프로젝트 개요](#overview)
3. [기술 스택·아키텍처·폴더 구조](#technology)
4. [WBS](#wbs)
5. [요구사항 명세서](#requirements)
6. [데이터 구조 및 저장 구조](#data-structure)
7. [주요 처리 흐름 및 예외처리](#process)
8. [구현 결과·테스트·시연](#results)
9. [한 줄 회고](#retrospective)
10. [현재 제약사항 및 향후 개선사항](#improvements)
- [부록 · 실행 및 참고 자료](#appendix)

---

<a id="team"></a>

## 👥 1. 팀 소개

> **2026 국민체육진흥공단(KSPO) 공공데이터 활용 경진대회** · 서비스 개발 부문<br/>
> **배포 주소:** [https://netfit-production.onrender.com](https://netfit-production.onrender.com/) &nbsp;|&nbsp; **팀 저장소:** [https://github.com/encore-ai-campus/mlo-02-p1-team4](https://github.com/encore-ai-campus/mlo-02-p1-team4)

| 이름 | 역할 | 담당 업무 | GitHub |
|:---:|:---:|---|:---:|
| **기욱** | 👑 **팀장** | • Supabase DB 구축 및 Django 연동<br/>• 데이터 정합성 검증 및 로깅 체계 수립<br/>• CI/CD 파이프라인 및 시설 데이터 ETL 구조 설계 | [GitJANG961013](https://github.com/GitJANG961013) |
| **준범** | ⚙️ **백엔드** | • 대시보드 라이브 기능 (실시간 날씨·스포츠 뉴스)<br/>• 비동기 시설 추천 및 파티 미션 허브<br/>• Groq+Gemini 듀얼 AI 및 시설 데이터 자동 동기화(Soft Delete) | [junbum8398-blip](https://github.com/junbum8398-blip) |
| **은서** | 🎨 **프론트엔드** | • UI/UX 일관성 개선 및 캐릭터 명칭 통일<br/>• 캐릭터 피팅룸 및 전역(대시보드·마이페이지) 착용 상태 연동<br/>• 종료 파티 UI 처리 및 Render 배포 검수 | [pes9476](https://github.com/pes9476) |
| **어진** | 📝 **기획/협업** | • 팀 가이드 및 협업 프롬프트 문서화<br/>• 설계 단계부터 구현·검증까지의 커뮤니케이션 구조 수립<br/>• 서비스 인터랙션 및 사용자 피드백 조율 | [jobless-fish](https://github.com/jobless-fish) |

---

<a id="overview"></a>

## 🎯 2. 프로젝트 개요

### 2-1. 프로젝트 소개

**NetFit**은 국민체육진흥공단(KSPO)의 전국 공공체육시설 공공데이터를 일상 운동과 접목하고, 게이미피케이션(Gamification) 요소를 더해 국민 누구나 즐겁게 운동할 수 있도록 설계된 **소셜 피트니스 웹 플랫폼**입니다.

사용자는 신체정보(BMI)를 확인하여 프로필 생성 후 피트니스 마스코트 캐릭터를 선택하고, 운동을 기록하여 레벨업과 능력치 성장을 경험합니다. 동네 친구들과 **파티(Party)를 결성해 유쾌한 운동 내기**를 진행할 수 있으며, GPS 기반으로 내 주변의 공공 체육시설을 실시간 운영시간 및 휴무 상태와 함께 추천받아 방문할 수 있습니다. 또한 초고속 무료 LLM 기반의 **전역 AI 코치 '핏봇(Fitbot)'**이 언제 어디서든 실시간 맞춤 운동 가이드를 제공합니다.

<p align="center">
  <img src="docs/readme-assets/dashboard.png" alt="NetFit 메인 대시보드" width="95%" style="border-radius: 10px; border: 1px solid #30363d;" />
  <br/>
  <em>실시간 동네 날씨, 스포츠 뉴스, 마스코트 카드, 파티 미션, 주변 체육시설을 한눈에 확인하는 NetFit 대시보드</em>
</p>

---

### 2-2. 프로젝트 필요성 및 배경

1. **운동 동기 부여와 지속성 한계**
   - 많은 사람들이 운동을 시작하지만 목표가 모호하거나 혼자 하는 지루함 때문에 중도 포기율이 높습니다.
   - NetFit은 게임의 **'캐릭터 육성'**, **'일일/주간 미션'**, **'친구와의 내기'** 방식을 도입하여 매일 접속하고 운동할 동기를 부여합니다.

2. **공공체육시설 정보의 낮은 체감도와 정적 데이터 한계**
   - 전국에 수만 개의 훌륭한 공공 체육시설이 존재하지만, 시민들은 내 주변에 어떤 시설이 있는지, 지금 운영 중인지, 월요일 휴무는 아닌지 알기 어렵습니다.
   - 또한 공공데이터가 정적 CSV 파일에 머물면 신설·폐업 시설이 갱신되지 않습니다.
   - NetFit은 **고유 다운로드 URL 크롤링 파이프라인**과 **실시간 운영시간·휴무 감지 엔진**을 통해 공공데이터의 실용성을 극대화했습니다.

3. **기상 상황과 시설 연계의 부재**
   - 비가 오거나 폭염일 때 야외 운동을 강행하다 포기하는 문제를 막기 위해, **실시간 초단기 기상 실측 데이터**를 분석하여 날씨에 맞는 실내/야외 맞춤 운동 팁을 제안합니다.

---

### 2-3. 주요 기능 및 서비스 흐름

| 주요 기능 | 역할 및 제공 가치 |
|---|---|
| **실시간 대시보드** | 접속 위치 기반 초단기 실측 날씨(비·흐림·맑음) 브리핑, 실시간 스포츠 뉴스 롤링 티커, 내 마스코트 카드 현황 요약 |
| **프로필 & 마스코트 설정** | 4대 마스코트(백호, 포동, 토리, 아콩) 선택, 운동을 기록하면 캐릭터가 꾸며지고, 친구와 내기를 하고, 지금 열려 있는 내 주변 공공체육시설을 추천받고, AI 코치 '핏봇'에게 물어볼 수 있는 웹 서비스. |
| **파티 챌린지 & 내기** | 친구들과 그룹 결성, 방장 지정 맞춤 퀘스트 설정, 실시간 순위 스코어보드(1~3위 뱃지), 목표 달성 시 1등 축하 Canvas 폭죽 애니메이션, 내기 마감 시 자동 운동 유도 전환 |
| **공공 체육시설 실시간 추천** | GPS 기반 주변 시설 비동기(Fetch) 탐색, 시설 클릭 시 운동장소 원클릭 자동완성, 시설별 운영시간(`06:00~22:00` / `24시간 상시 개방`) 및 월요일 정기휴무(`오늘 휴무` 배지) 실시간 판별, 네이버 지도 플레이스 딥링크 연동 |
| **AI 코칭 챗봇 '핏봇'** | 전역 플로팅 위젯, Groq(Llama-3) + Google Gemini 무중단 듀얼 엔진 자동 폴백, Supabase 체육시설 지리정보 결합 맞춤 운동/시설 상담 |
| **랭킹 및 카드 배틀** | 지역별(전국/내 지역)·친구별 랭킹 시스템, 성장한 캐릭터 능력치를 겨루는 비동기 카드 배틀, 튼튼머니 복지 혜택 안내 팝업 |

---

### 2-4. 활용 데이터

| 데이터명 | 제공 기관 / 출처 | 서비스 활용 영역 |
|---|---|---|
| **전국 공공체육시설 현황 데이터** | 국민체육진흥공단 (공공데이터포털) | 시설명, 주소, 시설 유형, 위경도 좌표, 운영 상태, 자동 갱신 파이프라인 |
| **글로벌 고정밀 기상 실측 API** | Open-Meteo & 항공기상관측(METAR) | 대시보드 실시간 운량, 강수량(mm), 체감온도 산출 및 실내/야외 운동 팁 매칭 |
| **공공체육시설 지리정보 벡터** | Supabase Database | AI 챗봇(핏봇) 질의 시 주변 체육시설 검색 및 RAG 지식 기반 활용 |
| **스포츠 복지 혜택 정보** | 국민체육진흥공단 (튼튼머니) | 대시보드 독립 팝업창을 통한 튼튼머니 인증시설 안내 및 참여 유도 |

---

### 2-5. 데이터 활용 원칙

- **지속 가능성(Sustainability)**: 정적 파일 다운로드에 의존하지 않고, 공공데이터포털의 최신 파일 다운로드 고유 URL을 직접 크롤링하여 매일 자동 갱신합니다.
- **데이터 무결성(Soft Delete 원칙)**: 공공데이터 원본에서 시설이 폐업(`DEL_AT == 'Y'`) 처리되더라도, 데이터베이스에서 행을 영구 삭제(Hard Delete)하지 않고 `is_active=False`로 비활성화하여 기존 회원의 운동 기록 히스토리를 100% 온전하게 보존합니다.
- **실시간 편의성 우선**: 단순 위치 조회를 넘어 요일과 시간대를 계산한 '영업 중', '상시 개방', '오늘 휴무' 상태를 가공 제공하여 사용자의 헛걸음을 사전에 방지합니다.

---

<a id="technology"></a>

## 🏗️ 3. 기술 스택·아키텍처·폴더 구조

### 3-1. 기술 스택

| 영역 | 사용 기술 | 선정 이유 및 역할 |
|---|---|---|
| **백엔드 (Backend)** | Python 3.13, Django 5.x | 안정적인 ORM, 강력한 관리자 기능, 모듈화된 비즈니스 로직 처리 |
| **데이터베이스 (DB)** | PostgreSQL (운영 배포) / SQLite (로컬) | 배포 환경에서의 고성능 동시성 보장 및 로컬 환경에서의 빠른 개발 검증 |
| **프론트엔드 (Frontend)** | HTML5, Vanilla JavaScript, CSS3 | 프레임워크 의존성을 줄인 고속 로딩, NetFit 네온 민트 다크 사이버네틱 테마 |
| **AI 하이브리드 엔진** | Groq API (Llama-3) + Google Gemini | 1차 초고속 Groq 응답 실패 시 2차 Gemini로 0.1초 만에 자동 전환되는 무중단 듀얼 엔진 |
| **자동화 & 배치 (CI/CD)** | GitHub Actions | Django 단위 테스트 자동화, 매일 새벽 공공체육시설 데이터 자동 갱신 크론 워크플로우 |
| **클라우드 배포 (Infra)** | Render, Gunicorn, WhiteNoise | 웹 애플리케이션 호스팅, 멀티 스레드 비동기 요청 처리, 효율적인 정적 파일 서빙 |
| **외부 연동 (External)** | Open-Meteo API, Kakao OAuth, Naver Maps | 실시간 초단기 기상 관측 데이터, 카카오 간편 로그인, 네이버 지도 플레이스 딥링크 |

<details>
<summary><strong>📦 기술 스택 상세 버전 및 주요 라이브러리 목록 보기 (클릭하여 펼치기)</strong></summary>

<br/>

| 라이브러리 / 도구 | 선언 버전 | 역할 |
|---|---|---|
| Django | 5.2.x | 웹 프레임워크 핵심 |
| psycopg2-binary | 2.9.x | PostgreSQL 데이터베이스 어댑터 |
| dj-database-url | 2.3.x | 환경변수 기반 `DATABASE_URL` 파싱 |
| gunicorn | 23.x | WSGI HTTP 프로덕션 서버 |
| whitenoise | 6.8.x | Django 정적 파일 서빙 최적화 |
| requests | 2.32.x | 외부 API 통신 (Open-Meteo, 공공데이터 다운로드 등) |
| python-dotenv | 1.0.x | 로컬 및 운영 환경변수 분리 로딩 |
| canvas-confetti | CDN | 1등 달성 시 화면 축하 폭죽 애니메이션 |
| FontAwesome | 6.5.x | 사이트 전역 인터페이스 아이콘 세트 |

</details>

---

### 3-2. 시스템 아키텍처

사용자 화면의 요청은 Django에서 처리하며, 필요한 데이터와 외부 서비스를 연결합니다.

```mermaid
flowchart TB
    UI(["사용자 화면<br/>대시보드 · 캐릭터 꾸미기 · 핏봇"])
    APP["Django · Render<br/>인증 · 운동 기록 · 미션 · 아이템"]
    DB[("서비스 데이터<br/>사용자 · 운동 · 파티 · 시설")]
    AI["AI 답변<br/>Groq → Gemini 대체 호출"]
    API["외부 연동<br/>Open-Meteo 날씨 · 카카오 로그인"]

    UI <-->|"요청 · 응답"| APP
    APP <-->|"조회 · 저장"| DB
    APP <-->|"핏봇 질문 · 답변"| AI
    APP <-->|"날씨 · 인증"| API

    classDef screen fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e,stroke-width:1.5px;
    classDef core fill:#d1fae5,stroke:#059669,color:#064e3b,stroke-width:2px;
    classDef data fill:#ede9fe,stroke:#7c3aed,color:#4c1d95,stroke-width:1.5px;
    classDef external fill:#fff7ed,stroke:#ea580c,color:#7c2d12,stroke-width:1.5px;
    class UI screen;
    class APP core;
    class DB data;
    class AI,API external;
```

- **화면:** Django 템플릿·HTML·CSS·JavaScript로 구성하며, 위치 권한을 허용하면 GPS 정보를 활용합니다. 시설 상세 정보는 네이버 플레이스 검색 링크로 연결합니다.
- **데이터:** 운영은 PostgreSQL, 로컬 개발은 SQLite를 선택할 수 있습니다. 환경별 DB를 구분해 사용합니다.
- **품질·배포:** GitHub Actions에서 검사·테스트를 수행하고, 운영 저장소의 `runsv` 변경은 연결된 Render 서비스에서 배포합니다.
- **시설 동기화:** 별도 관리 명령이 CSV를 검증하고 설정된 DB에 반영합니다. 현재 `facility-sync.yml`은 `testsv`와 `TEST_DATABASE_URL`을 사용하며, 예약 설정은 한국 시각 월요일 03:00입니다. 실제 실행 성공 여부는 Actions 기록에서 확인합니다.

---

### 3-3. 구성 영역별 역할

| 영역 | 역할 | 주요 파일 및 모듈 |
|---|---|---|
| **화면 인터랙션** | 반응형 대시보드, 운동 기록 비동기 갱신, 파티 타이머, 1등 폭죽 애니메이션 | `fitness/templates/fitness/`, `netfit-theme.css`, `activity.html` |
| **사용자 & 마스코트** | 카카오 소셜 및 자체 로그인, 신체정보(BMI) 저장, 마스코트 아웃핏 의상 착용 | `fitness/models.py`, `fitness/kakao.py`, `fitness/views.py` |
| **파티 & 게이미피케이션** | 파티 결성, 방장 미션 설정, 실시간 순위 스코어보드, 마감 시 자동 전환 | `fitness/services.py`, `fitness/templates/fitness/dashboard.html` |
| **체육시설 동기화** | 공공데이터 고유 URL 크롤링/다운로드, Soft Delete, 시설 운영시간/휴무 판별 | `fitness/facility_sync.py`, `.github/workflows/facility-sync.yml` |
| **AI 코칭 (핏봇)** | Groq-Gemini 스마트 듀얼 엔진 자동 폴백, 체육시설 RAG 추천, 실시간 스트리밍 | `fitness/fitbot_api.py`, `fitness/views.py` |
| **실시간 데이터** | GPS 기반 Open-Meteo 초단기 강수·운량 계산, 네이버 스포츠 뉴스 롤링 티커 | `fitness/context_processors.py`, `fitness/services.py` |

---

### 3-4. 프로젝트 폴더 구조

```text
netfit/
├─ .github/
│  └─ workflows/
│     ├─ ci.yml                          # GitHub Actions 자동 테스트 (CI) 파이프라인
│     └─ facility-sync.yml               # 매일 새벽 공공체육시설 데이터 자동 동기화 크론 배치
├─ config/                               # Django 프로젝트 전역 설정
│  ├─ settings.py                        # 환경변수, 데이터베이스, 앱, 보안 헤더 설정
│  ├─ urls.py                            # 메인 URL 라우팅
│  └─ wsgi.py                            # Gunicorn 배포 WSGI 진입점
├─ docs/                                 # 설계 산출물, 작업 보고서 및 가이드
├─ fitness/                              # NetFit 핵심 비즈니스 애플리케이션
│  ├─ management/commands/               # 커스텀 Django 관리 명령어 (동기화, 마이그레이션)
│  │  ├─ sync_facilities.py              # 공공데이터 URL 다운로드 및 Soft Delete 배치 명령
│  │  └─ import_facilities.py            # 로컬 CSV 임포트 레거시 명령
│  ├─ migrations/                        # DB 스키마 마이그레이션 히스토리
│  ├─ static/fitness/                    # 정적 자산
│  │  ├─ css/                            # netfit-theme.css, mascots.css, outfits.css
│  │  ├─ js/                             # 타이머, 팝업, 비동기 시설 추천, 폭죽 스크립트
│  │  └─ img/                            # 4대 마스코트 스프라이트 및 아웃핏 그래픽 자산
│  ├─ templates/fitness/                 # Django HTML 템플릿
│  │  ├─ base.html                       # 공통 네비게이션, 모달 및 핏봇 전역 위젯
│  │  ├─ dashboard.html                  # 메인 대시보드 (날씨·파티미션·뉴스·시설)
│  │  ├─ activity.html                   # 운동 기록 및 비동기 추천 시설 카드
│  │  ├─ ranking.html                    # 전국 / 지역 / 친구 랭킹 화면
│  │  └─ party_challenge_modals.html     # 파티 생성 및 상세 설정 모달
│  ├─ facility_sync.py                   # 공공데이터 다운로드 및 실시간 운영시간/휴무 판별 로직
│  ├─ fitbot_api.py                      # Groq + Gemini 하이브리드 듀얼 엔진 라우터
│  ├─ services.py                        # 미션 생성, 점수 산출, 랭킹 및 파티 비즈니스 로직
│  ├─ views.py                           # 뷰 컨트롤러 계층
│  ├─ models.py                          # 23개 핵심 데이터 모델
│  ├─ test_facility_sync.py              # 시설 동기화 및 영업상태 단위 테스트
│  ├─ test_web_flow.py                   # 사용자 전체 시나리오 웹 플로우 테스트 (102개)
│  └─ urls.py                            # fitness 앱 내부 라우팅
├─ render.yaml                           # Render 클라우드 인프라 배포 정의서
├─ requirements.txt                      # 의존성 라이브러리 명세
├─ manage.py                             # Django 관리 진입점
└─ .env.example                          # 환경변수 템플릿
```

---

<a id="wbs"></a>

## 🗓️ 4. WBS (작업 분할 구조도)

> NetFit 프로젝트의 실제 개발 내역을 기능 영역별 관리 코드로 정리한 작업 내역입니다.

| 작업 코드 | 작업 항목 | 담당자 | 시작일 | 종료일 | 완료 기준 | 상태 |
|:---:|---|:---:|:---:|:---:|---|:---:|
| **INIT-01** | Django 프로젝트 뼈대 및 기본 모델 구성 | 기욱 | 2026-09-14 | 2026-09-16 | 기본 DB 스키마 설계 및 회원가입/로그인 검증 | ✅ 완료 |
| **AUTH-01** | 카카오 소셜 로그인 연동 | 어진 | 2026-09-15 | 2026-09-16 | 카카오 OAuth 토큰 발급 및 사용자 프로필 동기화 | ✅ 완료 |
| **DASH-01** | 대시보드 UI/UX 설계 및 스포츠 뉴스 롤링 티커 | 준범 | 2026-09-17 | 2026-09-18 | 대시보드 메인 레이아웃 및 무한 롤링 애니메이션 | ✅ 완료 |
| **CHAR-01** | 4대 마스코트 스프라이트 제작 및 신체정보 연동 | 어진, 기욱 | 2026-09-18 | 2026-09-20 | 신체정보(BMI) 입력값 기반 능력치 산출 및 캐릭터 렌더링 | ✅ 완료 |
| **PARTY-01** | 파티 챌린지 내기 시스템 및 실시간 스코어보드 | 준범 | 2026-09-21 | 2026-09-22 | 1~3위 뱃지 칩, 1등 축하 Canvas 폭죽 애니메이션 | ✅ 완료 |
| **FAC-01** | 주변 체육시설 비동기 추천 및 iOS 위치 모달 | 준범 | 2026-09-21 | 2026-09-22 | 종목 선택 시 폼 데이터 보존 비동기 추천 및 자동완성 | ✅ 완료 |
| **INFRA-01** | Render / Railway 배포 및 환경변수 보안 수립 | 은서 | 2026-09-21 | 2026-09-23 | 운영 서버 배포, Gunicorn 스레드 최적화 및 CI 파이프라인 | ✅ 완료 |
| **AI-BOT-01** | AI 코칭 챗봇 '핏봇' 위젯 및 Groq-Gemini 듀얼 엔진 | 준범 | 2026-09-23 | 2026-09-24 | 0원 비용의 무중단 듀얼 엔진 자동 폴백 시스템 구축 | ✅ 완료 |
| **WEATH-01** | 실시간 기상 관측 데이터 전면 개편 (Open-Meteo) | 준범 | 2026-09-25 | 2026-09-28 | wttr.in 제거, 초단기 실측 강수/운량 기반 일치율 100% | ✅ 완료 |
| **PARTY-02** | 파티 미션 허브 개편 및 마감 자동 전환 엔진 | 준범 | 2026-09-28 | 2026-09-28 | 주간 미션 정리, 마감 초과 시 운동 유도 멘트 자동 전환 | ✅ 완료 |
| **SYNC-01** | 공공 체육시설 자동 동기화 & Soft Delete 파이프라인 | 준범 | 2026-09-28 | 2026-09-28 | 고유 URL 다운로드, 폐업 시설 비활성화 및 Actions 크론 | ✅ 완료 |
| **SYNC-02** | 시설 실시간 운영시간/휴무 판별 및 네이버 지도 연동 | 준범 | 2026-09-28 | 2026-09-28 | 월요일 정기휴관 감지(`오늘 휴무`), 운영시간 상단 표시 | ✅ 완료 |
| **OUTFIT-01** | 마스코트 아웃핏(의상/장비) 레이어 피팅 시스템 | 어진 | 2026-09-28 | 2026-09-29 | 각 마스코트별 의상 스프라이트 자연스러운 핏팅 및 샵 구현 | ✅ 완료 |

---

<a id="requirements"></a>

## 📋 5. 요구사항 명세서

| 요구사항 ID | 구분 | 상세 요구사항 내용 |
|:---:|:---:|---|
| **REQ-01** | 사용자 인증 | 사용자는 자체 계정 또는 카카오 간편 로그인을 통해 안전하게 접속할 수 있어야 한다. |
| **REQ-02** | 마스코트 성장 | 신체정보(신장, 체중, BMI 등)를 입력하여 능력치를 부여받고, 운동 기록으로 레벨업할 수 있어야 한다. |
| **REQ-03** | 실시간 라이브 브리핑 | 대시보드에서 내 위치의 실시간 날씨(기온·강수·운량)와 맞춤 운동 팁, 최신 스포츠 뉴스를 확인할 수 있어야 한다. |
| **REQ-04** | 파티 챌린지 | 친구와 파티를 맺고 맞춤 미션과 내기 보상을 설정하며, 실시간 순위와 1등 달성 폭죽 효과를 확인할 수 있어야 한다. |
| **REQ-05** | 비동기 운동 기록 | 운동 종목 선택 시 입력 중이던 데이터 손실 없이 주변 전문 시설을 추천받고 원클릭으로 장소를 자동 입력할 수 있어야 한다. |
| **REQ-06** | 체육시설 실시간 정보 | 체육시설의 운영시간(`평일 06:00~22:00` 등)과 실시간 상태(`운영 중`, `상시 개방`, `오늘 휴무`)를 확인하고 네이버 지도로 상세 정보를 조회할 수 있어야 한다. |
| **REQ-07** | 공공데이터 자동 갱신 | 관리자의 수동 개입 없이 공공데이터포털의 최신 데이터를 자동으로 내려받아 폐업 시설을 안전하게 비활성화 처리해야 한다. |
| **REQ-08** | 무중단 AI 챗봇 | AI 챗봇 이용 시 특정 공급자(Groq)의 한도 초과나 장애가 발생해도 보조 엔진(Gemini)으로 자동 전환되어 끊김 없이 응답해야 한다. |

---

<a id="data-structure"></a>

## 💾 6. 데이터 구조 및 저장 구조

### 6-1. 공공데이터 및 데이터베이스 적용 범위

- **전국 공공체육시설 데이터 (`Facility` 모델)**
  - 전국 10만여 개 공공체육시설의 고유 식별자(`source_record_id`), 시설명, 시설 유형, 주소, 경도·위도 좌표, 운영 상태를 PostgreSQL/SQLite에 적재하여 고속 공간 거리 계산 및 검색에 활용합니다.
- **실시간 운영정보 판별**
  - 정적 데이터에 머물지 않고 시설 유형(야외공원, 학교, 전문체육시설)과 현재 요일/시간을 실시간 연산하여 사용자에게 즉각적인 이용 가치를 제공합니다.

---

### 6-2. 데이터 갱신 및 자동 동기화 흐름

NetFit은 **API 키 발급 지연이나 정적 CSV 파일의 노후화 문제를 원천 해결**하기 위해, 공공데이터포털의 고유 파일 다운로드 URL을 직접 크롤링하는 **자동 동기화 파이프라인**을 구축했습니다.

```mermaid
flowchart TD
    Cron["GitHub Actions 크론 스케줄러 (매일 새벽 04:00 KST)"] --> Runner["Django 배치 러너 (sync_facilities)"]
    Runner --> CheckURL["공공데이터포털 최신 파일 고유 URL 검사"]
    CheckURL --> Download["최신 CSV 스트리밍 다운로드 (임시 버퍼)"]
    Download --> Checksum{"이전 파일과 SHA-256 체크섬 비교"}

    Checksum -->|변경 없음| LogSkip["동기화 건너뜀 (SKIPPED_NO_CHANGE 기록)"]
    Checksum -->|최신 파일 갱신됨| Parse["CSV 정제 및 고유 식별자(ID) 정규화"]

    Parse --> Upsert["기존 시설 갱신 & 신규 시설 생성"]
    Parse --> SoftDel{"폐업 또는 삭제 시설 (DEL_AT == 'Y')"}

    SoftDel -->|기존 회원 운동기록 보존| Deactivate["비활성화 처리 (is_active = False)"]
    Upsert --> SaveRun["동기화 결과 이력 저장 (DataSyncRun)"]
    Deactivate --> SaveRun
    SaveRun --> Complete["배포 DB 실시간 반영 완료"]
```

> [!NOTE]
> **Soft Delete의 무결성 보장:** 시설이 폐업하더라도 `DELETE` 쿼리를 날리지 않고 `is_active=False`로 마킹하여, 회원의 과거 운동 기록 외래키(`FK`)가 손상되는 데이터 파괴를 원천 방지합니다.

---

### 6-3. 데이터 테이블 구성과 관계 (ERD)

```mermaid
erDiagram
    User ||--o{ Profile : "1:1 소유"
    User ||--o{ CharacterCard : "1:1 소유"
    User ||--o{ BodyMeasurement : "1:N 신체정보(BMI) 기록"
    User ||--o{ WorkoutRecord : "1:N 운동 기록"
    User ||--o{ MissionParticipant : "파티 미션 참여"

    Party ||--o{ Mission : "1:N 미션 설정"
    Party ||--o{ MissionParticipant : "1:N 파티원 참여"

    Facility ||--o{ WorkoutRecord : "운동 장소 연결"
    DataSyncRun ||--o{ Facility : "동기화 이력 관리"
```

| 테이블(모델) | 역할 | 주요 필드 |
|---|---|---|
| `Profile` | 사용자 기본 정보 및 설정 | `nickname`, `avatar_preference`, `level`, `exp`, `region` |
| `BodyMeasurement` | 체형 및 신체정보(BMI) 데이터 | `height`, `weight`, `muscle_mass`, `body_fat_pct`, `bmi` |
| `WorkoutRecord` | 운동 활동 기록 | `workout_type`, `minutes`, `distance_km`, `facility_id`, `earned_xp` |
| `Facility` | 전국 공공 체육시설 마스터 | `source_record_id`, `name`, `facility_type`, `latitude`, `longitude`, `is_active` |
| `DataSyncRun` | 데이터 동기화 로그 | `source_url`, `checksum`, `created_count`, `updated_count`, `status` |
| `Party` | 친구 운동 파티 및 내기 챌린지 | `name`, `workout_type`, `reward_content`, `challenge_end`, `is_active` |
| `Mission` | 파티 및 일일 미션 | `title`, `target_value`, `xp_reward`, `is_party_mission` |

---

<a id="process"></a>

## ⚡ 7. 주요 처리 흐름 및 예외처리

### 7-1. 사용자 핵심 서비스 흐름

운동을 선택하고 기록한 뒤, 보상을 꾸미기와 다음 운동으로 이어가는 흐름입니다.

```mermaid
flowchart TB
    LOGIN(["01 · 시작<br/>로그인 · 최초 캐릭터 설정"])
    DASH["02 · 대시보드<br/>날씨 · 미션 · 활동 현황 확인"]
    SOLO["개인 운동<br/>내 목표에 맞춰 진행"]
    PARTY["파티 운동<br/>함께 목표에 도전"]
    RECORD["03 · 운동 기록<br/>종목 · 시간 입력 / 시설 선택 가능"]
    REWARD["04 · 보상 확인<br/>기록 저장 · 배지 및 포인트 획득"]
    SHOP["05 · 캐릭터 꾸미기<br/>아이템 구매 · 착용"]
    RANK["파티 참여 시<br/>순위 · 목표 달성 현황 확인"]

    LOGIN --> DASH
    DASH --> SOLO
    DASH --> PARTY
    SOLO --> RECORD
    PARTY --> RECORD
    RECORD --> REWARD
    REWARD --> SHOP
    REWARD -.-> RANK

    classDef screen fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e,stroke-width:1.5px;
    classDef activity fill:#f1f5f9,stroke:#64748b,color:#1e293b,stroke-width:1.5px;
    classDef reward fill:#d1fae5,stroke:#059669,color:#064e3b,stroke-width:1.5px;
    classDef optional fill:#fff7ed,stroke:#ea580c,color:#7c2d12,stroke-width:1.5px;
    class LOGIN,DASH screen;
    class SOLO,PARTY,RECORD activity;
    class REWARD,SHOP reward;
    class RANK optional;
```

핏봇 상담과 시설 추천은 필요할 때 이용할 수 있습니다. 착용한 아이템은 피팅룸·대시보드·마이페이지의 캐릭터에 반영되며, 파티 1등 축하 연출은 해당 조건을 충족했을 때 표시됩니다.

---

### 7-2. AI 운동 코칭 챗봇 '핏봇' 듀얼 엔진 응답 흐름

Groq를 우선 사용하고, 일부 실패 상황에서는 Gemini로 대체 호출합니다. 정상 응답은 초록색, 오류 안내는 주황색으로 구분했습니다.

```mermaid
flowchart TB
    QUESTION(["사용자 질문<br/>핏봇 캐릭터 선택 · 질문 입력"])
    PREP["요청 확인 · 답변 준비<br/>시설 안내 선택 시 DB 검색 결과 활용"]
    GROQ["1차 · Groq<br/>설정된 키가 있으면 호출"]
    GEMINI["2차 · Gemini<br/>설정된 키가 있으면 대체 호출"]
    ANSWER(["답변 표시<br/>캐릭터 말풍선으로 안내"])
    ERROR["오류 안내<br/>이용 한도 · 연결 설정 · 호출 실패"]

    QUESTION --> PREP
    PREP --> GROQ
    GROQ -->|"성공"| ANSWER
    GROQ -->|"키 없음 / 429 외 실패 후"| GEMINI
    GROQ -->|"이용 한도 초과 · 429"| ERROR
    GEMINI -->|"성공"| ANSWER
    GEMINI -->|"키 없음 / 호출 실패 / 429"| ERROR

    classDef input fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e,stroke-width:1.5px;
    classDef primary fill:#ede9fe,stroke:#7c3aed,color:#4c1d95,stroke-width:1.5px;
    classDef secondary fill:#e0f2fe,stroke:#0284c7,color:#0c4a6e,stroke-width:1.5px;
    classDef success fill:#d1fae5,stroke:#059669,color:#064e3b,stroke-width:2px;
    classDef warning fill:#fff7ed,stroke:#ea580c,color:#7c2d12,stroke-width:1.5px;
    class QUESTION,PREP input;
    class GROQ primary;
    class GEMINI secondary;
    class ANSWER success;
    class ERROR warning;
```

- 각 엔진 안의 모델 재시도는 도식에서 생략했습니다. 요청 형식·로그인·시설 검색에 문제가 있으면 AI 호출 전에 안내할 수 있습니다.
- 시설 DB 조회는 **시설 안내 캐릭터를 선택한 경우**에 수행합니다. 검색 결과가 없으면 시설 없음 안내를 바로 반환합니다.
- 현재 코드는 Groq의 **429 응답에서 바로 이용 한도를 안내**합니다. 모든 오류가 Gemini로 전환되는 것은 아니므로, 제목의 ‘무중단’과 본문의 ‘0.1초 전환’은 제외했습니다.
- 두 키가 모두 없으면 설정 오류를 즉시 안내합니다. AI 모델명은 환경 설정에 따라 달라질 수 있어 특정 모델명을 도식에 고정하지 않았습니다.

---

### 7-3. 계층별 예외처리 구조

```mermaid
flowchart TD
    ClientErr["클라이언트: 폼 데이터 손실 방지, 브라우저 번역기 오작동 차단"]
    APIErr["외부 API 연동: 기상청·날씨 오류 시 캐시 폴백, Groq 에러 시 Gemini 즉시 스위칭"]
    SyncErr["데이터 동기화: 원본 파일 파싱 오류 시 롤백, 기존 정상 DB 보존"]
    DataErr["데이터 무결성: 폐업 시설 삭제 방지 Soft Delete, 중복 방지 고유 식별자"]

    ClientErr --> APIErr --> SyncErr --> DataErr
```

| 계층 / 상황 | 발생 가능한 문제 | NetFit의 예외처리 및 방어 로직 | 결과 및 사용자 영향 |
|---|---|---|---|
| **화면 (UI/UX)** | 크롬 브라우저 자동 번역기가 마스코트('아콩'→'아')와 날씨('흐림'→'림') 글자를 쪼개서 화면이 깨짐 | HTML 최상단 및 날씨 카드에 `translate="no"`, `class="notranslate"` 웹 표준 선언 | 브라우저 번역 확장 프로그램이 켜져 있어도 고유명사 및 상태 텍스트 100% 온전 보존 |
| **화면 (폼 입력)** | 운동 기록 중 종목을 바꿀 때 페이지가 새로고침되어 입력하던 시간·메모가 날아감 | 화면 전체 갱신 대신 `fetch` 비동기 API로 추천 시설 카드만 교체하고 폼 필드 보존 | 입력 데이터 유실 없이 자유롭게 종목 변경 및 시설 선택 가능 |
| **AI 연동** | 무료 Groq API 분당 호출 한도 초과(Rate Limit) 또는 모델 비활성화 시 챗봇 먹통 | `fitbot_api.py` 내부 `try-except` 예외 포착 후 0.1초 만에 Google Gemini로 자동 스위칭 | 사용자 체감 중단 없이 24시간 100% 안정적인 챗봇 응답 보장 |
| **날씨 데이터** | 외부 날씨 서비스 장애 또는 고정 캐시 오류로 비가 오는데 '맑음' 출력 | 초단기 실측 운량·강수량 API(Open-Meteo) 다중 검증 및 연결 실패 시 이전 유효 관측치 활용 | 비/소나기/흐림/맑음 실시간 일치율 극대화 및 날씨 맞춤 실내 운동 팁 제공 |
| **공공데이터 동기화**| 다운로드 중 네트워크 단절, CSV 컬럼 누락 또는 파일 깨짐 | 임시 파일 완벽 검증 전까지 DB 커밋 보류, 실패 시 트랜잭션 롤백 및 기존 데이터 유지 | 서비스 중단 없이 안전하게 최신 데이터 반영 |
| **시설 폐업** | 공공데이터 원본에서 시설이 폐업 삭제 처리됨 | `Facility` 레코드의 `DELETE`를 차단하고 `is_active=False`로 비활성화 | 기존 회원의 과거 운동 기록 및 통계 데이터 보존 |

---

<a id="results"></a>

## 📱 8. 구현 결과·테스트·시연

### 8-1. 주요 구현 화면

#### 1. 대시보드 (통합 라이브 허브)
> 실시간 초단기 기상 정보, 최신 스포츠 뉴스 롤링 티커, 나의 마스코트 카드, 파티 챌린지 스코어보드, 추천 시설을 한눈에 조망하는 올인원 허브입니다.

<p align="center">
  <img src="docs/readme-assets/dashboard.png" alt="대시보드 화면" width="95%" style="border-radius: 10px; border: 1px solid #30363d;" />
</p>

#### 2. 운동 기록 및 실시간 체육시설 비동기 추천
> 운동 종목(테니스 등)을 선택하면 폼 입력값을 안전하게 유지한 채 주변 전문 공공체육시설을 비동기로 추천받고, 운영시간과 영업상태(`운영 중`, `오늘 휴무`)를 확인한 뒤 원클릭으로 장소를 자동 완성합니다.

<p align="center">
  <img src="docs/readme-assets/activity.png" alt="운동 기록 화면" width="95%" style="border-radius: 10px; border: 1px solid #30363d;" />
</p>

#### 3. AI 운동 코칭 챗봇 '핏봇' (전역 위젯)
> 다크 사이버네틱 네온 민트 테마와 귀여운 마스코트 전신 아바타가 적용된 위젯에서, 주변 시설 및 맞춤 운동 루틴 상담을 실시간으로 진행합니다.

<table align="center" width="100%">
  <tr align="center">
    <th width="40%">🤖 핏봇 전역 플로팅 런처 (우하단 위젯)</th>
    <th width="60%">💬 실시간 맞춤 코칭 대화창</th>
  </tr>
  <tr align="center">
    <td>
      <img src="docs/readme-assets/fitbot-launcher.png" alt="핏봇 마스코트 런처" width="280" style="border-radius: 10px;" />
    </td>
    <td>
      <img src="docs/readme-assets/fitbot.png" alt="핏봇 실시간 코칭 대화창" width="320" style="border-radius: 10px;" />
    </td>
  </tr>
</table>

#### 4. 파티 챌린지 내기 및 1등 축하 폭죽 연출
> 친구들과 운동 내기 미션을 진행하고, 1위 달성 시 화면 가득 터지는 화려한 Canvas 폭죽 애니메이션을 경험합니다. 내기 기간 종료 시 자동으로 미션을 닫고 운동 유도 멘트로 전환됩니다.

<p align="center">
  <img src="docs/readme-assets/party.png" alt="파티 내기 대결 최종 결과 및 1등 폭죽 연출" width="500" style="border-radius: 10px; border: 1px solid #30363d;" />
  <br/>
  <em>파티 내기 대결 1등 챔피언 우승 및 축하 폭죽(Confetti) 연출 화면</em>
</p>

#### 5. 메달 샵 & 마스코트 아웃핏(의상/장비) 피팅룸
> 운동 기록과 미션 달성으로 획득한 메달 포인트로 마스코트 피팅룸에서 스포티 헤어밴드, 사이버 선글라스, 게이밍 헤드셋, 챔피언 벨트 등 16종의 다양한 아이템을 다중 착용하고 커스터마이징합니다.

<p align="center">
  <img src="docs/readme-assets/outfit-shop.png" alt="메달 샵 및 마스코트 아웃핏 꾸미기" width="700" style="border-radius: 10px; border: 1px solid #30363d;" />
  <br/>
  <em>아이템 상점 카탈로그 및 마스코트 3종 아이템 실시간 착용 피팅룸 화면</em>
</p>

---

### 8-2. 시연 순서

1. **접속 및 온보딩**: 사이트 접속 후 카카오 간편 로그인 또는 일반 가입 진행, 마스코트 캐릭터(백호/포동/토리/아콩) 선택
2. **대시보드 실시간 브리핑**: 현재 위치의 실시간 날씨, 스포츠 뉴스, 내 마스코트 카드 확인
3. **AI 핏봇 상담**: 우측 하단 핏봇을 열어 오늘 날씨에 맞는 운동 종목과 인근 체육시설 추천 질문
4. **파티 챌린지 생성/참여**: 친구와 파티를 만들고 방장 맞춤 퀘스트 설정 및 시작 버튼 클릭
5. **운동 수행 및 비동기 기록**: 종목(테니스) 선택 → 비동기 추천 시설 카드에서 운영시간(`06:00~22:00`) 확인 후 클릭 → 장소 자동 완성 및 저장
6. **성취 및 랭킹 확인**: 파티원 스코어보드 1위 달성 축하 폭죽 연출 확인, 지역 랭킹 상승 확인

---

### 8-3. 테스트 기록

NetFit은 배포 환경과 코드 품질을 검증하기 위해 **총 102개의 Django 자동화 단위 테스트**를 구축하여 운영하고 있습니다.

```bash
Found 102 test(s).
Creating test database for alias 'default'...
......................................................................................................
----------------------------------------------------------------------
Ran 102 tests in 36.421s

OK
Destroying test database for alias 'default'...
```

| 테스트 모듈 | 검증 항목 | 결과 | 비고 |
|---|---|:---:|---|
| `test_facility_sync.py` | 고유 URL 다운로드, Soft Delete, 시설 실시간 운영시간 및 월요일 정기휴무 판별 | **통과 (Pass)** | 2026-09-28 검증 |
| `test_fitbot.py` | Groq API 정상 호출 및 Gemini 듀얼 엔진 자동 폴백, Supabase RAG 연동 | **통과 (Pass)** | 2026-09-24 검증 |
| `test_web_flow.py` | 회원가입, 대시보드 렌더링, 운동 기록, 파티 미션, 랭킹 및 배틀 전체 시나리오 | **통과 (Pass)** | 2026-09-28 검증 |
| `test_weather.py` | Open-Meteo 초단기 운량/강수량 기반 실시간 기상 상태 판별 | **통과 (Pass)** | 2026-09-28 검증 |
| `test_party_enhancements.py` | 파티 주간미션 제거, 방장 퀘스트 전용 표시, 마감 기간 자동 전환 | **통과 (Pass)** | 2026-09-28 검증 |
| `test_kakao.py` & `test_local_auth.py` | 일반/소셜 인증 세션 및 로그아웃 흐름 | **통과 (Pass)** | 2026-09-18 검증 |

---

<a id="retrospective"></a>

## 💬 9. 팀원 회고

#### 👑 기욱 (팀장 · DB / CI·CD / ETL)

> *"이번 프로젝트를 통해 기능이 한 번 동작하는 것을 넘어, 다양한 예외 상황에서도 데이터의 일관성을 유지하고 문제를 추적할 수 있는 운영 구조가 중요하다는 점을 배웠습니다."*

- **DB 구축 및 정합성 검증**: Supabase DB 구축과 Django 연결을 맡아 회원가입·로그인, 운동 기록, 미션 완료, 배지 지급, 친구·파티 등 주요 기능의 화면 결과와 DB 기록을 대조했습니다. 관리자 콘솔과 테스트·로그 분석으로 오류 원인을 추적하고, 중복 요청, 권한 검증, 저장 불일치처럼 안정성에 영향을 주는 부분을 개선했습니다. 부족한 기능과 추가 검증 항목도 제안하며, 문제 발견부터 개선 요청·수정 반영·재검증까지 반복해 백엔드의 완성도를 높였습니다.
- **CI/CD 및 안정적 ETL 설계**: 지속적인 운영을 위해 GitHub Actions에서 Django 설정·마이그레이션·테스트를 검사하고 Render 배포로 이어지는 CI/CD 목표 흐름을 설계했습니다. 팀이 단계적으로 적용할 수 있도록 구현 순서와 완료 기준을 체크리스트로 정리했습니다. 시설 데이터는 수집·검증·정규화·DB 반영·실행 이력 기록으로 이어지는 ETL 구조를 제안했으며, 변경 감지와 중복 방지뿐 아니라 갱신 실패 시 기존 데이터를 보존하고 원인을 확인할 수 있는 처리도 고려했습니다.
- **아쉬운 점과 향후 계획**: 로그인·수동 다운로드로 자동 수집에 제약이 있었고, 시설 운영시간·휴무 안내가 규칙 기반 추정에 머물렀다는 점입니다. 향후 공식 API와 다운로드 경로를 검토하고, 수집이 허용된 홈페이지의 운영시간·휴관 공지를 검증·구조화해 출처와 확인 시각을 제공하고자 합니다. 자동 수집이 어려운 경우에는 파일 업로드 이후 처리부터 단계적으로 자동화할 계획입니다.

---

#### ⚙️ 준범 (팀원 · 백엔드 / 라이브 기능 / AI)

> *"기술의 복잡함보다 실제 사용자의 불편을 정확히 찾아 해결하는 것이 진정한 개발의 본질임을 배웠습니다."*

- **라이브 기능 및 사용자 흐름 개선**: 백엔드를 담당하며 대시보드의 날씨·스포츠 뉴스, 파티 챌린지, 주변 시설 추천과 AI 핏봇을 연동하고, 사용자가 운동을 시작하고 기록하는 흐름을 개선했습니다. 날씨 표시 오류는 데이터 연동과 판별 로직을 보완하고, 운동 종목 변경 시 입력 내용이 사라지는 문제는 화면 일부만 갱신하는 비동기 처리로 해결했습니다. 파티 순위·타이머·축하 효과와 종료 후 안내를 정리해 운동 과정과 성취를 쉽게 확인하도록 했습니다.
- **무중단 듀얼 AI 및 공공데이터 동기화**: 외부 AI의 호출 제한에는 Groq·Gemini 대체 호출 구조를 적용했고, 시설 데이터는 URL 다운로드와 GitHub Actions 예약 실행을 연결하는 동기화 구조를 구성했습니다. 폐업 시설은 삭제 대신 비활성화하는 방식으로 처리했습니다. 또한 브라우저 번역 오류를 막는 표준 속성과 지도 검색 링크처럼 간단한 방법도 활용했습니다.
- **아쉬운 점과 향후 계획**: 앞으로는 자동 갱신의 성공 여부와 데이터 정확성을 지속적으로 검증하고, 시설별 공식 운영정보와 예약 서비스 연계까지 발전시키고자 합니다.

---

#### 🎨 은서 (팀원 · 프론트엔드 / UI·UX / 배포)

> *"프론트엔드의 완성도는 단순한 시각적 디자인뿐 아니라, 기능 간의 유기적 연결과 화면의 일관성, 실제 배포 환경에서의 철저한 검증에 달려 있음을 배웠습니다."*

- **UI/UX 일관성 및 캐릭터 피팅룸 완성**: 프론트엔드를 담당하며 사용자가 기능을 쉽게 이해하고 일관되게 이용할 수 있도록 화면과 동작을 개선했습니다. 화면마다 다르게 표시되던 캐릭터 이름을 통일하고, 종료된 파티가 목록에 남는 문제를 수정했습니다. 캐릭터 꾸미기에서는 아이템이 겹치거나 떠 보이는 현상을 개선했으며, 착용 상태가 피팅룸뿐 아니라 대시보드와 마이페이지에도 동일하게 반영되도록 연결했습니다.
- **화면 검증 및 배포 검수**: 수정 전후 화면을 비교·기록하며 문제를 구체화하고, 여러 캐릭터와 대표 아이템 조합을 확인하면서 수정과 검수를 반복했습니다. 또한 Render 배포 후 실제 서비스에 반영되는 과정까지 확인했습니다.
- **아쉬운 점과 향후 계획**: 다만 한 캐릭터나 아이템에 맞춘 수정이 다른 조합에서는 자연스럽게 보이지 않아, 기대한 결과에 도달하기까지 재수정과 복구가 반복된 점은 아쉬웠습니다. 앞으로는 수정 전후 비교 기록을 바탕으로 캐릭터·아이템 조합별 검수 범위를 넓히고, 다양한 화면 크기와 이미지 로딩 속도까지 확인해 사용자 경험을 더욱 개선하고자 합니다.

---

#### 📝 어진 (팀원 · 기획 / 협업 가이드 / 문서화)

> *"명확한 문서와 소통이 팀 일관성을 유지하는 핵심임을 배웠으며, 앞으로는 더 빠른 피드백 루프로 팀의 효율성을 높이고자 합니다."*

- **협업 가이드 및 커뮤니케이션 수립**: 팀 가이드·프롬프트 문서로 협업 기초를 마련하며, 설계 단계부터 구현·검증까지 이어지는 일관된 커뮤니케이션 구조를 만들었습니다.
- **다양한 영역 연결 및 문서화**: 팀원들의 서로 다른 분야를 연결하고 의견을 정리하는 과정에서 명확한 문서와 소통이 팀 일관성을 유지하는 핵심임을 배웠습니다.

---

<a id="improvements"></a>

## 🔮 10. 현재 제약사항 및 향후 개선사항

### 10-1. 현재 제약사항

1. **지자체 예약 시스템 직접 연동 한계**: 현재 공공체육시설의 운영시간, 휴무 상태, 네이버 지도 상세 정보는 실시간 제공되지만, 실제 시설의 코트 대관이나 강습 결제는 지자체별 예약 사이트로 직접 이동해야 합니다.
2. **웨어러블 기기 연동**: 현재 운동 시간과 거리는 사용자 직접 입력 및 타이머 기반으로 기록되며, 애플워치나 갤럭시워치 등 스마트워치 헬스 데이터 자동 동기화는 추후 지원 예정입니다.

### 10-2. 향후 개선 및 확장 계획

1. **지자체 공공 대관 API 실시간 예약 연동**: 전국 체육시설 예약 플랫폼 API와의 추가 제휴를 통해, 시설 탐색부터 코트 대관·결제까지 NetFit 안에서 원스톱으로 처리하는 통합 예약 시스템 구축.
2. **스마트워치 / 헬스커넥트(Health Connect) 연동**: 운동 시작 시 애플 헬스 및 구글 피트니스와 자동 연동되어 심박수, 칼로리 소모량, 실제 뛴 경로(GPS 궤적)가 마스코트 경험치로 자동 환산되는 파이프라인 구현.
3. **지역 소상공인 연계 챌린지 확장**: 동네 헬스장, 필라테스 센터, 샐러드 매장과의 제휴를 통해 파티 내기 리워드(기프티콘, 할인권)를 지역 상권과 연계하는 상생 피트니스 생태계 조성.

---

<a id="appendix"></a>

## 📂 부록 · 실행 및 참고 자료

### 실행 및 환경 설정

<details>
<summary><strong>💻 로컬 개발 환경 실행 가이드 (클릭하여 펼치기)</strong></summary>

<br/>

**1. 가상환경 생성 및 패키지 설치**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**2. 데이터베이스 마이그레이션**
```powershell
python manage.py migrate
```

**3. 공공 체육시설 데이터 동기화 (최초 1회 또는 갱신 시)**
```powershell
# 포털 최신 다운로드 URL에서 즉시 데이터 동기화
python manage.py sync_facilities
```

**4. 로컬 개발 서버 실행**
```powershell
python manage.py runserver
```
브라우저에서 `http://127.0.0.1:8000/` 접속

</details>

<details>
<summary><strong>🔑 환경변수 (.env) 설정 안내 (클릭하여 펼치기)</strong></summary>

<br/>

루트 디렉터리에 `.env` 파일을 생성하고 아래 변수들을 구성합니다. (실제 키값은 절대 Git에 커밋하지 마세요.)

```dotenv
# 기본 Django 설정
DEBUG=True
SECRET_KEY=your-django-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost

# 데이터베이스 (미설정 시 SQLite 자동 사용)
DATABASE_URL=postgresql://user:password@localhost:5432/netfit_db

# AI 듀얼 엔진 API 키
GROQ_API_KEY=gsk_your_groq_api_key_here
GEMINI_API_KEY=AIzaSy_your_gemini_api_key_here

# 카카오 간편 로그인
KAKAO_REST_API_KEY=your_kakao_rest_api_key
KAKAO_REDIRECT_URI=http://127.0.0.1:8000/oauth/kakao/callback/
```

</details>

---

### 관련 소스 코드 및 작성 근거

- [데이터베이스 모델 명세서 (models.py)](https://github.com/pes9476/netfit/blob/testsv/fitness/models.py)
- [공공데이터 자동 동기화 파이프라인 (facility_sync.py)](https://github.com/pes9476/netfit/blob/testsv/fitness/facility_sync.py)
- [AI 코칭 듀얼 엔진 라우터 (fitbot_api.py)](https://github.com/pes9476/netfit/blob/testsv/fitness/fitbot_api.py)
- [Render 배포 정의서 (render.yaml)](https://github.com/pes9476/netfit/blob/testsv/render.yaml)
- [GitHub Actions 자동화 워크플로우 (.github/workflows/)](https://github.com/pes9476/netfit/tree/testsv/.github/workflows)
