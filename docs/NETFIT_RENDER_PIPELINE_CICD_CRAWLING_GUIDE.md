# NETFIT Render 파이프라인·CI/CD·데이터 수집 운영 가이드

- 작성 기준일: 2026-09-22
- 저장소: <https://github.com/pes9476/netfit>
- 배포 플랫폼: Render
- 운영 URL: <https://netfit-production.onrender.com/>
- 데이터베이스: Supabase PostgreSQL
- 사용 프레임워크: Django
- Render 서비스: `netfit-production`
- 확정 배포 브랜치: `runsv`

> 이 문서는 현재 로컬 저장소, GitHub 원격 브랜치 목록, 과거 `netfit_tigger` 코드, 최신 `runsv` 코드와 Render 공식 문서를 기준으로 작성했다. Render 대시보드 자체의 서비스 설정은 저장소만으로 확인할 수 없으므로, 대시보드 확인이 필요한 항목은 별도로 표시한다.

### 운영 주소 확인 결과

2026-09-22 기준으로 실제 Render 운영 주소를 확인했다.

| 확인 주소 | HTTP 상태 | 결과 |
|---|---:|---|
| `https://netfit-production.onrender.com/` | 200 | 웹 애플리케이션 정상 응답 |
| `https://netfit-production.onrender.com/healthz/` | 200 | Django 및 DB health check 정상 응답 |

따라서 이 문서에서 사용하는 기준 운영 origin은 다음과 같다.

```text
https://netfit-production.onrender.com
```

---

## 1. 먼저 확인된 핵심 결론

현재 NETFIT에는 애플리케이션 기능과 Railway 배포 설정은 있지만, Render 기준의 완성된 파이프라인은 아직 없다.

| 점검 항목 | 현재 상태 | 판단 |
|---|---|---|
| Django 애플리케이션 | 존재 | 완료 |
| Supabase `DATABASE_URL` 연결 코드 | 존재 | 사용 가능 |
| Gunicorn 실행 설정 | `Procfile`에 존재 | Render에 재사용 가능 |
| 정적 파일 | WhiteNoise 사용 | Render에 재사용 가능 |
| 상태 확인 API | `/healthz/` 존재 | Render health check에 사용 가능 |
| Railway 설정 | `railway.json` 존재 | Render에서는 적용되지 않음 |
| Render Blueprint | `render.yaml` 없음 | 미구현 |
| GitHub Actions CI | `.github/workflows` 없음 | 미구현 |
| 테스트 통과 후 배포 | 설정 파일상 없음 | 미구현 |
| 예약 실행 | Cron/Celery 설정 없음 | 미구현 |
| 시설 CSV 적재 | `import_facilities` 존재 | 수동 ETL/Import |
| 웹 페이지 수집 예시 | `scrape_facility_hours` 존재 | 예제 수준 |
| 운영용 크롤링 파이프라인 | 없음 | 미구현 |

가장 먼저 해결할 문제는 **배포 서비스 이름과 Git 브랜치 이름을 구분하는 것**이다.

### 원격 브랜치 확인 결과

2026-09-22에 GitHub 원격을 직접 조회한 결과 다음 브랜치만 존재했다.

```text
backend
netfit
netfit_giuk
railway/fix-deploy-bd69e9
runsv
testsv
```

원격 GitHub에는 `netfit_tigger` 브랜치가 없었다. 로컬의 `origin/netfit_tigger`는 이전에 존재했던 원격 브랜치의 오래된 추적 정보일 가능성이 높다.

이후 Render의 배포 브랜치를 `runsv`로 변경했다. 따라서 현재 기준 배포 연결은 다음과 같다.

```text
GitHub 저장소: pes9476/netfit
배포 브랜치: runsv
Render 서비스: netfit-production
운영 주소: https://netfit-production.onrender.com/
```

Render 대시보드에서는 다음 위치에서 이 설정을 다시 확인할 수 있다.

```text
Render Dashboard
→ netfit-production 서비스
→ Settings
→ Build & Deploy
→ Repository
→ Branch
```

현재 `runsv`는 GitHub 원격에 실제로 존재한다. 2026-09-22 확인 시 최신 커밋은 다음과 같았다.

```text
56a445e fix: Remove duplicate close button and overlay badge from popup window
```

---

## 2. 파이프라인이란 무엇인가?

파이프라인은 입력이 들어온 뒤 여러 자동 처리 단계를 거쳐 결과가 만들어지는 흐름이다. NETFIT에서는 두 종류를 구분해야 한다.

### 2.1 소프트웨어 배포 파이프라인

```text
개발자 코드 작성
  → Git push / Pull Request
  → 자동 검사와 테스트(CI)
  → 승인 및 배포 브랜치 병합
  → Render build
  → DB migration
  → Gunicorn 실행
  → /healthz/ 확인
  → 새 버전으로 트래픽 전환(CD)
```

### 2.2 공공데이터 처리 파이프라인

```text
KSPO 원본 데이터 확보
  → 원본 파일 보관
  → 형식과 필수 컬럼 검증
  → 지역명·좌표 정규화
  → 중복 판별
  → Supabase DB 적재
  → 적재 건수와 오류 기록
  → 시설 추천 API/화면에서 조회
```

두 흐름 모두 파이프라인이지만 목적이 다르다.

- CI/CD 파이프라인: 코드를 안전하게 배포한다.
- 데이터 파이프라인: 외부 데이터를 신뢰할 수 있는 서비스 데이터로 만든다.

---

## 3. 현재 배포 파이프라인은 어디에 있는가?

### 3.1 현재 존재하는 파일

과거 `netfit_tigger`와 최신 `runsv`에는 다음 파일이 존재한다.

- `Procfile`
- `railway.json`
- `requirements.txt`
- `/healthz/` 엔드포인트

`Procfile`의 Gunicorn 명령은 Render Start Command로 재사용할 수 있다.

```text
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

하지만 `railway.json`은 Railway 전용 설정이다. Render는 이 파일을 읽어 다음 항목을 자동 적용하지 않는다.

- Railpack builder
- Railway pre-deploy migration
- Railway health check
- Railway restart policy

Render에서는 Dashboard 설정 또는 저장소 루트의 `render.yaml`로 다시 정의해야 한다. Render는 기본적으로 저장소 루트의 `render.yaml`을 Blueprint로 사용한다. [Render Blueprint 공식 문서](https://render.com/docs/blueprint-spec)

### 3.2 현재 `settings.py`의 Render 호환성 문제

과거 `netfit_tigger` 설정은 Railway 환경변수를 기준으로 작성돼 있다.

```python
ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT_ID"))
PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
```

Render에서는 공식적으로 다음 환경변수를 제공한다.

- `RENDER`: Render 환경 여부
- `RENDER_EXTERNAL_HOSTNAME`: Render 공개 호스트 이름

따라서 Render로 이전할 때 다음처럼 플랫폼 중립적으로 바꾸는 것이 좋다.

```python
ON_RENDER = bool(os.getenv("RENDER"))
ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT_ID"))
ON_PLATFORM = ON_RENDER or ON_RAILWAY

DEBUG = env_bool("DEBUG", not ON_PLATFORM)

PUBLIC_DOMAIN = (
    os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    or os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")
if PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(PUBLIC_DOMAIN)

CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f"https://{PUBLIC_DOMAIN}")
```

Render 공식 Django 가이드 역시 `RENDER`와 `RENDER_EXTERNAL_HOSTNAME`을 이용해 운영 환경과 허용 호스트를 구분하는 방식을 안내한다. [Render Django 배포 공식 문서](https://render.com/docs/deploy-django)

지금 코드에서도 Render 환경변수에 `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`를 직접 넣으면 동작할 수 있다. 하지만 코드 차원에서 Render를 인식하도록 수정하는 편이 설정 누락에 더 안전하다.

---

## 4. 목표 CI/CD 구조

NETFIT에 권장하는 최종 구조는 다음과 같다.

```text
기능 브랜치
  ├─ netfit_giuk
  └─ 팀원 작업 브랜치
          ↓ Pull Request
GitHub Actions CI
  ├─ dependency 설치
  ├─ Django system check
  ├─ migration 누락 검사
  ├─ 백엔드 자동 테스트
  └─ 정적 파일 수집 검사
          ↓ 성공 + 리뷰 승인
배포 브랜치(runsv)
          ↓
Render Auto-Deploy: After CI Checks Pass
          ↓
Build Command
          ↓
Pre-Deploy: migrate
          ↓
Start: Gunicorn
          ↓
/healthz/ 성공
          ↓
신규 버전 트래픽 전환
```

Render는 연결된 브랜치의 push를 자동 배포할 수 있으며, `After CI Checks Pass`를 선택하면 CI 성공 후에만 배포한다. CI가 없는데 이 옵션을 켜면 감지할 검사가 없어 배포가 시작되지 않는다. [Render 배포 공식 문서](https://render.com/docs/deploys)

---

## 5. GitHub Actions CI 구성

현재 저장소에는 `.github/workflows`가 없으므로 CI가 없다. 다음 파일을 배포 브랜치에 추가한다.

```text
.github/workflows/ci.yml
```

권장 예시:

```yaml
name: NetFit CI

on:
  push:
    branches:
      - runsv
      - testsv
      - netfit_giuk
  pull_request:
    branches:
      - runsv

permissions:
  contents: read

jobs:
  backend-test:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    env:
      USE_SQLITE: "1"
      DEBUG: "False"
      SECRET_KEY: "ci-only-not-production-secret"

    steps:
      - name: Checkout source
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip

      - name: Install dependencies
        run: python -m pip install -r requirements.txt

      - name: Django configuration check
        run: python manage.py check

      - name: Verify migration files
        run: python manage.py makemigrations --check --dry-run

      - name: Run backend tests
        run: >
          python manage.py test
          config.test_deployment
          fitness.test_kakao
          fitness.test_local_auth
          fitness.test_logout
          fitness.test_mascots
          fitness.test_web_flow
          -v 2

      - name: Verify static collection
        run: python manage.py collectstatic --noinput
```

### Selenium은 처음부터 같은 CI에 넣지 않는다

`fitness/tests_selenium.py`는 브라우저와 ChromeDriver가 필요하다. 이전 점검에서도 드라이버 다운로드 환경 때문에 실패했다. 백엔드 CI에 섞으면 애플리케이션이 정상인데도 배포가 계속 막힐 수 있다.

권장 분리 방식:

- 필수 CI: Django check, migration, 단위·통합 테스트
- 별도 UI CI: Playwright/Selenium, 브라우저 버전 고정
- 발표 전 수동 smoke test: 로그인, 미션, 친구, 파티, 랭킹

GitHub Actions 파일은 `.github/workflows` 아래에 있어야 하며 push, Pull Request, 예약 시간 등을 trigger로 사용할 수 있다. [GitHub Actions 공식 문서](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

---

## 6. Render 설정 방법

### 6.1 Render Dashboard에서 설정하는 방법

먼저 다음처럼 구성한다.

| Render 항목 | 권장 값 |
|---|---|
| Service Type | Web Service |
| Repository | `pes9476/netfit` |
| Branch | `runsv` |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60` |
| Health Check Path | `/healthz/` |
| Auto-Deploy | `After CI Checks Pass` |

Render는 새 인스턴스가 health check를 통과한 후 트래픽을 전달한다. `/healthz/`는 단순 HTML이 아니라 DB 연결 상태까지 검사하도록 이미 작성돼 있어 적합하다. [Render Health Checks 공식 문서](https://render.com/docs/health-checks)

### 6.2 환경변수

Render에 다음 값을 등록한다.

```env
DEBUG=False
SECRET_KEY=<Render에서 생성한 긴 임의 값>
DATABASE_URL=<Supabase PostgreSQL 연결 URL>
ALLOWED_HOSTS=netfit-production.onrender.com
CSRF_TRUSTED_ORIGINS=https://netfit-production.onrender.com
SECURE_SSL_REDIRECT=True

KAKAO_REST_API_KEY=<카카오 REST API 키>
KAKAO_CLIENT_SECRET=<카카오 Client Secret>
KAKAO_REDIRECT_URI=https://netfit-production.onrender.com/login/kakao/callback/
```

카카오 디벨로퍼스에도 Render 도메인과 같은 Redirect URI를 등록해야 한다.

```text
Web 사이트 도메인
https://netfit-production.onrender.com

Redirect URI
https://netfit-production.onrender.com/login/kakao/callback/
```

비밀번호와 API 키는 `render.yaml`, `.env.example`, GitHub 코드에 실제 값으로 작성하지 않는다.

### 6.3 migration 실행 위치

가장 좋은 위치는 Render의 Pre-Deploy Command다.

```text
python manage.py migrate --noinput
```

이 단계가 실패하면 새 버전을 시작하지 않고 기존 정상 버전을 유지할 수 있다. 다만 Render 공식 문서상 Pre-Deploy Command는 유료 Web Service, Private Service, Background Worker에서 제공된다. [Render 배포 단계 공식 문서](https://render.com/docs/deploys)

무료 Web Service를 사용한다면 선택지는 다음과 같다.

1. Render 공식 Django 예시처럼 build 단계에서 migration을 실행한다.
2. 배포 직전에 Render Shell에서 수동으로 migration한다.
3. Start Command 앞에 migration을 연결한다.

공모전 개발 단계의 현실적인 명령:

```text
python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

단, 이 방법은 서버 시작과 schema 변경이 묶이므로 장기 운영에는 Pre-Deploy Command가 더 낫다. 여러 인스턴스가 동시에 시작되는 환경에서는 migration 동시 실행 위험도 고려해야 한다.

---

## 7. `render.yaml` 권장 예시

Dashboard에서만 설정하면 팀원이 실제 배포 설정을 코드에서 확인하기 어렵다. 저장소 루트에 `render.yaml`을 두면 배포 구성을 버전 관리할 수 있다.

> Render의 실제 배포 브랜치가 `runsv`로 확정되어 아래 Blueprint에도 같은 값을 사용한다.

```yaml
services:
  - type: web
    name: net-fit-tiger
    runtime: python
    plan: free
    branch: runsv
    autoDeployTrigger: checksPass
    buildCommand: >-
      pip install -r requirements.txt &&
      python manage.py collectstatic --noinput
    startCommand: >-
      python manage.py migrate --noinput &&
      gunicorn config.wsgi:application
      --bind 0.0.0.0:$PORT
      --workers 2
      --threads 2
      --timeout 60
      --access-logfile -
      --error-logfile -
    healthCheckPath: /healthz/
    envVars:
      - key: DEBUG
        value: "False"
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        sync: false
      - key: ALLOWED_HOSTS
        sync: false
      - key: CSRF_TRUSTED_ORIGINS
        sync: false
      - key: KAKAO_REST_API_KEY
        sync: false
      - key: KAKAO_CLIENT_SECRET
        sync: false
      - key: KAKAO_REDIRECT_URI
        sync: false
```

유료 인스턴스에서는 migration을 Start Command에서 제거하고 다음 필드를 사용하는 것이 더 안전하다.

```yaml
preDeployCommand: python manage.py migrate --noinput
```

`autoDeployTrigger: checksPass`는 연결 브랜치의 CI 성공 후 배포를 시작한다. `sync: false`는 secret 값을 코드에 넣지 않고 Blueprint 최초 생성 시 입력하게 한다. [Render Blueprint 명세](https://render.com/docs/blueprint-spec)

---

## 8. CSV 적재는 크롤링인가?

### 결론

아니다. 현재 `import_facilities.py`가 하는 일은 **이미 확보한 CSV 파일을 읽어 DB에 적재하는 CSV Import 또는 ETL의 Load 단계**다.

```text
이미 존재하는 CSV
  → csv.DictReader
  → 일부 정제와 지역명 변환
  → update_or_create
  → Facility 테이블
```

웹사이트를 탐색하거나 서버에서 데이터를 수집하지 않으므로 크롤링이라고 부르는 것은 정확하지 않다.

### 용어 구분

| 용어 | 의미 | NETFIT 현재 상태 |
|---|---|---|
| Import | 가지고 있는 파일을 시스템에 넣음 | 구현됨 |
| ETL | 추출 → 변환 → 적재 | 변환·적재 일부 구현 |
| API 수집 | 공식 API를 호출해 데이터를 받음 | 시설 데이터에는 미구현 |
| 다운로드 자동화 | 공식 URL에서 CSV를 자동 다운로드 | 미구현 |
| Scraping | 특정 웹페이지 HTML에서 필요한 값 추출 | 예제만 존재 |
| Crawling | 여러 URL을 규칙에 따라 순회하며 수집 | 미구현 |

### 현재 `scrape_facility_hours.py`의 수준

이 명령은 URL 하나를 받아 HTML을 다운로드하고, 페이지 제목과 ‘운영’, ‘시간’이 들어간 단어를 출력한다.

```text
URL 1개
  → requests.get
  → BeautifulSoup
  → 텍스트 후보 출력
```

다음 요소가 없으므로 운영용 크롤러는 아니다.

- 여러 시설 URL 순회
- robots.txt 및 이용약관 확인
- 요청 간격과 rate limit
- 재시도와 지수 backoff
- 데이터 schema 검증
- DB 저장
- 기존 데이터 변경 감지
- 수집 시각과 출처 기록
- 실패 URL 재처리
- 로그와 모니터링

발표에서는 다음처럼 표현하는 것이 정확하다.

> KSPO 공공체육시설 CSV를 정제·정규화하여 Supabase PostgreSQL에 적재하는 공공데이터 ETL 파이프라인을 구현했습니다. 시설 홈페이지 운영시간 수집은 BeautifulSoup 기반의 기술 검증 단계이며, 운영용 자동 수집은 향후 과제입니다.

---

## 9. 더 품질 높은 시설 데이터 파이프라인

### 9.1 권장 구조

```text
[Extract]
KSPO 공식 API 또는 공식 CSV 다운로드 URL
        ↓
[Raw]
원본 파일 + checksum + 수집 시각 보관
        ↓
[Validate]
필수 컬럼, 인코딩, 건수, 좌표 범위 검사
        ↓
[Transform]
지역명, 주소, 시설 유형, 위·경도 정규화
        ↓
[Stage]
임시 테이블에 먼저 적재
        ↓
[Load]
고유 시설 ID 기준 upsert
        ↓
[Reconcile]
원본에서 사라진 시설 비활성화
        ↓
[Observe]
신규/수정/삭제/오류 건수와 실행시간 기록
```

### 9.2 현재 코드에서 개선할 부분

#### 1. 고유키

현재는 `name + address`로 `update_or_create()`한다. 시설명이나 도로명주소 표기가 바뀌면 같은 시설이 중복 생성될 수 있다.

권장 우선순위:

1. 원본 데이터의 시설 고유 ID 사용
2. 고유 ID가 없으면 공식 관리기관 ID와 시설 ID 조합
3. 마지막 대안으로 정규화한 이름·주소의 hash 사용

DB에도 `UniqueConstraint`를 추가해야 동시 실행에서 중복을 막을 수 있다.

#### 2. 잘못된 지역 fallback

현재 인식하지 못한 지역을 `서울특별시`로 저장한다.

```python
"region": region if region in valid_regions else "서울특별시"
```

이 방식은 알 수 없는 지역의 시설을 서울 시설로 오염시킨다. 다음 중 하나가 더 안전하다.

- 오류 행으로 기록하고 적재하지 않음
- `미분류` 상태로 저장
- 별도 검수 테이블로 보냄

#### 3. 실행 결과

현재 출력은 처리한 행 수 하나뿐이다. 다음 항목을 분리해야 한다.

```text
원본 행 수
신규 생성 수
수정 수
변경 없음 수
삭제/비활성화 수
검증 실패 수
중복 수
실행 시작·완료 시각
원본 파일 checksum
```

#### 4. 트랜잭션

전체 파일 검증 전에 운영 테이블을 한 행씩 변경하면 중간 실패 시 절반만 갱신될 수 있다. 작은 파일은 `transaction.atomic()`을 사용하고, 큰 파일은 staging table에 검증 후 교체·병합하는 것이 좋다.

#### 5. 추적 메타데이터

`Facility` 또는 별도 수집 이력 모델에 다음 값을 저장한다.

```text
source_name
source_record_id
source_url
source_updated_at
ingested_at
dataset_version
content_hash
last_seen_at
```

### 9.3 권장 관리 명령

운영에서는 `import_facilities`보다 목적이 명확한 명령으로 확장한다.

```powershell
python manage.py sync_facilities --source-url "공식 데이터 URL"
```

명령 내부 단계:

1. 공식 URL에서 파일 다운로드
2. timeout과 재시도
3. checksum으로 이전 데이터와 동일한지 확인
4. 필수 컬럼과 전체 건수 검증
5. 지역명·좌표 정규화
6. transaction 또는 staging table 사용
7. 고유 ID 기준 upsert
8. 마지막 확인 시각 갱신
9. 완전한 원본일 때만 누락 시설 비활성화
10. 실행 결과를 `DataSyncRun`에 기록

---

## 10. 크롤링은 어디에서 사용해야 하는가?

크롤링은 공식 API나 다운로드 데이터에 없는 정보가 꼭 필요한 경우에만 보조 수단으로 사용한다.

### 적절한 사용 후보

- 시설별 공식 홈페이지 운영시간
- 휴관일 안내
- 프로그램 또는 강좌 안내
- 전화번호와 예약 페이지

### 우선순위

```text
공식 Open API
  > 공식 CSV/JSON 다운로드
  > 기관이 허용한 개별 페이지 scraping
  > 검색엔진 결과나 비공식 사이트 crawling
```

공식 데이터가 있으면 크롤링보다 API 또는 파일 다운로드 자동화를 우선한다. HTML은 화면 개편으로 구조가 쉽게 바뀌고, robots.txt·이용약관·개인정보·요청 부하를 고려해야 하기 때문이다.

### 운영 크롤러의 필수 조건

- 허용된 출처만 수집
- 명확한 User-Agent와 연락처
- timeout 설정
- 시설별 요청 간격
- 429/5xx 재시도와 backoff
- 동일 도메인 동시 요청 제한
- HTML selector 변경 탐지
- 원문 URL과 수집 시각 기록
- 실패 큐와 재처리
- 응답 HTML 전체를 무기한 보관하지 않음
- 수집 결과를 바로 신뢰하지 않고 검증 후 반영

---

## 11. Cron은 어디에 사용해야 하는가?

Cron은 정해진 시간에 짧게 실행되고 종료되는 반복 작업에 사용한다. 웹 요청을 처리하는 Gunicorn 프로세스 안에서 `while True`나 `APScheduler`를 실행하는 방식은 권장하지 않는다.

그 이유는 다음과 같다.

- 웹 인스턴스가 여러 개면 같은 작업이 중복 실행될 수 있음
- Render가 재시작하면 실행 시점이 흔들림
- 무료 서비스가 정지하면 scheduler도 정지함
- 웹 요청 처리와 데이터 수집이 CPU·메모리를 경쟁함
- 실패 재처리와 실행 이력 관리가 어려움

### NETFIT Cron 후보

| 작업 | 권장 주기 | 이유 |
|---|---:|---|
| 공공시설 공식 데이터 동기화 | 주 1회 또는 원본 갱신주기 | 시설 변경 반영 |
| 시설 운영시간 수집 | 일 1회 이하 | 대상 사이트 부하 방지 |
| 만료된 친구·파티 초대 정리 | 매시간 또는 일 1회 | 상태 일관성 |
| 종료된 파티 상태 정리 | 매일 | 기간 기반 상태 갱신 |
| 통계·랭킹 집계 | 매일 새벽 | 조회 성능 개선 시 사용 |
| 고아 이미지 정리 | 주 1회 | Storage 비용 관리 |
| DB 백업 | Supabase 백업 정책 사용 | 앱 Cron보다 관리형 백업 권장 |

스포츠 뉴스는 요청 시 10분 캐시를 사용하는 현재 구조라면 별도 Cron이 반드시 필요하지 않다. 날씨도 사용자 위치와 요청 시점에 따라 달라지므로 미리 매일 수집하기보다 요청 시 조회가 적합하다.

---

## 12. Render Cron Job 구성

### 12.1 Django 관리 명령부터 만든다

예시 파일:

```text
fitness/management/commands/sync_facilities.py
```

실행 명령:

```text
python manage.py sync_facilities
```

관리 명령은 작업이 끝나면 반드시 종료되어야 한다. Render Cron Job은 실행 시간만큼 과금되고 persistent disk를 사용할 수 없으며, 모든 시간은 UTC 기준이다. [Render Cron Job 공식 문서](https://render.com/docs/cronjobs)

### 12.2 Render Dashboard

```text
Render Dashboard
→ New
→ Cron Job
→ Repository: pes9476/netfit
→ Branch: runsv
→ Build Command: pip install -r requirements.txt
→ Command: python manage.py sync_facilities
→ Environment: Web Service와 같은 DATABASE_URL 등
```

매주 월요일 한국시간 04:20에 실행하려면 UTC 전날 19:20이다.

```cron
20 19 * * SUN
```

정각에는 작업이 몰릴 수 있으므로 `00분`보다 `17분`, `23분`처럼 분산된 시각이 좋다.

### 12.3 Blueprint에 Cron 추가 예시

```yaml
  - type: cron
    name: netfit-facility-sync
    runtime: python
    branch: runsv
    schedule: "20 19 * * SUN"
    buildCommand: pip install -r requirements.txt
    startCommand: python manage.py sync_facilities
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: SECRET_KEY
        sync: false
```

Render Blueprint에서 Cron 서비스는 `type: cron`과 `schedule`을 사용한다. [Render Blueprint 명세](https://render.com/docs/blueprint-spec)

### 비용 주의

Render 무료 인스턴스는 Web Service, Postgres, Key Value 등 일부 서비스에 한정된다. 별도 Cron Job은 실행 비용과 지원 plan을 대시보드에서 확인해야 한다. [Render 무료 서비스 공식 문서](https://render.com/docs/free)

공모전 단계에서 유료 Cron을 사용하기 어렵다면 다음 대안이 있다.

1. GitHub Actions schedule이 `sync_facilities`를 실행하고 Supabase에 연결
2. 관리자가 Render Shell에서 제출 전 수동 동기화
3. SQL만으로 가능한 정리 작업은 Supabase의 DB 예약 기능 검토

GitHub Actions에 `DATABASE_URL`을 넣는 경우 GitHub Repository Secret을 사용해야 하며, Fork PR에는 운영 secret을 전달하면 안 된다.

---

## 13. GitHub Actions 예약 실행 대안

Render Cron 비용을 사용하지 않을 때 예시는 다음과 같다.

```yaml
name: Weekly Facility Sync

on:
  workflow_dispatch:
  schedule:
    - cron: "20 19 * * SUN"

permissions:
  contents: read

concurrency:
  group: facility-sync
  cancel-in-progress: false

jobs:
  sync:
    runs-on: ubuntu-latest
    environment: production

    env:
      DEBUG: "False"
      SECRET_KEY: ${{ secrets.DJANGO_SECRET_KEY }}
      DATABASE_URL: ${{ secrets.DATABASE_URL }}

    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip

      - run: python -m pip install -r requirements.txt
      - run: python manage.py sync_facilities
```

GitHub 예약 workflow는 기본 브랜치에서 실행된다. 따라서 실제 데이터 동기화 코드가 기본 브랜치에 있어야 한다. 운영 DB secret 접근 권한과 승인 정책을 함께 설정해야 한다.

---

## 14. 데이터 동기화 테스트 전략

데이터 파이프라인도 애플리케이션 코드와 동일하게 테스트해야 한다.

### 단위 테스트

- 지역명 변환
- 위도 `-90~90`, 경도 `-180~180` 범위
- 삭제 표시 행 제외
- 필수 시설명·주소 검증
- 고유 ID 생성
- 동일 행 hash 계산

### 통합 테스트

- 처음 적재 시 신규 생성
- 같은 파일 재실행 시 중복 없음
- 시설명 수정 시 동일 시설 갱신
- 한 행 오류가 전체 원본을 오염시키지 않음
- 미지원 지역이 서울로 저장되지 않음
- 원본 누락 시설 비활성화 정책
- 동시에 두 번 실행해도 중복 없음

### 운영 검증

동기화 전후에 다음 지표를 비교한다.

```text
전체 시설 수
지역별 시설 수
좌표 누락 비율
주소 누락 비율
신규/수정/비활성화 수
검증 실패 비율
실행 시간
원본 파일 checksum
```

예를 들어 전체 시설의 30%가 한 번에 사라지면 자동 반영하지 않고 실패 처리하여 잘못된 원본이나 parser 오류를 확인해야 한다.

---

## 15. 모니터링과 장애 대응

### 배포 모니터링

- GitHub Actions: 테스트 성공·실패
- Render Events/Deploys: build, migration, start log
- `/healthz/`: 애플리케이션과 DB 연결 상태
- Render notification: 배포 실패와 health check 실패

### 데이터 파이프라인 모니터링

- `DataSyncRun` 테이블에 실행 상태 저장
- 성공/실패, 시작/완료 시각, 처리 건수, 오류 요약
- 연속 실패 시 관리자 알림
- 로그에 DB 비밀번호, Kakao token, 사용자 개인정보 제외

권장 상태 모델:

```text
PENDING → RUNNING → SUCCESS
                  ↘ FAILED
                  ↘ PARTIAL
                  ↘ SKIPPED_NO_CHANGE
```

### 실패 원칙

- 다운로드 실패: 기존 운영 데이터 유지
- schema 불일치: 적재 중단
- 검증 실패 급증: 적재 중단
- 일부 개별 행 오류: 정책에 따라 격리 후 나머지 반영
- DB transaction 실패: rollback
- 중복 실행: lock을 획득한 하나만 실행

---

## 16. 권장 구현 순서

### 1단계 — 배포 대상 확정

- [x] Render 서비스의 실제 GitHub Branch를 `runsv`로 변경
- [x] GitHub에 없는 `netfit_tigger` 대신 원격에 존재하는 `runsv` 사용
- [ ] `testsv`는 테스트 브랜치, `runsv`는 운영 배포 브랜치로 보호 규칙 문서화
- [ ] 배포 브랜치에 branch protection 적용

### 2단계 — Render 전환

- [ ] `settings.py`에 `RENDER`, `RENDER_EXTERNAL_HOSTNAME` 반영
- [ ] `render.yaml` 추가
- [ ] Render 환경변수 입력
- [ ] Kakao 사이트 도메인을 `https://netfit-production.onrender.com`으로 등록
- [ ] Kakao Redirect URI를 `https://netfit-production.onrender.com/login/kakao/callback/`으로 등록
- [ ] `/healthz/`를 Health Check Path로 등록
- [ ] `railway.json`은 과거 설정으로 문서화하거나 제거 여부 결정

### 3단계 — CI/CD

- [ ] `.github/workflows/ci.yml` 추가
- [ ] Django check와 migration 검사
- [ ] 백엔드 테스트 실행
- [ ] Render Auto-Deploy를 `After CI Checks Pass`로 변경
- [ ] 실패 커밋이 배포되지 않는지 확인

### 4단계 — 데이터 파이프라인

- [ ] CSV Import를 크롤링이라고 부르지 않도록 문서 수정
- [ ] 고유 시설 ID와 DB unique constraint 추가
- [ ] 잘못된 지역의 서울 fallback 제거
- [ ] `DataSyncRun` 실행 이력 모델 추가
- [ ] `sync_facilities` 명령 구현
- [ ] 원본 checksum과 변경 건수 기록

### 5단계 — 스케줄링

- [ ] 공식 데이터 갱신 주기 확인
- [ ] Render Cron 또는 GitHub Actions schedule 선택
- [ ] 중복 실행 lock 추가
- [ ] 실패 알림 설정
- [ ] 수동 재실행 절차 작성

### 6단계 — 운영용 크롤링이 필요한 경우

- [ ] 공식 API/CSV에 정보가 없는지 먼저 확인
- [ ] 대상 사이트 robots.txt와 이용약관 확인
- [ ] 시설별 공식 URL 품질 점검
- [ ] rate limit, retry, parser 테스트 구현
- [ ] 원문·수집 시각·신뢰도 저장

---

## 17. 공모전 발표 표현

### 현재 상태를 정확히 표현하는 문장

> NETFIT은 KSPO 공공체육시설 CSV를 Django 관리 명령으로 정제하고 Supabase PostgreSQL에 중복을 억제하여 적재하는 ETL 구조를 구현했습니다. 현재는 수동 파일 적재 방식이며, 공식 데이터 갱신 주기에 맞춘 자동 다운로드와 예약 동기화를 확장 과제로 설계했습니다.

### 고도화 이후 사용할 수 있는 문장

> NETFIT은 KSPO 공공체육시설 데이터를 정기적으로 수집하고, 원본 검증·지역 표준화·중복 제거·변경 감지 과정을 거쳐 Supabase에 반영하는 자동 데이터 파이프라인을 운영합니다. CI에서 코드와 migration을 검증한 뒤 Render가 정상 버전만 배포하며, 시설 데이터 동기화는 독립된 Cron Job으로 실행됩니다.

### 피해야 할 표현

- “CSV를 DB에 넣었으므로 크롤링을 구현했다.”
- “실시간 데이터다.” — 주기 갱신이라면 갱신 주기를 밝혀야 함
- “중복이 절대 없다.” — DB unique constraint가 없으면 보장할 수 없음
- “지역경제를 활성화했다.” — 실제 효과 측정 전에는 기여 가능성으로 표현
- “CI/CD가 구축됐다.” — CI 파일과 배포 차단 조건이 실제로 동작해야 함

---

## 18. 최종 권장 구조

```text
                         ┌─────────────────────────┐
                         │ GitHub 기능 브랜치       │
                         └────────────┬────────────┘
                                      │ Pull Request
                                      ▼
                         ┌─────────────────────────┐
                         │ GitHub Actions CI       │
                         │ check / migration / test│
                         └────────────┬────────────┘
                                      │ 성공
                                      ▼
                         ┌─────────────────────────┐
                         │ Production branch       │
                         └────────────┬────────────┘
                                      │ checksPass
                                      ▼
                         ┌─────────────────────────┐
                         │ Render Web Service      │
                         │ build → migrate → start │
                         └────────────┬────────────┘
                                      │
                       /healthz/ 성공 │
                                      ▼
                         ┌─────────────────────────┐
                         │ NETFIT Web Application  │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │ Supabase PostgreSQL     │
                         └────────────▲────────────┘
                                      │ upsert
                                      │
┌───────────────────────┐  schedule  ┌┴────────────────────────┐
│ KSPO 공식 데이터       │ ─────────→ │ Render Cron / GH Actions│
│ API 또는 CSV download  │            │ sync_facilities         │
└───────────────────────┘            └─────────────────────────┘
```

이 구조에서 웹 서버, 배포, 데이터 수집을 분리하면 다음 효과가 있다.

- 잘못된 코드가 운영에 바로 배포되는 것을 방지
- migration 누락으로 인한 컬럼 오류 예방
- 데이터 동기화가 웹 요청 성능에 미치는 영향 감소
- 수집 실패 시 기존 시설 데이터 보존
- 언제 어떤 원본으로 DB가 변경됐는지 추적 가능
- 공모전 발표에서 단순 CSV 업로드가 아닌 검증 가능한 공공데이터 활용 구조 제시

---

## 19. 참고한 공식 문서

- [Render Django 배포](https://render.com/docs/deploy-django)
- [Render 배포와 CI 연동](https://render.com/docs/deploys)
- [Render Blueprint 명세](https://render.com/docs/blueprint-spec)
- [Render Cron Jobs](https://render.com/docs/cronjobs)
- [Render Health Checks](https://render.com/docs/health-checks)
- [Render 무료 서비스 제한](https://render.com/docs/free)
- [GitHub Actions workflow 문법](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
