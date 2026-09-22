# NETFIT testsv 파이프라인 실행 기록

확인일: 2026-09-22 (Asia/Seoul)

## 진행 현황판

| 단계 | 결과 | 근거 |
|---|---|---|
| 0. 기준 상태 | 완료 | `testsv`, 시작 `56a445e`, 작업 트리 clean |
| 1. GitHub Actions CI | 완료 | `.github/workflows/ci.yml` |
| 2. Render 테스트 설정 | 완료 | `render.yaml`, Render 환경 감지 테스트 |
| 3. 지역 오류 수정 | 완료 | 미지원 지역 skip 및 오류 집계 |
| 4. 시설 식별자 | 완료 | 명시 ID 우선, 없으면 SHA-256 대체 키, DB unique |
| 5. 실행 이력 | 완료 | `DataSyncRun`, admin, 상태·건수·오류 기록 |
| 6. `sync_facilities` | 완료 | 로컬 파일 검증형 ETL 및 rollback |
| 7. 예약 실행 준비 | 부분 완료 | 수동 workflow만 준비, 자동 schedule은 보류 |
| 8. 크롤링 검증 | 보류 | 공식 URL·robots.txt·이용약관 범위 미확정 |

## 기준 정보

- 저장소: `https://github.com/pes9476/netfit`
- 작업 브랜치: `testsv`
- 시작 commit: `56a445e`
- 구현 종료 commit: `288e98d` (이 문서 커밋 제외)
- 운영 `runsv`, Render `netfit-production`, 운영 Supabase 변경: 없음

## 변경 전 상태

- Django `check`: 통과
- `makemigrations --check --dry-run`: 변경 없음
- 첫 테스트 실행: 로컬 의존성 `whitenoise` 누락으로 실패
- `pip install -r requirements.txt` 후 기존 53개 테스트: 통과
- 시설 적재는 미지원 지역을 `서울특별시`로 저장할 수 있었음
- 시설 원본 식별자, DB 중복 제약, 동기화 이력과 검증형 동기화 명령이 없었음
- CI 및 Render testsv Blueprint가 없었음

## 단계별 변경 기록

### 단계 1 — CI

- push: `testsv`, `runsv`, `netfit_giuk`
- pull request: `testsv`, `runsv`
- SQLite 강제 사용, Django check, migration 누락 검사, 백엔드 70개 테스트,
  collectstatic 실행
- 공식 최신 안정 major인 `actions/checkout@v7`, `actions/setup-python@v7` 사용
- Selenium과 운영 secret은 포함하지 않음

### 단계 2 — Render 테스트 설정

- 서비스 이름 `netfit-test`, 브랜치 `testsv`, 무료 플랜으로 Blueprint 작성
- `DATABASE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`는 `sync: false`
- `RENDER`, `RENDER_EXTERNAL_HOSTNAME` 감지와 HTTPS·secure cookie 기본값 구현
- 배포 환경에서 SQLite 사용 또는 PostgreSQL 설정 누락 시 시작을 차단
- 운영 Render 서비스는 생성·수정하지 않음

### 단계 3 — 지역 오류

- 미지원 지역의 서울 fallback 제거
- 미지원·누락 지역은 해당 행만 제외하고 실패 건수와 행 번호 기록
- 삭제 표시(`DEL_AT=Y`) 행은 저장하지 않음
- 정상 행은 오류 행과 독립적으로 저장

### 단계 4 — 시설 식별자와 원본 분석

체크인된 `facilities.csv` 분석 결과:

| 항목 | 결과 |
|---|---:|
| 전체 행 | 44,612 |
| 활성 행 | 35,573 |
| 삭제 표시 행 | 9,039 |
| 시설명 누락 | 0 |
| 주소 누락 | 7,585 (활성 행의 21.3%) |
| 명시적 시설 고유 ID 컬럼 | 없음 |
| 정규화 시설명+주소 중복 그룹 | 270 |
| 중복 그룹 포함 행 | 699 |

- 향후 원본에 `SOURCE_RECORD_ID`, `FCLTY_ID`, `FCLTY_NO`가 있으면 해당 ID를 우선 사용
- 현재 원본은 NFKC·공백·대소문자를 정규화한 시설명+주소의 SHA-256 사용
- 기존 행은 data migration으로 backfill
- 기존 중복 행은 삭제하지 않고 legacy 식별자로 보존
- `source_record_id`에 DB unique constraint 적용

### 단계 5 — 실행 이력

`DataSyncRun`에 다음을 기록한다.

- 상태: `PENDING`, `RUNNING`, `SUCCESS`, `FAILED`, `SKIPPED_NO_CHANGE`
- 원본 이름·정제된 URL·SHA-256 checksum
- 시작·종료 시각
- 원본·생성·수정·제외·실패 건수
- 민감한 URL 자격 증명과 token을 제거한 오류 요약
- 같은 원본 이름의 `RUNNING` 상태를 DB 제약으로 하나만 허용

### 단계 6 — 시설 동기화

```powershell
python manage.py sync_facilities --source-path facilities.csv
```

구현된 안전장치:

- 빈 파일 및 필수 컬럼 누락 거절
- UTF-8 검증
- 지역 및 위·경도 범위 검증
- 명시 ID 또는 SHA-256 기준 upsert
- 동일 checksum 재실행 생략
- 직전 성공 원본보다 30% 이상 감소하면 중단
- `--allow-large-drop`으로 명시적 예외 가능
- DB 저장 오류 시 전체 시설 변경 rollback
- 원본에서 빠진 기존 시설은 삭제하거나 비활성화하지 않음
- 공식 URL 미확정 상태에서 `--source-url` 사용 시 명확하게 실패

실제 체크인 CSV를 로컬 SQLite에서 실행한 결과:

| 생성 | 수정·중복 통합 | 삭제 표시 제외 | 실패 |
|---:|---:|---:|---:|
| 35,144 | 429 | 9,039 | 0 |

같은 파일을 다시 실행했을 때 `SKIPPED_NO_CHANGE`로 종료됐다.

### 단계 7 — 예약 실행

- `.github/workflows/facility-sync.yml`에 `workflow_dispatch`와 `concurrency` 구현
- 격리된 GitHub Environment `testsv`의 `TEST_DATABASE_URL`만 사용
- secret이 없으면 실행 전에 실패
- 공식 다운로드 URL과 수동 검증이 없으므로 `schedule`은 활성화하지 않음
- 운영 Supabase에서는 실행하지 않음

### 단계 8 — 크롤링

현재 `scrape_facility_hours.py`는 단일 URL의 제목과 키워드를 확인하는 기술 예시다.
공식 시설 URL 목록, robots.txt, 이용약관, 필요한 필드가 확정되지 않아 요청을 실행하거나
운영 데이터에 저장하는 기능은 추가하지 않았다.

## 오류 기록

| 단계 | 오류 | 원인 | 해결 |
|---|---|---|---|
| 기준 테스트 | 다수 테스트 연쇄 오류 | 로컬 `whitenoise` 미설치 | requirements 설치 후 재실행 |
| 원본 조사 | 고유 ID 없음 | CSV에 시설 레코드 ID 미제공 | 명시 ID 우선 + 정규화 hash fallback |
| 예약 실행 | 공식 URL 없음 | 다운로드 원본 미확정 | 수동 로컬 파일 workflow만 준비 |

## 최종 로컬 검증

```text
Django check: 통과 (0 issues)
Migration check: 통과 (No changes detected)
Backend tests: 70개 통과
Collectstatic: 151개 파일 수집
git diff --check: 통과
```

## 변경 전 → 변경 후

| 영역 | 변경 전 | 변경 후 |
|---|---|---|
| CI | 없음 | push/PR Django 자동 검사 |
| Render | 대시보드 수동 설정 | secret 없는 testsv Blueprint |
| 시설 지역 | 미지원 지역이 서울로 저장될 수 있음 | 잘못된 지역 제외·집계 |
| 중복 | 이름+주소 `update_or_create` | source ID + DB unique constraint |
| 실행 이력 | 없음 | 상태·checksum·건수·오류 기록 |
| 동기화 | 수동 import | 검증·upsert·rollback `sync_facilities` |
| 예약 | 없음 | 격리 DB용 수동 workflow |

## runsv 병합 판단

로컬 기준으로는 병합 후보 상태다. 다음 조건을 모두 확인한 뒤 병합한다.

1. `testsv` push 후 GitHub Actions CI 통과
2. 운영 DB 백업 또는 복구 지점 확인
3. migration `0020`~`0022`의 기존 Facility backfill 결과 검토
4. 기존 중복 시설은 자동 삭제되지 않는다는 정책 확인

공식 데이터 URL, 자동 schedule, 크롤링은 이번 병합의 완료 조건에 포함하지 않는다.
