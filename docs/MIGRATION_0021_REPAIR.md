# 0021 배포 지연 완화

기준: origin/runsv 1676c9e. 운영 DB 접근·배포는 수행하지 않음.

## 수정

- 시설별 save 대신 최대 500개씩 bulk_update.
- PK 기반 페이지 조회로 장시간 서버 커서 사용 회피.
- 현재 migration의 DB alias 사용.
- 처리 건수 로그를 즉시 출력. 로그의 commit pending은 migration 전체가 아직 커밋되지 않았다는 의미.
- 기존 atomic migration 및 기존 ID 생성 규칙 유지. 기존 중복 행 삭제 없음.
- CI에 501개 행/배치 경계 중복/unique 적용 회귀 테스트 추가.

## 제한과 배포 조건

0021이 이미 적용된 DB에서는 이 파일 변경으로 재실행되지 않는다.
후속 0023에서 이름/주소와 일치하는 구형 키만 현재 CSV sync 키 형식으로 보정한다.
0021이 이미 적용된 DB도 0023으로 보정된다. 외부 원본 ID와 legacy 중복 키는 보존한다.
목표 키가 이미 존재하면 두 행 모두 보존하고 충돌 수를 로그에 기록한다.
기존 의미상 중복 행을 자동 병합/삭제하지 않으며, 해당 정리는 별도 검토 대상이다.
CSV 재적재 및 재실행 시 신규 중복 생성 방지, 외부 ID 보존, 충돌 보존을 테스트했다.

운영 DB의 0021 실행·적용 상태와 백업을 확인한 뒤 배포한다.
기존 migration 작업이 실행 중인 상태에서 중복 실행하지 않는다.
일괄 저장은 왕복 쿼리를 줄이지만 DB lock, 연결 장애, Render 시간 제한 문제의 해결을 보장하지 않는다.
--fake, migration 삭제, 실패를 무시하고 서버를 실행하는 변경은 하지 않는다.

Start Command는 migrate --noinput 뒤에 && gunicorn 명령을 유지한다.
성공 증거는 0021/0022 OK, Gunicorn Listening, 최신 커밋의 Live이다.

## 로컬 검증 (2026-09-23)

- SQLite 격리 테스트 72개 통과 (25.198초).
- makemigrations --check --dry-run: No changes detected.
- collectstatic: 151개 수집 (로컬 검증용 SECRET_KEY 사용).
- git diff --check: 통과.
- 운영 PostgreSQL 실행 시간과 적용 여부는 원격 배포 로그로 별도 확인 필요.
- 기존 CI 실패 원인인 수요일 러닝/수영 미션 제목의 종목명 누락도 수정.
