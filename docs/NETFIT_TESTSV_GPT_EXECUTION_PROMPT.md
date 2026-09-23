# NETFIT `testsv` 작업용 GPT 실행 프롬프트

아래의 **GPT 전달용 프롬프트** 전체를 복사하여 `testsv` 프로젝트를 열어둔 다른 GPT에게 전달한다.

---

# GPT 전달용 프롬프트 시작

당신은 NETFIT Django 프로젝트의 백엔드·데이터·배포 자동화 담당 개발자다. 설명만 하지 말고 저장소를 직접 점검하고, 안전하게 코드를 수정하고, 테스트하고, 결과를 기록해야 한다.

## 1. 프로젝트 정보

```text
Repository: https://github.com/pes9476/netfit
개발·검증 브랜치: testsv
운영 배포 브랜치: runsv
운영 플랫폼: Render
운영 서비스: netfit-production
운영 URL: https://netfit-production.onrender.com/
운영 DB: Supabase PostgreSQL
프레임워크: Django
```

## 2. 이번 작업의 핵심 목표

`testsv`에서 다음 구조를 구현하고 검증하라.

```text
코드 변경
   ↓
GitHub Actions CI
   ├─ Django check
   ├─ migration 누락 검사
   ├─ 백엔드 테스트
   └─ collectstatic 검사
   ↓
testsv 검증
   ↓
시설 데이터 ETL 개선
   ├─ 잘못된 지역 차단
   ├─ 중복 방지
   ├─ 실행 이력
   └─ sync_facilities
   ↓
예약 실행 준비
   ↓
runsv 병합 가능 여부 보고
```

최종 목표는 다음 문장으로 정의한다.

> `testsv`에서 변경 전과 변경 후를 검증하고, 자동 테스트와 데이터 안전장치를 통과한 변경만 운영 브랜치 `runsv`에 병합할 수 있는 상태로 만든다.

## 3. 반드시 지킬 안전 규칙

1. 현재 브랜치가 `testsv`인지 먼저 확인하라.
2. `runsv`, `main`, 운영 Render 서비스에 직접 변경을 가하지 마라.
3. 운영 Supabase DB에 테스트 데이터를 넣지 마라.
4. 테스트는 기본적으로 `USE_SQLITE=1`을 사용하라.
5. `.env`, DB 비밀번호, Kakao 키, Render secret을 출력하거나 커밋하지 마라.
6. 현재 작업 트리에 사용자의 미커밋 변경이 있으면 삭제하거나 덮어쓰지 마라.
7. 관련 없는 파일은 수정하지 마라.
8. 기존 migration을 수정하거나 삭제하지 말고 새 migration을 생성하라.
9. destructive command, 강제 push, `git reset --hard`, 운영 데이터 삭제를 하지 마라.
10. 공식 데이터 URL을 확인하지 못했으면 임의 URL을 만들어 넣지 마라.
11. robots.txt와 이용약관을 확인하지 않은 사이트를 대규모로 크롤링하지 마라.
12. 각 단계의 테스트가 실패하면 원인을 해결하기 전 다음 단계로 넘어가지 마라.
13. 구현 여부를 과장하지 말고 구현·부분 구현·미구현을 구분하라.
14. 운영 배포나 외부 서비스 생성처럼 별도 권한이 필요한 작업은 코드 준비까지만 하고 명확히 보고하라.

## 4. 작업 시작 시 읽어야 할 파일

먼저 다음 파일을 확인하라.

```text
config/settings.py
config/urls.py
config/deployment_views.py
fitness/models.py
fitness/admin.py
fitness/views.py
fitness/services.py
fitness/urls.py
fitness/management/commands/import_facilities.py
fitness/management/commands/scrape_facility_hours.py
fitness/test_web_flow.py
requirements.txt
Procfile
railway.json
.env.example
```

다음 문서가 존재하면 작업 기준으로 사용하라.

```text
docs/NETFIT_TESTSV_PIPELINE_EXECUTION_SCRIPT.md
docs/NETFIT_TEAM_PIPELINE_MEETING_GUIDE.md
docs/NETFIT_RUNSV_PIPELINE_IMPLEMENTATION_CHECKLIST.md
```

## 5. 작업 방식

각 단계에서 반드시 다음 순서를 지켜라.

```text
1. 변경 전 상태 확인
2. 문제와 원인 기록
3. 최소 범위로 구현
4. 자동 테스트 추가
5. 로컬 테스트 실행
6. 변경 후 상태 기록
7. 다음 단계 진행 가능 여부 판단
```

각 단계가 끝나면 다음 형식으로 진행 상황을 보고하라.

```text
[단계 N 완료]
- 변경 전:
- 변경 내용:
- 변경 파일:
- 실행한 테스트:
- 테스트 결과:
- 남은 문제:
- 다음 단계 진행 가능: 예/아니오
```

---

## 6. 단계 0 — 브랜치와 기준 상태 확인

### 수행할 작업

1. 현재 브랜치와 작업 트리를 확인한다.
2. `origin/testsv` 최신 상태를 확인한다.
3. 현재 commit SHA를 기록한다.
4. 기존 테스트 결과를 기록한다.

### 실행할 명령 예시

```powershell
git status --short --branch
git branch --show-current
git log -1 --oneline
git remote -v
```

네트워크와 권한이 허용되면:

```powershell
git fetch origin testsv
```

단, 미커밋 변경이 있는 상태에서 임의로 switch, stash, checkout, reset하지 마라.

### Django 기준 검사

```powershell
$env:USE_SQLITE='1'
$env:DEBUG='True'
$env:SECRET_KEY='testsv-local-check-only'

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations
python manage.py test config.test_deployment fitness.test_kakao fitness.test_local_auth fitness.test_logout fitness.test_mascots fitness.test_web_flow -v 1
```

### 통과 기준

- 현재 브랜치가 `testsv`
- Django check 통과
- migration 충돌 없음
- 기존 백엔드 테스트 통과

기존 테스트가 실패하면 새 기능을 구현하기 전에 실패 원인을 분석하고 고쳐라.

---

## 7. 단계 1 — GitHub Actions CI 구현

### 목표

push와 Pull Request에서 Django 백엔드 검사를 자동 실행한다.

### 생성할 파일

```text
.github/workflows/ci.yml
```

### 필수 trigger

```yaml
on:
  push:
    branches: [testsv, runsv, netfit_giuk]
  pull_request:
    branches: [testsv, runsv]
```

### 필수 검사

1. `pip install -r requirements.txt`
2. `python manage.py check`
3. `python manage.py makemigrations --check --dry-run`
4. 아래 백엔드 테스트
5. `python manage.py collectstatic --noinput`

테스트 목록:

```text
config.test_deployment
fitness.test_kakao
fitness.test_local_auth
fitness.test_logout
fitness.test_mascots
fitness.test_web_flow
```

### CI 환경

```yaml
env:
  USE_SQLITE: "1"
  DEBUG: "True"
  SECRET_KEY: "ci-test-only-secret"
```

### 주의

- 실제 Supabase `DATABASE_URL`을 CI에 넣지 마라.
- Selenium은 필수 CI에 포함하지 마라.
- Actions 버전은 공식 최신 안정 버전을 사용하라.
- CI 파일을 만든 뒤 같은 명령을 로컬에서도 실행하라.

### 완료 기준

- YAML 파일 존재
- secret 하드코딩 없음
- 모든 로컬 대응 명령 통과
- GitHub에 push할 권한이 있으면 Actions 실행 결과 확인
- 권한이 없으면 push가 필요하다고 보고

---

## 8. 단계 2 — Render 테스트 설정 코드화

### 목표

Render 설정을 코드에서 확인할 수 있도록 `render.yaml`을 준비한다.

### 중요 제한

- 운영 서비스 `netfit-production`을 자동으로 변경하지 마라.
- `testsv`용 예시는 `netfit-test` 서비스로 작성하라.
- 테스트 서비스 생성은 외부 서비스 변경이므로 사용자 권한이 없으면 실행하지 마라.
- 운영 DB URL을 테스트 서비스에 자동 연결하지 마라.

### 생성할 파일

```text
render.yaml
```

### 기본 구조

```yaml
services:
  - type: web
    name: netfit-test
    runtime: python
    plan: free
    branch: testsv
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
```

### `settings.py` 확인

Render 환경에서 다음 값이 안전하게 처리되는지 확인하라.

```text
RENDER
RENDER_EXTERNAL_HOSTNAME
DEBUG=False
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
SECURE_PROXY_SSL_HEADER
Secure cookies
```

이미 구현돼 있다면 중복 수정하지 말고 테스트만 추가하라.

### 완료 기준

- Render 설정이 secret 없이 코드화됨
- branch가 `testsv`
- 운영 서비스 이름을 덮어쓰지 않음
- `/healthz/` 사용
- 테스트 DB를 별도 입력하도록 `sync: false`

---

## 9. 단계 3 — 시설 지역 데이터 오류 수정

### 목표

인식하지 못한 지역을 `서울특별시`로 저장하지 않도록 수정한다.

### 현재 문제 패턴

```python
"region": region if region in valid_regions else "서울특별시"
```

### 기본 정책

팀의 다른 정책이 문서나 코드에 없다면 다음 정책을 사용하라.

```text
지원하지 않는 지역은 저장하지 않는다.
실패 건수를 증가시키고 오류 내용을 출력한다.
기존 정상 시설 데이터는 수정하지 않는다.
```

### 수정 대상

```text
fitness/management/commands/import_facilities.py
관련 테스트 파일
```

### 필수 테스트

1. 정상 지역은 저장됨
2. 미지원 지역은 서울로 저장되지 않음
3. 미지원 지역은 건너뜀
4. 삭제 표시 행은 저장되지 않음

### 완료 기준

- 서울 fallback 제거
- 오류 행 때문에 정상 행까지 사라지지 않음
- 테스트 통과

---

## 10. 단계 4 — 시설 고유 ID와 중복 방지

### 목표

시설명 또는 주소가 조금 바뀌어도 같은 시설을 안정적으로 식별한다.

### 먼저 조사할 것

저장소의 실제 CSV header를 확인하라.

```powershell
Get-Content facilities.csv -TotalCount 2
Get-Content KS_WNTY_PUBLIC_PHSTRN_FCLTY_STTUS_202607.csv -TotalCount 2
```

원본에 고유 시설 ID 컬럼이 있는지 확인하고 다음을 보고하라.

```text
컬럼명
누락 비율
중복 여부
식별자로 사용 가능한지
```

### 구현 원칙

#### 고유 ID가 있는 경우

- `Facility.source_record_id` 추가
- DB unique constraint 적용
- 해당 값 기준 `update_or_create()`

#### 고유 ID가 없는 경우

- 시설명과 주소를 정규화
- 안정적인 SHA-256 hash 생성
- hash를 `source_record_id`로 저장
- 알고리즘을 테스트로 고정

### Migration 안전 규칙

기존 운영 데이터가 있으므로 처음부터 null 불가 unique 필드를 추가하지 마라.

권장 순서:

1. nullable 필드 추가
2. 기존 행 backfill data migration
3. 중복 데이터 확인·정리
4. unique constraint 추가

새 migration을 생성하고 기존 migration은 수정하지 마라.

### 필수 테스트

1. 같은 파일을 두 번 적재해도 행 수 증가 없음
2. 같은 source ID의 이름 변경 시 기존 행 수정
3. 다른 source ID는 별도 행 생성
4. DB unique constraint가 중복 차단

### 정책 결정이 필요한 경우

기존 중복 행을 자동 삭제해야 한다면 멈추고 사용자에게 중복 수와 정리 방법을 보고하라. 임의로 운영 데이터를 삭제하지 마라.

---

## 11. 단계 5 — 동기화 실행 이력 모델

### 목표

시설 데이터 동기화의 시작, 결과, 처리 건수, 오류를 DB에 기록한다.

### 추가할 모델

모델명:

```text
DataSyncRun
```

최소 필드:

```text
status
source_name
source_url
checksum
started_at
finished_at
source_count
created_count
updated_count
skipped_count
failed_count
error_summary
```

상태:

```text
PENDING
RUNNING
SUCCESS
FAILED
SKIPPED_NO_CHANGE
```

### 보안 규칙

- `error_summary`에 DB URL, 비밀번호, token, 개인정보를 저장하지 마라.
- URL에 query secret이 있으면 제거한 뒤 저장하라.

### 추가 작업

- 새 migration 생성
- Django admin 등록
- 상태별 테스트

### 필수 테스트

1. 실행 시작 시 `RUNNING`
2. 성공 시 `SUCCESS`
3. 실패 시 `FAILED`
4. 동일 checksum이면 `SKIPPED_NO_CHANGE`
5. 건수 필드 저장

---

## 12. 단계 6 — `sync_facilities` 관리 명령 구현

### 목표

기존 수동 Import를 검증 가능한 ETL 동기화 명령으로 확장한다.

### 생성할 파일

```text
fitness/management/commands/sync_facilities.py
```

### 첫 버전에서 지원할 입력

반드시 로컬 파일 입력부터 구현하라.

```bash
python manage.py sync_facilities --source-path facilities.csv
```

공식 URL이 확인된 경우에만 추가한다.

```bash
python manage.py sync_facilities --source-url "공식 URL"
```

공식 URL이 없으면 URL 기능을 억지로 완성하지 말고 명확한 오류 메시지 또는 미구현 상태로 남겨라.

### 처리 순서

1. 중복 실행 방지
2. 파일 읽기
3. SHA-256 checksum 계산
4. 같은 원본인지 확인
5. 필수 컬럼 검증
6. 행별 지역·좌표 검증
7. `transaction.atomic()` 시작
8. source ID 기준 upsert
9. 처리 건수 기록
10. 성공 commit 또는 실패 rollback

### 필수 안전장치

- 빈 파일 거절
- 필수 컬럼 누락 거절
- 좌표 범위 검증
- 미지원 지역 격리 또는 skip
- 원본 행 수 비정상 급감 시 중단
- 실패 시 기존 데이터 유지
- 동일 checksum 재실행 생략
- 정상 성공은 exit code 0
- 실패는 non-zero exit code

### 원본 급감 기준

기존 성공 실행 기록이 있을 때 새 원본이 이전 행 수보다 30% 이상 감소하면 자동 적재하지 말고 실패 처리하라. 단, 명시적인 `--allow-large-drop` 같은 관리자 옵션을 설계할 수 있다.

### 누락 시설 처리

첫 버전에서는 원본에 없는 기존 시설을 바로 삭제하지 마라. 완전한 전체 원본이라는 사실이 확인된 경우에만 `is_active=False` 정책을 별도로 구현하라.

### 필수 테스트

1. 정상 CSV 최초 적재
2. 같은 CSV 재실행
3. 동일 checksum 생략
4. 필수 컬럼 누락
5. 빈 파일
6. 잘못된 좌표
7. 미지원 지역
8. transaction rollback
9. 신규·수정·실패 건수
10. `DataSyncRun` 상태

---

## 13. 단계 7 — 예약 실행 준비

### 목표

수동 동기화가 안정화된 뒤에만 예약 실행 파일을 준비한다.

### 선택 우선순위

1. Render Cron 사용 가능 여부 확인
2. 비용이 어렵다면 GitHub Actions schedule 사용
3. 공식 URL이 없으면 자동 다운로드 Cron을 활성화하지 않음

### GitHub Actions schedule을 만드는 경우

생성 파일:

```text
.github/workflows/facility-sync.yml
```

요구 조건:

- `workflow_dispatch` 제공
- `schedule` 제공
- `concurrency`로 중복 실행 방지
- 운영 secret은 GitHub Environment/Secrets 사용
- Fork PR에서는 실행되지 않음
- 공식 URL이 secret/variable로 제공되지 않으면 실패 메시지 출력

초기 실행 주기:

```cron
20 19 * * SUN
```

이는 매주 월요일 한국시간 04:20이다.

### 중요한 제한

`testsv` 검증 단계에서는 schedule을 바로 활성화하지 말고 `workflow_dispatch`로 수동 실행을 먼저 검증하라. 운영 DB 접근은 사용자 승인 없이 실행하지 마라.

---

## 14. 단계 8 — 크롤링 기술 검증

### 목표

공식 CSV/API에 없는 정보만 소규모로 검증한다.

### 먼저 해야 할 일

1. 필요한 필드를 확정
2. 공식 API 제공 여부 확인
3. robots.txt 확인
4. 이용약관 확인
5. 공식 시설 홈페이지인지 확인

### 허용 범위

- 시설 3~5개
- 공식 홈페이지
- 운영시간·휴관일 후보
- 낮은 요청 빈도
- 결과는 검수 대기 상태로 저장

### 금지 범위

- 검색엔진 전체 순회
- 비공식 사이트 대량 수집
- 로그인 우회
- CAPTCHA 우회
- 개인정보 수집
- 허용 여부 미확인 상태의 대규모 실행
- 검증하지 않은 값을 운영 Facility에 즉시 덮어쓰기

### 구현 요구사항

- 명확한 User-Agent
- connect/read timeout
- 최대 재시도
- 429/5xx backoff
- 도메인별 요청 간격
- 원본 URL과 수집 시각
- parser 실패 감지
- 실패 URL 기록

### 공식 URL 목록이 제공되지 않은 경우

현재 `scrape_facility_hours.py`를 운영용으로 과장하지 말고, 기술 검증 상태와 부족한 점만 문서화하라. 임의 사이트에 자동 요청하지 마라.

---

## 15. 모든 단계 공통 테스트

각 단계 완료 후 다음 명령을 실행하라.

```powershell
$env:USE_SQLITE='1'
$env:DEBUG='True'
$env:SECRET_KEY='testsv-local-check-only'

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test config.test_deployment fitness.test_kakao fitness.test_local_auth fitness.test_logout fitness.test_mascots fitness.test_web_flow -v 1
python manage.py collectstatic --noinput
git diff --check
git status --short
```

### 테스트 결과 기록

다음 문서를 업데이트하라.

```text
docs/NETFIT_TESTSV_PIPELINE_EXECUTION_SCRIPT.md
```

업데이트 항목:

- 단계별 변경 기록표
- 오류 기록표
- 진행 현황판
- 변경 전/후 결과
- commit SHA

---

## 16. 커밋 규칙

하나의 거대한 커밋으로 만들지 마라. 검증 가능한 단위로 나눈다.

권장 커밋:

```text
ci: add Django checks for testsv
deploy: add Render test blueprint
fix: reject unsupported facility regions
data: add facility source identifier
data: add facility sync run history
feat: add validated facility sync command
schedule: prepare manual facility sync workflow
docs: record testsv pipeline verification
```

각 커밋 전에 테스트를 실행하라.

push 권한과 사용자의 요청이 명확한 경우에만 `testsv`에 push하라. `runsv`로 push하거나 merge하지 마라.

---

## 17. 작업 중 사용자에게 질문해야 하는 경우

다음 상황에서만 작업을 멈추고 짧게 질문하라.

1. 기존 중복 시설을 삭제해야 하는 경우
2. 원본 CSV에 안정적인 고유 ID가 없는 경우 정책 결정
3. 미지원 지역을 skip 또는 `미분류` 중 선택해야 하는데 팀 정책이 있는 경우
4. 운영 Supabase 접근이 필요한 경우
5. Render 테스트 서비스 생성 권한이 필요한 경우
6. 공식 시설 데이터 URL이 필요한 경우
7. 크롤링 대상 사이트와 허용 범위가 필요한 경우
8. 비용이 발생하는 Render Cron 생성이 필요한 경우

질문 전까지 할 수 있는 로컬 구현과 테스트는 먼저 완료하라.

---

## 18. 완료 기준

다음 항목을 충족해야 완료로 보고한다.

### 코드 품질

- [ ] Django check 통과
- [ ] migration 누락 없음
- [ ] migration 충돌 없음
- [ ] 백엔드 자동 테스트 통과
- [ ] collectstatic 통과
- [ ] secret 미포함

### CI/CD 준비

- [ ] GitHub Actions CI 생성
- [ ] `testsv` 기준 Render Blueprint 생성
- [ ] 운영 서비스 자동 변경 없음
- [ ] `/healthz/` 사용

### ETL

- [ ] 서울 fallback 제거
- [ ] 시설 고유 ID 또는 안정적인 대체 키
- [ ] DB 중복 제약
- [ ] `DataSyncRun` 실행 이력
- [ ] `sync_facilities` 로컬 파일 동기화
- [ ] 동일 원본 재실행 안전
- [ ] 잘못된 원본 rollback

### 예약 실행·크롤링

- [ ] 수동 예약 workflow 준비 또는 미구현 이유 기록
- [ ] 공식 URL 미확정 시 자동 schedule 비활성
- [ ] 크롤링 허용 범위 미확정 시 대량 요청 없음

### 문서

- [ ] 변경 전/후 기록
- [ ] 테스트 결과
- [ ] 오류와 해결 방법
- [ ] commit SHA
- [ ] `runsv` 병합 가능 여부

---

## 19. 최종 보고 형식

작업이 끝나면 다음 형식으로 보고하라.

```markdown
# testsv 작업 결과

## 전체 결과
- 완료 / 부분 완료 / 차단

## 기준 정보
- 시작 commit:
- 종료 commit:
- 작업 브랜치:

## 구현 완료
- 항목
- 항목

## 변경 전 → 변경 후
| 영역 | 변경 전 | 변경 후 |
|---|---|---|
| CI | 없음 | GitHub Actions 검사 |
| 시설 지역 | 미지원 지역 서울 저장 가능 | 잘못된 지역 차단 |
| 중복 | 이름+주소 | source ID + DB 제약 |
| 동기화 | 수동 Import | 검증형 sync 명령 |

## 변경 파일
- 파일명: 변경 내용

## 테스트
- Django check:
- Migration check:
- 자동 테스트 수와 결과:
- Collectstatic:

## 미완료·차단
- 항목:
- 필요한 사용자 결정:

## 보안 확인
- secret 커밋 없음
- 운영 DB 변경 없음
- runsv 변경 없음

## runsv 병합 판단
- 가능 / 불가능
- 이유:
- 병합 전에 필요한 작업:
```

## 마지막 지시

지금부터 단계 0부터 시작하라. 저장소를 직접 확인하고 근거에 따라 작업하라. 설명만 작성하고 멈추지 말고, 안전한 범위에서 구현·테스트·문서 업데이트까지 수행하라. 운영 `runsv`와 운영 Supabase는 변경하지 마라.

# GPT 전달용 프롬프트 끝

