# NETFIT `runsv` 파이프라인 구축 가이드 및 점검 체크리스트

## 문서 정보

| 항목 | 내용 |
|---|---|
| 작성 기준일 | 2026-09-22 |
| GitHub | <https://github.com/pes9476/netfit> |
| 운영 배포 브랜치 | `runsv` |
| Render 서비스 | `netfit-production` |
| 운영 주소 | <https://netfit-production.onrender.com/> |
| 애플리케이션 | Django |
| 운영 DB | Supabase PostgreSQL |

> 이 문서는 `runsv`를 실제 운영 배포 브랜치로 사용하는 현재 구조를 기준으로 한다. 체크박스의 `[x]`는 저장소 또는 운영 응답에서 확인한 항목이고, `[ ]`는 아직 구현·확인이 필요한 항목이다.

---

# 1. 전체 요약

## 현재 상태 한눈에 보기

```text
GitHub runsv
    ↓ push
Render Web Service
    ↓ build/start
Django + Gunicorn
    ↓
Supabase PostgreSQL
```

현재는 Render가 `runsv`를 배포하고 웹과 DB health check도 정상이다. 하지만 저장소 안에는 `render.yaml`과 GitHub Actions가 없으므로 다음 부분은 아직 자동화되지 않았다.

- 테스트 통과 여부에 따른 배포 차단
- Render 설정의 코드 버전 관리
- 공공시설 데이터 자동 다운로드
- 시설 데이터 검증 및 동기화 이력
- Cron 기반 정기 갱신
- 운영용 크롤링

## 최종 목표 구조

```text
기능 브랜치
    ↓ Pull Request
GitHub Actions CI
    ├─ Django check
    ├─ migration 검사
    ├─ 자동 테스트
    └─ collectstatic 검사
    ↓ 성공
runsv 병합
    ↓
Render CD
    ├─ dependency 설치
    ├─ collectstatic
    ├─ migrate
    ├─ Gunicorn 실행
    └─ /healthz/ 검사
    ↓
NETFIT 운영 서비스
    ↓
Supabase PostgreSQL

KSPO 공식 데이터
    ↓ 정기 실행
sync_facilities 관리 명령
    ├─ Extract
    ├─ Validate/Transform
    └─ Load/Upsert
    ↓
Facility 테이블
```

---

# 2. 현재 파이프라인 점검 결과

## 2.1 소프트웨어 배포 파이프라인

| 항목 | 현재 상태 | 위치 | 판정 |
|---|---|---|---|
| 운영 브랜치 | `runsv` | Render Dashboard | 확인됨 |
| 운영 URL | `netfit-production.onrender.com` | Render | 확인됨 |
| 웹 응답 | HTTP 200 | `/` | 정상 |
| DB health check | HTTP 200 | `/healthz/` | 정상 |
| Gunicorn | 설정 존재 | `Procfile` | 구현됨 |
| 정적 파일 | WhiteNoise | `config/settings.py` | 구현됨 |
| PostgreSQL 연결 | `DATABASE_URL` | `config/settings.py` | 구현됨 |
| Railway 설정 | 존재 | `railway.json` | Render에서는 미사용 |
| Render Blueprint | 없음 | `render.yaml` | 미구현 |
| GitHub Actions CI | 없음 | `.github/workflows/ci.yml` | 미구현 |
| CI 성공 후 배포 | 없음 | Render Auto-Deploy | 미구현 |
| 정기 작업 | 없음 | Render Cron/GitHub Actions | 미구현 |

## 2.2 데이터 파이프라인

| 항목 | 현재 상태 | 판정 |
|---|---|---|
| KSPO CSV 파일 | 저장소에 포함 | 구현됨 |
| CSV 읽기 | `csv.DictReader` | 구현됨 |
| 삭제 행 제외 | `DEL_AT == Y` 제외 | 구현됨 |
| 일부 지역명 변환 | `region_map` | 구현됨 |
| DB 적재 | `update_or_create()` | 구현됨 |
| 자동 다운로드 | 없음 | 미구현 |
| 원본 checksum | 없음 | 미구현 |
| 필수 컬럼 검증 | 부족 | 부분 구현 |
| 고유 시설 ID | 없음 | 미구현 |
| DB unique constraint | 없음 | 미구현 |
| 동기화 실행 이력 | 없음 | 미구현 |
| 정기 갱신 | 없음 | 미구현 |

## 2.3 크롤링과 스케줄링

| 항목 | 현재 상태 | 판정 |
|---|---|---|
| 단일 URL HTML 요청 | `scrape_facility_hours.py` | 예제 수준 |
| BeautifulSoup 파싱 | 제목·키워드 출력 | 예제 수준 |
| 여러 URL 순회 | 없음 | 미구현 |
| DB 저장 | 없음 | 미구현 |
| robots.txt/약관 점검 | 없음 | 미구현 |
| rate limit/retry | 없음 | 미구현 |
| Cron | 없음 | 미구현 |

---

# 3. 배포 파이프라인 구성 방법

## 3.1 브랜치 역할

권장 브랜치 정책은 다음과 같다.

| 브랜치 | 역할 | 직접 push |
|---|---|---|
| `runsv` | Render 운영 배포 | 금지 권장 |
| `testsv` | 통합 테스트 | 팀 정책에 따라 허용 |
| `netfit_giuk` | 개인 개발·검증 | 허용 |
| 기능 브랜치 | 기능 단위 개발 | 허용 |

권장 흐름:

```text
기능 브랜치 또는 netfit_giuk
    ↓ Pull Request
testsv 통합 테스트
    ↓ 검증 완료
runsv Pull Request
    ↓ CI 성공 + 리뷰 승인
Render 자동 배포
```

## 3.2 Render에서 실행해야 할 단계

### Build Command

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

역할:

1. Python dependency 설치
2. CSS, JavaScript, 이미지 정적 파일 수집
3. 빌드 실패 시 배포 중단

### Migration

유료 Render 환경에서는 Pre-Deploy Command가 가장 적합하다.

```bash
python manage.py migrate --noinput
```

무료 환경에서 Pre-Deploy를 사용할 수 없다면 Start Command 앞에 연결한다.

```bash
python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60
```

### Health Check

```text
/healthz/
```

정상 기준:

- HTTP 2xx 또는 3xx
- Django 프로세스 응답
- Supabase DB 연결 성공
- 비밀정보를 응답에 포함하지 않음

## 3.3 Render 환경변수

```env
DEBUG=False
SECRET_KEY=<긴 임의 문자열>
DATABASE_URL=<Supabase PostgreSQL URL>
ALLOWED_HOSTS=netfit-production.onrender.com
CSRF_TRUSTED_ORIGINS=https://netfit-production.onrender.com
SECURE_SSL_REDIRECT=True

KAKAO_REST_API_KEY=<REST API 키>
KAKAO_CLIENT_SECRET=<Client Secret>
KAKAO_REDIRECT_URI=https://netfit-production.onrender.com/login/kakao/callback/
```

주의사항:

- `ALLOWED_HOSTS`에는 `https://`를 넣지 않는다.
- `CSRF_TRUSTED_ORIGINS`에는 `https://`를 넣는다.
- 실제 값은 GitHub에 올리지 않는다.
- `.env`는 로컬 전용이다.
- Render에서는 Environment Variables에 입력한다.

## 3.4 `render.yaml`

저장소 루트에 다음 파일을 추가하면 Render 구성을 코드로 관리할 수 있다.

```yaml
services:
  - type: web
    name: netfit-production
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
        value: netfit-production.onrender.com
      - key: CSRF_TRUSTED_ORIGINS
        value: https://netfit-production.onrender.com
      - key: KAKAO_REST_API_KEY
        sync: false
      - key: KAKAO_CLIENT_SECRET
        sync: false
      - key: KAKAO_REDIRECT_URI
        value: https://netfit-production.onrender.com/login/kakao/callback/
```

> `autoDeployTrigger: checksPass`는 GitHub Actions CI를 먼저 구성한 뒤 적용한다. CI가 없으면 Render가 기다릴 검사 결과가 없다.

---

# 4. ETL과 ELT 중 무엇을 선택해야 하는가?

## 4.1 용어 차이

### ETL

```text
Extract → Transform → Load
추출       변환          적재
```

DB에 넣기 전에 데이터 형식과 품질을 검증한다.

### ELT

```text
Extract → Load → Transform
추출       원본 적재    DB 내부 변환
```

원본을 먼저 데이터 웨어하우스에 넣고 SQL 등으로 변환한다.

## 4.2 NETFIT 권장 방식

NETFIT에는 **ETL 중심의 혼합형 구조**가 적합하다.

이유:

- Supabase DB 용량이 제한적이다.
- 운영 `Facility` 테이블에 잘못된 지역·좌표를 넣으면 추천 결과가 오염된다.
- 데이터 규모가 빅데이터 웨어하우스를 필요로 할 정도로 크지 않다.
- Django 관리 명령에서 검증과 정규화를 수행하기 쉽다.
- 원본 파일은 DB가 아니라 Supabase Storage 등에 보관할 수 있다.

권장 구조:

```text
공식 API/CSV
    ↓ Extract
임시 파일 또는 Supabase Storage Raw 영역
    ↓ Validate + Transform
Django sync_facilities
    ↓ Load
Supabase Facility 테이블
```

이는 원본을 별도로 보존한다는 점에서는 ELT의 장점을 일부 사용하지만, 운영 테이블에는 변환 완료 데이터만 넣으므로 핵심은 ETL이다.

## 4.3 현재 CSV 적재의 정확한 명칭

현재 작업은 크롤링이 아니라 다음에 해당한다.

```text
수동 CSV Import
또는
부분 ETL: CSV 읽기 → 일부 변환 → DB 적재
```

발표 문장:

> KSPO 공공체육시설 CSV를 읽어 지역명과 삭제 여부를 정제한 후 Supabase PostgreSQL에 upsert하는 공공데이터 ETL 구조를 구현했습니다.

## 4.4 권장 데이터 파이프라인

### Extract

1. 공식 Open API 또는 공식 다운로드 URL 사용
2. timeout 설정
3. 다운로드 응답 상태와 Content-Type 확인
4. 원본 파일 SHA-256 checksum 계산
5. 동일 checksum이면 적재 생략
6. 원본 출처, 다운로드 시각, 버전 기록

### Validate

1. 필수 컬럼 존재 여부
2. 파일 인코딩
3. 전체 행 수 급감 여부
4. 시설명·주소 누락 여부
5. 위도 `-90~90`
6. 경도 `-180~180`
7. 행정구역 허용값
8. 삭제 표시값 형식

### Transform

1. 앞뒤 공백 제거
2. 지역명 표준화
3. 주소 정규화
4. 시설 유형 표준화
5. 숫자 좌표 변환
6. 원본 고유 시설 ID 확보
7. 고유 ID가 없으면 정규화 키 생성

### Load

1. `transaction.atomic()` 사용
2. 고유 시설 ID 기준 upsert
3. 신규·수정·변경 없음 건수 분리
4. 완전한 원본일 때만 누락 시설 비활성화
5. 실행 결과 저장
6. 실패 시 rollback

## 4.5 현재 코드의 위험요소

### `name + address` 중복 판별

시설명이나 주소 표기가 바뀌면 같은 시설이 새 행으로 생성될 수 있다. 원본 시설 ID와 DB `UniqueConstraint`가 필요하다.

### 잘못된 지역의 서울 fallback

현재 미지원 지역이 `서울특별시`로 저장될 수 있다.

```python
"region": region if region in valid_regions else "서울특별시"
```

권장 처리:

- 적재 제외 후 오류 기록
- `미분류` 상태로 저장
- 검수 큐로 이동

서울로 강제 변환하는 방식은 데이터 오염이므로 제거해야 한다.

## 4.6 권장 모델

```python
class DataSyncRun(models.Model):
    status = models.CharField(max_length=20)
    source_name = models.CharField(max_length=100)
    source_url = models.URLField(blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    source_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)
```

시설에 추가할 권장 필드:

```text
source_record_id
source_name
source_updated_at
ingested_at
last_seen_at
content_hash
```

---

# 5. CI 구현 방법

## 5.1 CI의 역할

CI는 코드를 배포하는 기능이 아니라 **배포 가능한 코드인지 자동 검증하는 과정**이다.

NETFIT CI가 검사할 항목:

1. Python dependency 설치 가능 여부
2. Django 설정 오류
3. 모델 변경 후 migration 누락
4. 로그인·미션·친구·파티 테스트
5. 정적 파일 수집
6. 비밀정보가 코드에 포함되지 않았는지 검사

## 5.2 GitHub Actions 파일

경로:

```text
.github/workflows/ci.yml
```

권장 내용:

```yaml
name: NetFit CI

on:
  push:
    branches: [runsv, testsv, netfit_giuk]
  pull_request:
    branches: [runsv]

permissions:
  contents: read

jobs:
  django-test:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    env:
      USE_SQLITE: "1"
      DEBUG: "True"
      SECRET_KEY: "ci-test-only-secret"

    steps:
      - name: Checkout
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip

      - name: Install dependencies
        run: python -m pip install -r requirements.txt

      - name: Django system check
        run: python manage.py check

      - name: Check migration files
        run: python manage.py makemigrations --check --dry-run

      - name: Run backend tests
        run: >-
          python manage.py test
          config.test_deployment
          fitness.test_kakao
          fitness.test_local_auth
          fitness.test_logout
          fitness.test_mascots
          fitness.test_web_flow
          -v 2

      - name: Collect static files
        run: python manage.py collectstatic --noinput
```

## 5.3 Selenium 분리

Selenium은 다음 이유로 필수 백엔드 CI와 분리한다.

- Chrome/ChromeDriver 필요
- 외부 다운로드 장애 가능
- 백엔드는 정상인데 브라우저 환경 때문에 배포가 막힐 수 있음
- 실행 시간이 길어짐

권장 구성:

```text
ci.yml       → 배포를 막는 필수 백엔드 검사
ui-test.yml  → 별도 브라우저 테스트
```

---

# 6. CD 구현 방법

## 6.1 CD의 역할

CD는 CI를 통과한 코드를 Render 운영 환경에 자동 반영하는 과정이다.

```text
runsv push
    ↓
GitHub Actions 성공
    ↓
Render After CI Checks Pass
    ↓
Build
    ↓
Migration
    ↓
Start
    ↓
Health Check
    ↓
운영 반영
```

## 6.2 Render 설정

```text
Render Dashboard
→ netfit-production
→ Settings
→ Build & Deploy
```

확인할 값:

```text
Repository: pes9476/netfit
Branch: runsv
Auto-Deploy: After CI Checks Pass
Health Check Path: /healthz/
```

## 6.3 실패 동작

| 실패 위치 | 기대 동작 |
|---|---|
| CI 테스트 실패 | Render 배포 시작 안 함 |
| Build 실패 | 기존 정상 버전 유지 |
| Migration 실패 | 새 버전 시작 안 함 |
| Gunicorn 시작 실패 | 배포 실패 |
| Health check 실패 | 트래픽 전환 안 함 |

---

# 7. 크롤링은 어떻게 적용해야 하는가?

## 7.1 CSV 적재와 크롤링 구분

| 방식 | 설명 | NETFIT |
|---|---|---|
| CSV Import | 보유한 파일을 DB에 적재 | 현재 구현 |
| API 수집 | 공식 API 호출 | 시설 데이터 미구현 |
| Download automation | 공식 CSV URL 자동 다운로드 | 미구현 |
| Scraping | 한 페이지에서 특정 값 추출 | 예제 수준 |
| Crawling | 여러 페이지를 규칙적으로 순회 | 미구현 |

## 7.2 크롤링을 사용할 위치

공식 CSV/API에 없는 다음 정보에 한해서 사용한다.

- 시설 운영시간
- 휴관일
- 프로그램 안내
- 예약 URL
- 시설별 공지사항

우선순위:

```text
공식 API
  > 공식 CSV/JSON
  > 허용된 공식 홈페이지 scraping
  > 비공식 사이트 crawling
```

## 7.3 현재 `scrape_facility_hours.py`

현재 기능:

```text
URL 1개 요청
  → HTML 파싱
  → 제목과 운영시간 관련 후보 단어 출력
```

아직 없는 기능:

- 시설 목록 순회
- selector별 구조화 데이터 추출
- DB 저장
- 요청 간격 제한
- 재시도
- 변경 감지
- 실행 이력
- 실패 URL 재처리

따라서 발표에서는 “운영용 크롤링 구현”이 아니라 **BeautifulSoup 수집 기술 검증**이라고 표현한다.

## 7.4 운영 크롤러 필수 조건

- robots.txt 확인
- 사이트 이용약관 확인
- 개인정보 수집 금지
- 식별 가능한 User-Agent
- 연결·읽기 timeout
- 도메인별 요청 간격
- HTTP 429/5xx backoff
- 최대 재시도 횟수
- 원본 URL과 수집 시각 저장
- selector 변경 탐지
- 실패 데이터 격리
- 실행 결과 모니터링

---

# 8. Cron은 어디에 적용해야 하는가?

## 8.1 Cron에 적합한 작업

| 작업 | 권장 주기 | 비고 |
|---|---:|---|
| KSPO 시설 데이터 동기화 | 주 1회 | 원본 갱신주기 우선 |
| 운영시간 scraping | 일 1회 이하 | 사이트 부하 주의 |
| 만료 초대 정리 | 매시간/매일 | 상태값이 자동 계산이면 불필요할 수 있음 |
| 종료 파티 정리 | 매일 | 날짜 기반 조회로 대체 가능 |
| 랭킹 집계 | 매일 | 사용자 증가 후 도입 |
| 고아 파일 정리 | 주 1회 | Supabase Storage 전환 후 |

날씨는 사용자 위치와 현재 시점에 따라 달라지므로 요청 시 조회가 적합하다. 스포츠 뉴스도 현재 요청 시 캐시 구조라면 Cron 우선순위가 낮다.

## 8.2 웹 서버 안에 scheduler를 넣지 않는 이유

Gunicorn 프로세스 내부에서 `while True`, `APScheduler`를 실행하면 다음 문제가 생긴다.

- worker 수만큼 중복 실행
- 배포·재시작 시 실행 시간 변경
- 웹 요청과 CPU·메모리 경쟁
- 무료 인스턴스 sleep 시 중단
- 실패 이력 확인 어려움

따라서 별도의 Render Cron Job 또는 GitHub Actions schedule을 사용한다.

## 8.3 Django 관리 명령

권장 파일:

```text
fitness/management/commands/sync_facilities.py
```

실행:

```bash
python manage.py sync_facilities
```

필수 동작:

1. 중복 실행 lock 획득
2. 공식 데이터 다운로드
3. checksum 비교
4. 검증과 정규화
5. transaction 적재
6. `DataSyncRun` 기록
7. lock 해제
8. 정상/실패 exit code 반환

## 8.4 Render Cron

```text
Render Dashboard
→ New
→ Cron Job
→ Repository: pes9476/netfit
→ Branch: runsv
→ Build: pip install -r requirements.txt
→ Command: python manage.py sync_facilities
```

한국시간 월요일 04:20 실행 예시:

```cron
20 19 * * SUN
```

Render Cron 시간은 UTC이므로 한국시간에서 9시간을 빼야 한다.

## 8.5 GitHub Actions schedule 대안

Render Cron 비용이 부담되면 GitHub Actions를 사용할 수 있다.

```yaml
name: Weekly Facility Sync

on:
  workflow_dispatch:
  schedule:
    - cron: "20 19 * * SUN"

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

주의사항:

- 운영 DB URL은 GitHub Secret에 저장한다.
- Fork Pull Request에는 운영 secret을 전달하지 않는다.
- GitHub Environment에 production 승인을 설정할 수 있다.
- DB 작업은 반드시 중복 실행을 방어한다.

---

# 9. 모니터링 구성

## 배포 모니터링

```text
GitHub Actions → CI 성공/실패
Render Deploys → build/start 로그
/healthz/      → Django/DB 상태
```

## 데이터 동기화 모니터링

기록할 값:

```text
실행 ID
상태
원본 URL/버전
checksum
시작·완료 시각
전체 행 수
신규 수
수정 수
비활성화 수
실패 수
오류 요약
```

권장 상태:

```text
PENDING
RUNNING
SUCCESS
FAILED
PARTIAL
SKIPPED_NO_CHANGE
```

실패 원칙:

- 다운로드 실패 → 기존 데이터 유지
- 필수 컬럼 없음 → 전체 적재 중단
- 행 수 비정상 급감 → 전체 적재 중단
- DB 오류 → rollback
- 개별 행 오류 → 격리 후 정책에 따라 진행
- 동시 실행 → 하나만 실행

---

# 10. 구현 순서

## 1단계: CI 구축

1. `.github/workflows/ci.yml` 생성
2. `runsv` push와 Pull Request에서 실행
3. Django check 실행
4. migration 누락 검사
5. 자동 테스트 실행
6. collectstatic 검사

## 2단계: CD 연결

1. Render Branch가 `runsv`인지 확인
2. Auto-Deploy를 `After CI Checks Pass`로 변경
3. `/healthz/` 설정
4. 실패하는 PR로 배포 차단 시험
5. 정상 PR로 배포 성공 시험

## 3단계: Render 설정 코드화

1. `render.yaml` 생성
2. 환경변수 secret 분리
3. migration 실행 위치 확정
4. Railway 전용 파일 보존/제거 정책 결정

## 4단계: ETL 개선

1. 지역 서울 fallback 제거
2. 원본 시설 ID 확인
3. DB unique constraint 추가
4. `DataSyncRun` 추가
5. `sync_facilities` 구현
6. 중복·실패·rollback 테스트

## 5단계: 정기 실행

1. KSPO 원본 갱신주기 확인
2. Render Cron 또는 GitHub schedule 선택
3. 운영 secret 연결
4. 중복 실행 방지
5. 실패 알림과 수동 재실행 절차 작성

## 6단계: 필요 시 크롤링

1. 공식 API/CSV에 없는 필드 확정
2. 수집 허용 여부 확인
3. 대상 홈페이지별 parser 구현
4. rate limit/retry 적용
5. 신뢰도와 출처 기록

---

# 11. 최종 점검 체크리스트

## A. 브랜치와 배포

- [x] Render 운영 브랜치는 `runsv`
- [x] 운영 URL 접속 성공
- [x] `/healthz/` HTTP 200 확인
- [ ] `runsv` branch protection 적용
- [ ] 직접 push 제한
- [ ] Pull Request 리뷰 필수화
- [ ] 운영 배포 커밋 SHA 기록

## B. Render

- [x] Gunicorn 설정 존재
- [x] WhiteNoise 설정 존재
- [x] Supabase `DATABASE_URL` 사용
- [ ] `render.yaml` 생성
- [ ] `RENDER_EXTERNAL_HOSTNAME` 코드 반영본을 `runsv`에 병합
- [ ] `DEBUG=False` 확인
- [ ] `ALLOWED_HOSTS` 확인
- [ ] `CSRF_TRUSTED_ORIGINS` 확인
- [ ] Kakao Render Redirect URI 확인
- [ ] migration 자동 실행 확인
- [ ] health check 경로 등록 확인

## C. CI

- [ ] `.github/workflows/ci.yml` 생성
- [ ] dependency 설치 검사
- [ ] Django system check
- [ ] `makemigrations --check --dry-run`
- [ ] 백엔드 테스트
- [ ] 정적 파일 수집 검사
- [ ] CI 실패 시 Pull Request 병합 차단
- [ ] Selenium workflow 분리

## D. CD

- [ ] Render `After CI Checks Pass` 설정
- [ ] CI 실패 커밋 배포 차단 확인
- [ ] Build 실패 시 기존 버전 유지 확인
- [ ] Migration 실패 시 배포 중단 확인
- [ ] Health check 실패 시 트래픽 전환 차단 확인
- [ ] 배포 rollback 절차 작성

## E. ETL

- [x] CSV 읽기 구현
- [x] 삭제 표시 행 제외
- [x] 일부 지역명 정규화
- [x] `update_or_create()` 적재
- [ ] 공식 다운로드/API URL 확정
- [ ] checksum 계산
- [ ] 필수 컬럼 검증
- [ ] 좌표 범위 검증
- [ ] 서울 fallback 제거
- [ ] 고유 시설 ID 추가
- [ ] DB unique constraint 추가
- [ ] transaction 또는 staging 적용
- [ ] `DataSyncRun` 구현
- [ ] 신규·수정·실패 건수 기록
- [ ] 원본 급감 안전장치

## F. ELT 판단

- [x] 운영 DB에는 정제 데이터만 저장하는 ETL 선택
- [ ] Raw 원본 보관 위치 결정
- [ ] Supabase Storage bucket 검토
- [ ] 원본 보존 기간 결정
- [ ] DB 용량 사용량 모니터링

## G. 크롤링

- [x] BeautifulSoup 기술 예제 존재
- [ ] 크롤링 필요 필드 확정
- [ ] 공식 API/CSV 우선 검토
- [ ] robots.txt 확인
- [ ] 이용약관 확인
- [ ] User-Agent 설정
- [ ] timeout/retry/backoff
- [ ] 요청 간격 제한
- [ ] selector 변경 테스트
- [ ] 수집 시각·원본 URL 기록
- [ ] 실패 URL 재처리

## H. Cron

- [ ] 공식 데이터 갱신주기 확인
- [ ] `sync_facilities` 관리 명령 구현
- [ ] Render Cron/GitHub schedule 선택
- [ ] UTC↔KST 시간 확인
- [ ] 중복 실행 lock
- [ ] 정상 종료 exit code
- [ ] 실패 알림
- [ ] 수동 재실행 방법

## I. 보안과 운영

- [x] 실제 secret은 `.env`/Render Variables 사용
- [ ] GitHub secret scanning 확인
- [ ] 노출된 DB 비밀번호 회전
- [ ] 로그 개인정보 제거
- [ ] Supabase 백업 정책 확인
- [ ] 인증사진을 Supabase Storage로 이전
- [ ] 운영 장애 대응 담당자 지정

---

# 12. 공모전 발표용 표현

## 현재 구현 기준

> NETFIT은 `runsv` 브랜치를 기준으로 Render에 자동 배포되고 있으며, Django 애플리케이션은 Supabase PostgreSQL과 연결되어 운영됩니다. 공공체육시설 데이터는 KSPO CSV를 Django 관리 명령으로 읽어 지역명을 정규화하고 중복을 억제하여 적재하는 ETL 구조를 사용합니다.

## 자동화 완료 후

> GitHub Actions가 Django 설정, migration, 테스트를 검증한 뒤 정상 코드만 Render에 배포합니다. KSPO 공공체육시설 데이터는 정기 작업을 통해 자동 수집되며, 원본 검증·지역 표준화·중복 제거·변경 감지 과정을 거쳐 Supabase에 반영됩니다.

## 정확한 용어

| 현재 기능 | 발표 표현 |
|---|---|
| CSV 수동 적재 | 공공데이터 ETL/Import |
| BeautifulSoup 단일 URL 예제 | 웹 데이터 수집 기술 검증 |
| Render push 배포 | 자동 배포/CD 일부 구현 |
| GitHub Actions 추가 후 | CI/CD 구축 |
| Cron 추가 후 | 정기 데이터 동기화 |

다음 표현은 구현 전에는 사용하지 않는다.

- “실시간 시설 데이터 수집”
- “운영용 크롤링 완료”
- “완전한 CI/CD 구축”
- “중복이 절대 발생하지 않음”
- “지역경제 활성화 효과 입증”

---

# 13. 관련 파일

| 파일 | 역할 |
|---|---|
| `config/settings.py` | 환경변수, DB, 보안, 정적 파일 |
| `config/deployment_views.py` | `/healthz/` |
| `Procfile` | Gunicorn 시작 명령 |
| `railway.json` | 과거 Railway 배포 설정 |
| `requirements.txt` | Python dependency |
| `fitness/models.py` | Facility 등 DB 모델 |
| `fitness/management/commands/import_facilities.py` | 현재 CSV Import |
| `fitness/management/commands/scrape_facility_hours.py` | BeautifulSoup 예제 |
| `.github/workflows/ci.yml` | 추가할 CI 파일 |
| `render.yaml` | 추가할 Render Blueprint |
| `fitness/management/commands/sync_facilities.py` | 추가할 ETL 동기화 명령 |

---

# 14. 완료 기준

다음 흐름이 실제로 증명되면 기본 파이프라인 구축이 완료된 것으로 판단한다.

```text
1. 개발자가 Pull Request 생성
2. GitHub Actions 자동 실행
3. 실패 테스트가 있으면 병합·배포 차단
4. 성공하면 runsv 병합
5. Render 자동 build
6. Supabase migration 성공
7. Gunicorn 시작
8. /healthz/ 통과
9. 새 버전 서비스 반영
10. 예약 시간에 시설 데이터 동기화
11. 동기화 결과와 변경 건수 기록
12. 실패 시 기존 시설 데이터 유지 및 알림
```

이 기준을 만족하면 NETFIT은 단순히 “배포된 Django 웹”을 넘어, 코드와 공공데이터를 지속적으로 검증·배포·갱신할 수 있는 운영 구조를 갖추게 된다.

