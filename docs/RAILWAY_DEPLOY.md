# NetFit tigger · Railway 배포

대상: `pes9476/netfit` 저장소의 `netfit_tigger` 브랜치.
Railway의 Source Branch를 이 브랜치로 선택하면 됩니다. `main`으로 통합할 경우에는
일반 merge로 이 브랜치의 기능과 배포 설정을 함께 반영한 뒤 Source Branch를 변경합니다.

## 1. Railway 서비스 연결

기존 NetFit 서비스의 Settings → Source에서 GitHub 저장소와 `netfit_tigger`를 선택합니다.
새 서비스라면 Deploy from GitHub repo로 연결합니다. Root Directory는 저장소 루트입니다.
Config File은 `/railway.json`입니다. 이 파일이 빌드·시작·헬스체크를 정의합니다.
이전에 대시보드에서 설정한 별도 패키지 설치 명령이 있다면 기본 설치로 되돌리세요.

- Python: `.python-version`의 3.13
- 설치: `requirements.txt` (PostgreSQL 드라이버는 psycopg3)
- 빌드: `python manage.py collectstatic --noinput`
- 배포 직전: `python manage.py migrate --noinput`
- 실행: Gunicorn, Railway가 제공하는 `$PORT` 사용
- 상태 확인: `/healthz/`에서 DB 연결까지 확인, 정상 200 / DB 오류 503

첨부 가이드의 `psycopg2-binary==2.9.9`와 `Procfile`의 `release:` 항목은 사용하지 않습니다.
마이그레이션은 Railway의 `preDeployCommand`로 명시했습니다.

## 2. 환경 변수

첫 빌드 전에 Variables에 입력합니다. 예시 비밀번호를 실제 값으로 오해하지 마세요.

| 이름 | 값 |
| --- | --- |
| `DEBUG` | `False` |
| `SECRET_KEY` | 별도로 생성한 임의의 비밀 문자열 |
| `DATABASE_URL` | Supabase 또는 Railway PostgreSQL 연결 URI |
| `MEDIA_ROOT` | `/data/media` |
| `PYTHONUNBUFFERED` | `1` |

`SECRET_KEY` 생성 예: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
실제 비밀값은 Railway Variables에만 저장하고 Git에 커밋하지 않습니다.

Settings → Networking에서 Public Domain을 생성합니다.
Railway의 `RAILWAY_PUBLIC_DOMAIN`으로 호스트, CSRF origin, 카카오 callback 기본 주소가 자동 설정됩니다.
직접 연결한 별도 도메인은 `ALLOWED_HOSTS`에 호스트를,
`CSRF_TRUSTED_ORIGINS`에 `https://`를 포함한 origin을 쉼표로 구분해 추가합니다.

Railway에서는 PostgreSQL 연결 정보가 없거나 `USE_SQLITE=1`이면 시작을 중단합니다.
일시적 컨테이너 디스크에 사용자 DB가 저장되는 것을 막기 위한 설정입니다.
로컬은 `.env.example`을 `.env`로 복사해 `DEBUG=True`로 실행하면 SQLite를 사용할 수 있습니다.

### Supabase

Supabase 프로젝트의 Connect에서 실제 URI를 복사합니다.
IPv4 연결이 필요한 환경에서는 Session pooler(일반적으로 5432)를 선택합니다.
URI에 `sslmode=require`를 지정하고 비밀번호의 특수문자는 URL 인코딩합니다.
Transaction pooler를 사용하는 경우에도 psycopg의 prepared statements와 서버 측 커서는
이 설정에서 비활성화됩니다. 다른 곳의 예시 호스트를 그대로 붙여 넣지 마세요.

### Railway PostgreSQL

기존 PostgreSQL 서비스의 `DATABASE_URL`을 웹 서비스 Variables에 reference로 연결합니다.
서비스 이름에 맞는 Railway 변수 참조를 사용하세요. SSL 지원 여부는 해당 DB 연결 설정에 따릅니다.

## 3. 인증 사진의 영구 저장

웹 서비스에 Railway Volume을 추가하고 Mount Path를 `/data`로 설정합니다.
`MEDIA_ROOT=/data/media`와 함께 사용해야 재배포 후에도 사진이 남습니다.
현재 구성은 단일 서비스 인스턴스와 연결된 볼륨을 전제로 합니다.
사진은 로그인한 사용자에게 업로드 폴더 안의 이미지로만 제공됩니다.
파일별 소유자 권한 검사는 기존 서비스 기능과 별도로 추가할 수 있습니다.

기존 PC의 사진은 자동 복사되지 않습니다. `media/` 안의 상대 경로를 유지하여
볼륨의 `/data/media/`로 옮겨야 DB에 저장된 파일명과 맞습니다.
이전 코드가 참조하던 프로젝트 루트의 `quest_proofs/`, `workout_proofs/`도
해당 사진이 있으면 새 `MEDIA_ROOT` 아래의 같은 폴더로 옮깁니다.

## 4. 카카오 로그인

`KAKAO_REST_API_KEY`, 필요 시 `KAKAO_CLIENT_SECRET`을 Variables에 설정합니다.
카카오 개발자 콘솔에 아래 주소를 Redirect URI로 등록합니다.

```text
https://실제-Railway-도메인/login/kakao/callback/
```

커스텀 도메인으로 로그인한다면 `KAKAO_REDIRECT_URI`도 해당 HTTPS 주소로 지정합니다.
로컬 `kakao.local.json`은 Git에서 제외되어 Railway로 업로드되지 않습니다.

## 5. 스키마와 기존 데이터

배포 전 명령은 `0016`까지 포함한 DB 테이블 구조를 적용합니다.
로컬 `db.sqlite3`의 회원·운동 기록을 PostgreSQL로 복사하는 작업은 별개입니다.
사용 중인 서버 데이터에 로컬 데이터를 덮어쓰지 마세요.
기존 데이터를 옮겨야 한다면 원본/대상 DB를 백업하고, 빈 대상 DB를 전제로
별도 데이터 이관을 진행합니다. 이번 배포 설정 작업은 사용자 데이터를 옮기지 않습니다.

시설 목록이 빈 DB라면 배포된 환경의 shell에서 한 번 실행합니다.

```bash
python manage.py import_facilities facilities.csv
python manage.py createsuperuser
```

`migrate`는 시설 CSV를 자동으로 불러오지 않습니다.

## 6. 확인 순서

1. 빌드 로그에서 의존성 설치와 `collectstatic` 성공을 확인합니다.
2. Pre-deploy에서 마이그레이션 성공을 확인합니다.
3. `/healthz/`가 `{"status":"ok"}`를 반환하는지 확인합니다.
4. 첫 화면·로그인·회원가입·정적 이미지가 정상인지 확인합니다.
5. 운동·퀘스트 기록과 사진 업로드를 확인합니다.
6. 재배포 후 DB 기록과 사진이 유지되는지 확인합니다.

`DisallowedHost`는 실제 호스트 설정, CSRF 오류는 HTTPS origin,
DB 연결 오류는 URI·비밀번호·연결 방식, 사진 소실은 볼륨 연결을 확인합니다.
빌드 로그에 `psycopg2-binary==2.9.9`가 다시 보이면 Source Branch/배포 커밋 또는
설치 명령이 다른 요구사항 파일을 사용하는지 확인합니다.

## 공식 참고 자료

- [Railway config as code](https://docs.railway.com/config-as-code/reference)
- [Railpack Python](https://railpack.com/languages/python/)
- [WhiteNoise Django 설정](https://whitenoise.readthedocs.io/en/stable/django.html)
- [Supabase 연결 방식](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase prepared statements](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL)
