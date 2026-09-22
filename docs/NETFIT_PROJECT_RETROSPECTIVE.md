# 본인이름의 NetFit 프로젝트 회고록

## 프로젝트 정보

| 항목 | 내용 |
|---|---|
| 팀명 | NetFit (KSPO 공공데이터 경진대회) |
| 담당자 | 본인이름 |
| 프로젝트 시작 기록 | 2026-09-14 |
| 회고 작성 기준일 | 2026-09-21 |
| 완성 예정일 | 2026-09-25 |
| GitHub | <https://github.com/pes9476/netfit> |
| 주요 기술 | Python, Django 5, PostgreSQL, Supabase, Railway, HTML/CSS/JavaScript, Kakao OAuth |

> 이 문서는 팀 대화, Git 커밋 이력, 현재 코드와 백엔드 점검 문서를 기준으로 작성했다. 커밋이 없었던 날짜도 빠뜨리지 않고 당시 점검·정리 상태를 기록했다. 2026-09-22부터 09-25까지는 아직 수행 결과가 아니라 완성일까지의 계획이다.

---

## 2026-09-14 — 프로젝트 시작과 Django 기본 구조 구성

### 당시 상황 & 배경

NetFit은 사용자의 운동 습관을 미션, 캐릭터 성장, 친구와 파티 기능으로 연결하는 서비스로 기획되었다. KSPO 공공데이터 경진대회 출품을 목표로 하므로 단순 화면 시제품이 아니라 계정, 운동 기록, 공공체육시설 데이터가 서로 연결되는 웹 애플리케이션 구조가 필요했다.

### 무엇을 하려고 했는가?

- Django 프로젝트의 기본 실행 구조를 만든다.
- 이후 회원, 운동 기록, 시설, 미션 기능을 추가할 수 있는 단일 애플리케이션을 준비한다.
- 로컬에서 빠르게 개발하고 추후 PostgreSQL 운영 환경으로 이전할 수 있게 한다.

### 왜 필요했는가?

사용자별 데이터와 권한을 안정적으로 관리하려면 URL, View, Model, Template이 분리된 서버 프레임워크가 필요했다. Django는 기본 인증, ORM, CSRF 방어, 마이그레이션을 함께 제공하므로 짧은 대회 일정에 적합했다.

### 실제 구현 과정

1. Django 프로젝트 `config`와 애플리케이션 `fitness`를 구성했다.
2. `manage.py`, 설정, URL 라우팅, WSGI 진입점을 만들었다.
3. 초기 화면과 정적 리소스를 연결할 수 있는 디렉터리 구조를 준비했다.
4. 로컬 개발 단계에서는 SQLite로 즉시 실행할 수 있도록 기반을 잡았다.

### 사용 기술/도구

- Python, Django
- Django ORM과 migration
- Git/GitHub
- SQLite(초기 로컬 개발 DB)

### 발생한 문제

초기 단계라 기능 오류보다 구조 결정이 핵심 과제였다. 개발 속도를 위해 SQLite를 사용하되, 최종 배포는 PostgreSQL/Supabase를 사용할 예정이어서 DB 설정을 한 환경에 고정하면 이후 이전 비용이 커질 수 있었다.

### 해결 방법

Django ORM을 중심으로 모델을 작성해 DB 엔진 의존성을 낮추고, 환경변수에 따라 SQLite와 PostgreSQL을 선택할 수 있는 방향을 잡았다. 직접 SQL 위주로 구현하는 방법은 초기 속도는 빠를 수 있지만 DB 전환과 테스트 격리가 어려워 채택하지 않았다.

### 작동 원리 & 기술 설명

```text
브라우저 요청
  → config/urls.py
  → fitness/urls.py
  → fitness/views.py
  → Django ORM
  → DB
  → Template 렌더링
  → HTML 응답
```

Django migration은 모델 변경 내용을 버전 파일로 저장하고, `migrate` 명령으로 실제 DB 스키마에 순서대로 반영한다.

### 코드/파일

- `manage.py`
- `config/settings.py`
- `config/urls.py`
- `config/wsgi.py`
- `fitness/apps.py`
- `fitness/views.py`
- `fitness/models.py`

### 완료 상태

**완료** — Git 기록 `e886d6f Initial Django project`

---

## 2026-09-15 — UI 테마, 계정 데이터 모델, 온보딩과 미션 기반 기능 구성

### 당시 상황 & 배경

기본 프로젝트만으로는 서비스 흐름을 시연할 수 없었다. 회원가입 후 사용자가 자신의 신체 정보와 지역을 입력하고, 솔로 또는 파티 모드를 선택한 뒤 운동 미션으로 이동하는 전체 사용자 흐름이 필요했다.

### 무엇을 하려고 했는가?

- NetFit 전용 화면 테마와 캐릭터 UI를 적용한다.
- Django 기본 계정과 사용자 프로필을 연결한다.
- PostgreSQL 연결 기반을 추가한다.
- 온보딩, 솔로·파티 미션, 주변 체육시설 화면을 구현한다.

### 왜 필요했는가?

계정 정보만으로는 지역 랭킹, 맞춤 운동, 인바디 기반 캐릭터 표현을 만들 수 없다. 사용자 계정과 서비스 데이터를 분리하면서도 1:1로 연결할 프로필 구조가 필요했다.

### 실제 구현 과정

1. NetFit 테마, 캐릭터 선택, 로그인 선택 화면을 구성했다.
2. Django `User`와 연결되는 `Profile`, `CharacterCard` 등 핵심 모델을 추가했다.
3. PostgreSQL 설정과 모델별 초기 migration을 작성했다.
4. 온보딩 화면을 소개 → 프로필 → 코스 → 모드 → 솔로/그룹 순서로 분리했다.
5. 공공체육시설 목록을 검색하고 추천할 화면과 데이터 모델을 마련했다.
6. 사용자 생성 시 signal을 통해 프로필과 캐릭터 카드가 함께 만들어지도록 연결했다.

### 사용 기술/도구

- Django built-in authentication
- Django ORM 관계(`OneToOneField`, `ForeignKey`, `ManyToManyField`)
- PostgreSQL
- Django signal
- HTML/CSS/JavaScript

### 발생한 문제

- 계정 정보, 프로필, 캐릭터, 친구 관계가 한 모델에 섞이면 유지보수가 어려웠다.
- 온보딩 도중 사용자가 페이지를 이탈하거나 입력을 누락할 경우 대시보드에서 필요한 값이 없을 수 있었다.
- 개발 DB와 운영 DB의 연결 방식이 달라질 가능성이 있었다.

### 해결 방법

- 인증은 Django `User`, 서비스 정보는 `Profile`, 성장 정보는 `CharacterCard`로 분리했다.
- 온보딩 완료 여부를 프로필에 저장해 로그인 후 이동 경로를 제어했다.
- DB 접속 정보는 코드에 직접 적지 않고 환경변수로 분리하는 구조를 선택했다.

하나의 사용자 모델에 모든 필드를 추가하는 방법은 빠르지만 인증과 도메인 데이터가 강하게 결합되고, Django 기본 인증의 장점을 잃을 수 있어 사용하지 않았다.

### 작동 원리 & 기술 설명

```text
User 생성
  └─ signal
      ├─ Profile 생성: 지역, 신체 정보, 운동 모드
      └─ CharacterCard 생성: 레벨, XP, 카드 상태

로그인
  ├─ onboarding 미완료 → 온보딩 화면
  └─ onboarding 완료 → 대시보드
```

### 코드/파일

- `fitness/models.py`
- `fitness/signals.py`
- `fitness/forms.py`
- `fitness/views.py`
- `fitness/templates/fitness/login.html`
- `fitness/templates/fitness/register.html`
- `fitness/templates/fitness/onboarding_*.html`
- `fitness/templates/fitness/facilities.html`
- `fitness/migrations/0001_initial.py` 이후 초기 migration

### 완료 상태

**완료** — Git 기록 `3dcc8d3`, `99f204c`, `9365c9c`

---

## 2026-09-16 — 배지·캐릭터 성장·대시보드와 시설 추천 개선

### 당시 상황 & 배경

온보딩 이후 사용자가 지속적으로 운동할 동기가 필요했다. 운동 기록을 단순 저장하는 것을 넘어 배지, 캐릭터 성장, 의상, 랭킹으로 연결하는 게임화 기능을 추가했다. 동시에 주변 시설 추천에서 지역 또는 GPS 정보를 제대로 얻지 못하는 사례를 점검했다.

### 무엇을 하려고 했는가?

- 운동시간에 따른 배지와 점수 체계를 만든다.
- 캐릭터 레벨·경험치·의상 기능을 구성한다.
- 대시보드에 운동·날씨·미션 정보를 모은다.
- 사용자 지역과 현재 위치를 이용해 가까운 공공체육시설을 추천한다.

### 왜 필요했는가?

NetFit의 핵심 가치는 운동 기록을 눈에 보이는 보상과 경쟁 요소로 전환하는 것이다. 또한 KSPO 공공데이터를 실제 사용자 위치와 연결해야 공공데이터 활용 목적이 명확해진다.

### 실제 구현 과정

1. `WorkoutRecord`, `BadgeAward`, `OutfitPurchase` 관련 기능을 연결했다.
2. 운동시간 30분·60분·90분을 동·은·금 배지 기준으로 설계했다.
3. 레벨, 현재 XP, 다음 레벨 필요 XP 계산 기능을 `CharacterCard`에 구성했다.
4. 사용자 나이·성별·체형에 따른 캐릭터 미리보기와 의상 장착 화면을 추가했다.
5. 날씨 API와 지역 대표 좌표를 이용한 fallback을 구현했다.
6. 시설 검색에 카테고리, 검색어, 위치 기반 거리 정렬을 연결했다.

### 사용 기술/도구

- Django ORM 집계
- JavaScript Geolocation API
- Open-Meteo 날씨 API
- Nominatim/BigDataCloud 역지오코딩
- Haversine 방식의 거리 계산
- NumPy 기반 능력치 계산

### 발생한 문제

#### 주변 시설에서 지역 데이터가 보이지 않는 문제

증상은 GPS 권한이 없거나 브라우저 위치 획득에 실패했을 때 추천 목록이 비거나 사용자 지역과 다른 결과가 표시되는 것이었다.

원인은 다음 가능성으로 나뉘었다.

- 브라우저가 위치 권한을 거부함
- HTTPS가 아닌 환경에서 위치 API 제약 발생
- `Profile.area` 값과 시설 CSV의 행정구역 표기가 다름
- 좌표가 없을 때 사용할 대표 좌표가 누락됨

#### 레벨과 랭킹 기준 혼동

화면에 레벨이 표시되어 레벨이 높은 순서로 랭킹이 정해지는 것처럼 보였지만, 실제 랭킹은 `BadgeAward.points` 누적 합계를 기준으로 정렬했다. XP 계산 함수는 존재했으나 모든 운동·미션 완료 경로에 연결된 상태는 아니었다.

### 해결 방법

- GPS 성공 시 실제 좌표로 시설 거리를 계산했다.
- GPS 실패 시 사용자의 프로필 지역 대표 좌표를 fallback으로 사용했다.
- 랭킹 설명을 ‘레벨 순’이 아니라 ‘누적 배지 점수 순’으로 정리했다.
- XP 저장 모델과 계산 함수의 존재 여부, 실제 지급 연결 여부를 체크리스트에서 분리했다.

외부 지도 API 하나에만 의존하는 방식은 API 장애나 키 설정 실패 시 전체 추천이 중단되므로 사용하지 않았다. 좌표가 없을 때 결과를 완전히 숨기는 대신 지역 기반 fallback을 선택했다.

### 작동 원리 & 기술 설명

```text
주변 시설 추천
  ├─ GPS 좌표 있음 → 각 시설까지 거리 계산 → 가까운 순 정렬
  └─ GPS 좌표 없음 → Profile.area 대표 좌표 → 거리 계산

랭킹
  → 대상 사용자 필터(지역/파티/친구)
  → BadgeAward.points 합계
  → 합계 내림차순 정렬
  → 레벨과 점수를 함께 표시
```

### 코드/파일

- `fitness/models.py`
- `fitness/views.py`
- `fitness/services.py`
- `fitness/templates/fitness/dashboard.html`
- `fitness/templates/fitness/facilities.html`
- `fitness/templates/fitness/ranking.html`
- `fitness/templates/fitness/outfit_shop.html`
- `fitness/static/fitness/js/avatar.js`
- `fitness/migrations/0009_*` ~ `0011_*`

### 완료 상태

**부분 완료** — 배지·대시보드·시설 추천은 구현됐으나 XP 지급 경로 연결과 운영 환경 위치 권한 검증은 추가 작업이 필요하다.

---

## 2026-09-17 — 팀 브랜치 분업과 백엔드·프론트엔드 통합 준비

### 당시 상황 & 배경

팀 작업이 `backend`, `netfit_tigger`, 개인 작업 브랜치로 나뉘었다. 한 팀원은 백엔드를, 다른 팀원은 대시보드와 사용자 화면을 수정하고 있었기 때문에 단순 파일 복사보다 Git 병합을 통해 이력을 유지해야 했다.

### 무엇을 하려고 했는가?

- 팀원이 수정한 코드를 각 브랜치에 기록한다.
- 스포츠 뉴스, 로그아웃 팝업, 화면 문구 등 UI 개선을 반영한다.
- 다음 날 통합할 수 있도록 브랜치별 작업 이력을 보존한다.

### 왜 필요했는가?

동일한 `views.py`, `models.py`, 대시보드 템플릿을 여러 사람이 동시에 수정하면 충돌이 발생한다. 작업 단위를 커밋으로 구분해야 어느 기능이 어디서 들어왔는지 추적하고 문제가 생겼을 때 원인을 찾을 수 있다.

### 실제 구현 과정

1. 백엔드 작업을 `backend` 브랜치에 커밋했다.
2. 팀원 작업을 `netfit_tigger` 브랜치에 커밋했다.
3. 스포츠 뉴스 롤링 애니메이션과 로그아웃 확인 팝업을 추가했다.
4. UI 문구와 날짜 표시를 개선했다.
5. 다음 통합 시 커밋 계보를 유지할 준비를 했다.

### 사용 기술/도구

- Git branch, commit, merge
- Django Template
- JavaScript `setInterval`
- CSS animation

### 발생한 문제

팀원이 만든 계정이 코드를 pull한 뒤 로컬에서 보이지 않는 혼동이 있었다. Git에는 소스코드와 migration은 저장되지만, Supabase나 로컬 DB에 생성된 사용자 행은 Git 커밋 대상이 아니다.

### 해결 방법

코드 동기화와 DB 데이터 동기화를 분리해서 이해했다.

```text
git pull로 가져오는 것: Python, HTML, CSS, migration 파일
git pull로 가져오지 못하는 것: 회원 계정, 운동 기록, 운영 DB 행
```

같은 계정을 확인하려면 두 실행 환경이 동일한 `DATABASE_URL`을 사용해야 한다. DB 덤프를 Git에 올리는 방법은 개인정보와 비밀번호 노출 위험이 있어 사용하지 않았다.

### 작동 원리 & 기술 설명

Git branch는 코드 이력을 분리한다. DB는 Git과 별개의 상태 저장소이므로, 동일한 코드를 실행하더라도 연결된 DB가 다르면 계정과 기록도 다르게 보인다.

### 코드/파일

- `fitness/templates/fitness/dashboard.html`
- `fitness/templates/fitness/logout_modal.html`
- `fitness/templates/fitness/base.html`
- Git 브랜치: `backend`, `netfit_tigger`

### 완료 상태

**완료** — Git 기록 `fdd1c3a`, `4de8d1f`, `21ca484`, `8bd14e2`

---

## 2026-09-18 — 통합 디버깅, 데이터 무결성 강화, 발표 점검

### 당시 상황 & 배경

1차 웹 구현 결과를 실제 사용자 흐름으로 점검하면서 여러 개선 요청이 나왔다.

- 운동시간 선택: 30분, 60분, 90분, 직접 입력
- 미션 완료 시 최근 운동 기록 자동 생성
- 배지 자동 지급과 중복 방지
- 솔로·파티 사진 인증
- 전국랭킹을 지역랭킹으로 표현
- 친구 요청과 파티 초대의 수락·거절
- 파티 참여자 진행 현황
- 프로필·인바디를 마이페이지로 변경

이 항목 중 문구와 배치는 프론트엔드, 데이터와 권한은 백엔드, 타이머·사진·모니터링은 공동 작업으로 역할을 구분할 필요가 있었다.

### 무엇을 하려고 했는가?

- 팀원 코드를 개인 통합 브랜치에 병합한다.
- 미션 완료, 운동 기록, 배지 지급을 하나의 안전한 처리로 만든다.
- 친구 요청과 파티 초대를 상대방 동의 방식으로 변경한다.
- 지역 데이터 표기를 통합한다.
- 인증사진을 검증한다.
- 발표 자료에 사용할 근거와 테스트 결과를 기록한다.

### 왜 필요했는가?

화면만 정상적으로 보이는 것과 데이터가 정확한 것은 다르다. 중복 클릭, 새로고침, 권한 없는 요청, 동시에 들어오는 수락 요청까지 고려하지 않으면 운동 기록·배지·친구·파티 데이터가 쉽게 중복되거나 잘못 연결될 수 있었다.

### 실제 구현 과정

#### 1. 팀 브랜치 병합

1. 원격 `netfit_tigger` 변경 사항을 가져왔다.
2. 커밋 계보가 다른 작업물을 병합했다.
3. migration 충돌을 merge migration으로 정리했다.
4. 병합 후 Django system check와 테스트를 실행했다.

#### 2. 미션 완료 원자 처리

미션 완료 시 다음 작업을 하나의 DB 트랜잭션으로 묶었다.

1. 로그인 사용자와 미션 참여 권한 확인
2. 종료된 파티 여부 확인
3. 이미 완료한 미션인지 확인
4. 운동 기록 자동 생성
5. 배지 지급
6. 미션 완료 상태 저장

핵심 개념은 다음과 같다.

```python
with transaction.atomic():
    # 권한 및 기존 완료 상태 확인
    # WorkoutRecord 생성
    # BadgeAward get_or_create
    # 미션 완료 상태 저장
```

#### 3. 친구 요청 구조

- 요청자, 수신자, 상태, 요청 시각, 응답 시각을 저장하는 `FriendRequest`를 사용했다.
- 상대방이 수락한 경우에만 양방향 `FriendLink`를 생성했다.
- 자기 자신 요청, 이미 친구인 사용자, 대기 중 중복 요청을 차단했다.
- 요청받은 사용자만 수락·거절할 수 있게 했다.

#### 4. 파티 초대 구조

- `PartyInvitation`에 대기·수락·거절 상태를 저장했다.
- 수락 시 파티 종료 여부와 최대 인원을 다시 확인했다.
- `select_for_update()` 성격의 행 잠금으로 동시 수락 시 정원 초과를 방지했다.
- 초대받지 않은 사용자의 응답을 차단했다.

#### 5. 사진 인증 검증

- JPEG, PNG, WebP만 허용했다.
- 최대 파일 크기를 5MB로 제한했다.
- 확장자만 보지 않고 Pillow를 이용해 실제 이미지인지 검증했다.
- 솔로·파티 미션과 자동 생성 운동 기록에 사진을 연결했다.

#### 6. 지역 데이터 통합

기존 `광주광역시`와 전남·광주 통합 표기를 서비스 정책상 `전남광주통합특별시`로 바라보도록 migration과 데이터 처리를 보강했다.

#### 7. 테스트 및 문서화

- 격리된 SQLite 테스트 DB에서 백엔드 테스트 39개를 실행했다.
- 39개가 통과했고 Django system check도 이상이 없었다.
- 발표용 백엔드 점검 문서와 구현 체크리스트를 작성했다.

### 사용 기술/도구

- Git merge
- Django `transaction.atomic()`
- DB unique/check constraint
- 행 잠금과 동시성 제어
- Pillow 이미지 검증
- Django TestCase와 mock
- Supabase PostgreSQL
- Markdown/HTML 점검 문서

### 발생한 문제

#### 문제 1. 중복 클릭으로 운동 기록과 배지가 여러 번 생길 가능성

원인은 화면의 버튼 비활성화만으로 중복 요청을 막으려 했기 때문이다. 사용자가 새로고침하거나 요청을 재전송하면 서버는 별개의 요청으로 처리한다.

#### 문제 2. 친구와 파티 관계가 상대방 동의 없이 즉시 생성됨

기존 구조는 친구 선택 즉시 양방향 관계나 파티 멤버십을 만들었다. 요청 상태를 저장할 중간 모델이 없어 수락·거절을 표현할 수 없었다.

#### 문제 3. 사진 저장 용량

Supabase DB의 제한 용량을 고려할 때 이미지 바이너리를 PostgreSQL에 직접 쌓으면 500MB를 빠르게 소비할 우려가 있었다.

#### 문제 4. Selenium 실행 실패

ChromeDriver를 자동으로 내려받을 수 없는 실행 환경 때문에 UI 테스트 1개가 실행되지 않았다. 이는 애플리케이션 assertion 실패가 아니라 브라우저 드라이버·네트워크 환경 문제였다.

#### 문제 5. migration 계보 충돌

팀 브랜치에서 같은 번호의 migration이 각각 생성되어 `0012`, `0014`, `0015`, `0016` 계보가 갈라졌다.

### 해결 방법

- 중복 처리는 UI가 아니라 DB 트랜잭션, `get_or_create`, unique constraint로 방어했다.
- 친구와 파티에 명시적인 초대/요청 상태 모델을 추가했다.
- 사진은 DB에 바이너리를 넣지 않고 파일 경로만 DB에 저장하도록 유지했다. 최종적으로는 Supabase Storage로 이전할 계획을 세웠다.
- 갈라진 migration은 merge migration으로 하나의 후속 계보를 만들었다.
- Selenium과 백엔드 테스트를 분리해, 브라우저 환경 실패가 백엔드 품질 결과를 가리지 않게 했다.

프론트엔드에서 버튼을 한 번만 누르게 하는 방법만으로는 네트워크 재시도와 악의적 요청을 막지 못하므로 단독 해결책으로 사용하지 않았다. 사진을 DB에 직접 저장하는 방식은 용량과 조회 성능 측면에서 부적합해 선택하지 않았다.

### 작동 원리 & 기술 설명

```text
미션 완료 요청
  → 사용자 인증
  → 참여 권한 확인
  → transaction.atomic 시작
  → 기존 완료/운동 기록/배지 확인
  → 운동 기록 생성
  → 배지 생성 또는 기존 값 사용
  → 완료 상태 저장
  → 전체 성공 시 commit
  → 한 단계라도 실패하면 rollback
```

트랜잭션은 여러 DB 변경을 하나의 작업 단위로 만든다. 중간에 예외가 발생하면 모두 취소되므로 ‘미션은 완료됐지만 운동 기록은 없는 상태’를 방지한다. DB 제약은 애플리케이션 검증을 통과한 동시 요청까지 마지막 단계에서 방어한다.

### 코드/파일

- `fitness/models.py`
- `fitness/views.py`
- `fitness/forms.py`
- `fitness/validators.py`
- `fitness/test_web_flow.py`
- `fitness/migrations/0012_merge_gwangju_jeonnam_region.py`
- `fitness/migrations/0013_friendrequest_partyinvitation.py`
- `fitness/migrations/0014_merge_20260918_1144.py`
- `fitness/migrations/0015_friendrequest_responded_at_and_more.py`
- `fitness/migrations/0016_merge_20260918_1453.py`
- `docs/BACKEND_PRESENTATION_AUDIT.md`
- `docs/BACKEND_IMPLEMENTATION_CHECKLIST.md`

### 완료 상태

**부분 완료**

- 완료: 미션 중복 방지, 자동 운동 기록, 배지, 친구 요청, 파티 초대, 이미지 형식·용량 검증, 지역 통합, 백엔드 테스트
- 진행 중: 서버 기준 타이머, Supabase Storage, 사진 URL 접근 제어, 상세 파티 모니터링

---

## 2026-09-19 — 기능 점검 결과 정리와 역할 재분류

### 당시 상황 & 배경

Git 커밋은 없었지만, 전날 통합 디버깅 결과를 발표와 후속 개발에 사용할 수 있도록 정리하는 단계가 필요했다. 요청사항에는 화면 문구 수정과 서버 데이터 설계가 섞여 있어 담당 영역이 불명확했다.

### 무엇을 하려고 했는가?

- 발견한 개선사항을 프론트엔드, 백엔드, 공동 작업으로 나눈다.
- 구현 여부와 추가 테스트 필요 여부를 체크박스로 표현한다.
- 발표에서 ‘구현 완료’와 ‘향후 개선’을 구분한다.

### 왜 필요했는가?

문구 변경과 데이터 무결성 작업을 같은 난이도로 취급하면 일정 산정이 틀어진다. 특히 친구 요청, 파티 초대, 타이머 검증은 화면만 바꿔서는 해결되지 않는다.

### 실제 정리 과정

| 영역 | 프론트엔드 | 백엔드 | 공동 작업 |
|---|---|---|---|
| 메뉴·버튼·문구 | 화면 표시 변경 | - | - |
| 미션 완료 | 완료 UI | 권한·중복·트랜잭션 | 결과 동기화 |
| 운동 타이머 | 초 단위 표시 | 시작·완료 시각 검증 | 상태 복구 |
| 사진 인증 | 선택·미리보기 | 저장·권한·검증 | 업로드 흐름 |
| 친구 요청 | 알림·수락 화면 | 상태·권한·관계 생성 | 사용자 흐름 |
| 파티 초대 | 알림·참여 현황 | 정원·종료·수락 검증 | 모니터링 |
| 지역 랭킹 | 명칭 변경 | 범위·점수 집계 | 실제/데모 표시 |

### 발생한 문제

- 단순한 UI 수정과 데이터 모델 변경이 한 목록에 섞여 있었다.
- 일부 기능은 화면에는 보이지만 서버 검증이 없어 완료로 판단하기 어려웠다.
- 데모 데이터와 실제 DB 데이터가 랭킹에 함께 표시될 수 있었다.

### 해결 방법

‘화면 존재 여부’가 아니라 인증, 권한, DB 저장, 중복 방지, 자동 테스트의 다섯 기준으로 구현 상태를 평가했다. 불확실한 항목은 완료로 표시하지 않고 부분 구현 또는 미완료로 남겼다.

### 작동 원리 & 기술 설명

백엔드 완료 판단 기준은 다음과 같이 정의했다.

```text
요청 가능
  + 입력값 검증
  + 사용자 권한 검증
  + DB 무결성 보장
  + 실패 시 안전한 응답
  + 자동 테스트
  = 백엔드 기능 완료
```

### 코드/파일

- `docs/BACKEND_PRESENTATION_AUDIT.md`
- `docs/BACKEND_IMPLEMENTATION_CHECKLIST.md`
- `docs/BACKEND_IMPLEMENTATION_CHECKLIST.html`

### 완료 상태

**완료** — 문서 기준 정리 완료, 코드 커밋 없음

---

## 2026-09-20 — 배포 전 점검과 운영 환경 전환 준비

### 당시 상황 & 배경

로컬 개발이 중심이던 프로젝트를 Railway에 배포하고 Supabase PostgreSQL을 운영 DB로 사용하기 위한 사전 점검이 필요했다. 로컬 `.env`의 비밀정보를 Git에 올리지 않으면서 배포 서버에는 같은 값을 전달해야 했다.

### 무엇을 하려고 했는가?

- 배포에 필요한 Python 패키지를 확인한다.
- 환경변수 이름과 DB 연결 방식을 정리한다.
- Supabase URL, Railway Variables, Git 소스코드의 역할을 구분한다.
- 배포 브랜치 정책을 확인한다.

### 왜 필요했는가?

GitHub는 소스코드 저장소이고 Railway는 실행 환경이며 Supabase는 데이터 저장소다. 세 시스템의 역할이 섞이면 DB 비밀번호를 Git에 커밋하거나, 잘못된 브랜치를 배포하거나, 로컬 DB와 운영 DB를 혼동할 위험이 있다.

### 실제 점검 과정

1. `requirements.txt`에서 PostgreSQL 드라이버, URL 파서, Gunicorn, WhiteNoise를 확인했다.
2. DB URL은 Supabase Connect 메뉴의 PostgreSQL connection string을 사용하도록 정리했다.
3. 비밀번호가 포함된 `.env`는 로컬 전용으로 유지했다.
4. 운영 환경에서는 Railway 서비스의 Variables에 값을 저장하는 방식을 선택했다.
5. 통합 배포 브랜치는 `main`, 개발 통합은 별도 브랜치로 운영하는 방향을 확인했다.

### 사용 기술/도구

- `psycopg[binary]`
- `dj-database-url`
- Gunicorn
- WhiteNoise
- Railway Variables
- Supabase Session Pooler/connection string

### 발생한 문제

- `psycopg2-binary`와 psycopg3 패키지 선택이 혼재했다.
- 팀원이 DB URL을 Git에 넣어야 하는 것으로 오해할 가능성이 있었다.
- Supabase 비밀번호가 연결 문자열에 포함되므로 노출 위험이 있었다.
- 어떤 브랜치를 Railway가 실제 배포 중인지 명확히 확인할 필요가 있었다.

### 해결 방법

- 현재 프로젝트는 Python 3.13과의 호환성을 고려해 `psycopg[binary]>=3.2,<4.0`을 사용하도록 정리했다.
- DB URL은 Git 파일이 아니라 Railway Variables의 `DATABASE_URL`로 저장하도록 했다.
- `.env.example`에는 변수 이름만 제공하고 실제 키와 비밀번호는 제외했다.
- Railway 서비스 설정에서 연결 저장소와 배포 브랜치를 명시적으로 확인하는 절차를 정했다.

비밀번호가 들어간 `.env`를 Git으로 팀원에게 공유하는 방법은 커밋 이력에 비밀정보가 영구적으로 남을 수 있어 사용하지 않았다. 각 팀원이 운영 DB에 접근해야 할 경우 제한된 권한 또는 안전한 별도 전달 방법을 사용해야 한다.

### 작동 원리 & 기술 설명

```text
GitHub main 브랜치
  → Railway가 코드 checkout
  → Railway Variables를 프로세스 환경에 주입
  → Django settings.py가 os.getenv()로 읽음
  → DATABASE_URL을 dj-database-url이 파싱
  → Supabase PostgreSQL 연결
```

### 코드/파일

- `.env.example`
- `.gitignore` 또는 Git 제외 정책
- `requirements.txt`
- `config/settings.py`
- `railway.json`

### 완료 상태

**진행 중** — 배포 설정 설계 완료, 실제 Railway 반영은 다음 날 진행

---

## 2026-09-21 — 최신 팀 코드 통합, migration 오류 해결, Railway·Supabase·카카오 배포

### 당시 상황 & 배경

팀원의 추가 수정 사항을 가져와 개인 프로젝트와 통합하고, 통합 브랜치를 Railway에 배포해 실제 인터넷에서 접근 가능한 상태로 전환했다. 배포된 서비스에서 생성한 계정이 Supabase에 저장되는 것도 확인했다.

### 무엇을 하려고 했는가?

- 최신 `netfit_tigger` 작업을 pull/merge한다.
- migration 누락으로 발생한 DB 컬럼 오류를 해결한다.
- Railway가 Supabase DB를 사용하도록 설정한다.
- 정적 파일과 Gunicorn 실행을 구성한다.
- 배포 도메인에서 카카오 로그인이 작동하도록 OAuth 주소를 맞춘다.
- 현재 화면 갱신 방식의 한계를 확인한다.

### 왜 필요했는가?

로컬에서만 작동하는 프로젝트는 팀 발표와 외부 시연에 사용할 수 없다. 또한 코드는 최신 모델을 기대하지만 운영 DB schema가 예전이면 페이지 자체가 열리지 않으므로 배포마다 migration을 자동 적용해야 했다.

### 실제 구현 과정

#### 1. 팀 코드 통합

1. `origin/netfit_tigger`의 최신 변경을 확인했다.
2. 솔로·파티 미션, 실제 파티원 구성, 결과 팝업, 친구 목록, 자동 타이머 기능을 통합했다.
3. 갈라진 migration을 `0017_merge_20260921_0949.py`로 정리했다.
4. 백엔드 구현 체크리스트를 최신 상태로 갱신했다.

#### 2. DB 컬럼 오류 점검

발생한 오류:

```text
ProgrammingError at /
column fitness_personaldailyquest.period_type does not exist
```

코드의 `PersonalDailyQuest` 모델은 `period_type` 컬럼을 조회했지만 연결된 PostgreSQL DB에는 해당 migration이 적용되지 않은 상태였다.

해결 절차:

```powershell
python manage.py showmigrations
python manage.py migrate
python manage.py check
```

배포 환경에서 같은 문제가 반복되지 않도록 Railway의 pre-deploy 단계에서 migration을 자동 실행하도록 했다.

#### 3. Railway 배포 구성

`railway.json`에 다음 흐름을 구성했다.

```json
{
  "deploy": {
    "preDeployCommand": "python manage.py migrate --noinput",
    "startCommand": "python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"
  }
}
```

Railway Variables에는 다음 이름을 사용하도록 정리했다.

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<긴 임의 문자열>
DATABASE_URL=<Supabase PostgreSQL 연결 문자열>
KAKAO_REST_API_KEY=<Kakao REST API 키>
KAKAO_CLIENT_SECRET=<Kakao Client Secret>
KAKAO_REDIRECT_URI=https://netfit-production.up.railway.app/login/kakao/callback/
```

`RAILWAY_PUBLIC_DOMAIN`은 Railway가 제공하며, `settings.py`가 이를 `ALLOWED_HOSTS`와 `CSRF_TRUSTED_ORIGINS`에 자동 반영하도록 했다.

#### 4. 운영 보안 설정

`DJANGO_DEBUG=False`일 때 다음을 적용했다.

- HTTPS 프록시 헤더 신뢰
- HTTP → HTTPS 리다이렉트
- Secure session/CSRF cookie
- HSTS
- Content-Type sniffing 방지
- 안전한 referrer policy

#### 5. 카카오 OAuth 배포 설정

카카오 디벨로퍼스와 Railway/Django에서 동일한 주소를 사용하도록 정리했다.

```text
사이트 도메인
https://netfit-production.up.railway.app

Redirect URI
https://netfit-production.up.railway.app/login/kakao/callback/
```

카카오 디벨로퍼스에는 허용 주소를 등록하고, Railway에는 Django가 로그인 요청에 사용할 주소와 키를 환경변수로 전달했다.

#### 6. Supabase 연결 검증

배포된 웹에서 새 계정을 생성한 뒤 Supabase 테이블에 계정과 연결 데이터가 생성되는 것을 확인했다. 이를 통해 다음 연결 흐름이 실제로 동작함을 확인했다.

```text
사용자 브라우저 → Railway Django → DATABASE_URL → Supabase PostgreSQL
```

#### 7. 화면 자동 갱신 문제 분석

DB에는 데이터가 저장되지만 화면에서 새로고침해야 최신 내용이 보이는 증상을 확인했다. 원인은 대부분의 화면이 Django 서버 렌더링 방식이라 최초 요청 시점의 HTML만 표시하고 이후 DB를 다시 조회하지 않기 때문이다.

현재 자동 갱신이 있는 부분:

- 날씨 `fetch`
- 스포츠 뉴스 `fetch`와 화면 롤링
- 브라우저 운동 타이머
- 의상 구매의 AJAX 처리 일부

자동 갱신이 부족한 부분:

- 운동 기록 목록
- 미션 완료 상태
- 친구 요청과 알림
- 파티 참여 현황
- 지역 랭킹

### 사용 기술/도구

- Railway
- Supabase PostgreSQL
- Django migration
- `dj-database-url`
- psycopg3
- Gunicorn
- WhiteNoise
- Kakao OAuth 2.0
- Git merge/push
- JavaScript Fetch API 분석

### 발생한 문제

#### 문제 1. `period_type` 컬럼 부재

모델과 migration 파일은 최신이지만 실제 DB schema가 과거 상태여서 ORM 쿼리가 존재하지 않는 컬럼을 조회했다.

#### 문제 2. 배포 환경변수 이름 혼동

일반적인 예시에서는 `SECRET_KEY`, `DEBUG`를 사용하지만 현재 코드는 `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`를 읽는다. 이름이 다르면 운영 설정이 적용되지 않고 개발용 기본값으로 실행될 수 있었다.

#### 문제 3. 카카오 Redirect URI 불일치 가능성

프로토콜, 도메인, 경로 또는 마지막 `/`가 다르면 카카오 인증이 거절될 수 있었다.

#### 문제 4. 새로고침 전까지 최신 데이터 미표시

서버에는 즉시 저장됐지만 열린 HTML은 자동으로 바뀌지 않았다. WebSocket이나 주기 조회가 없는 서버 렌더링 방식의 정상적인 한계였다.

#### 문제 5. 로컬 파일 저장의 배포 한계

인증사진이 서버의 `media/` 폴더에 저장된다. Railway의 로컬 파일 시스템은 영구 이미지 저장소로 사용하기에 적합하지 않으므로 재배포 시 파일 보존을 보장하기 어렵다.

### 해결 방법

- migration 누락은 `migrate` 실행과 pre-deploy 자동화로 해결했다.
- 실제 코드가 읽는 환경변수 이름을 `rg`로 확인해 Railway 변수명과 맞췄다.
- Kakao 사이트 도메인, Redirect URI, `KAKAO_REDIRECT_URI`를 완전히 동일하게 설정했다.
- 화면 갱신은 초기 버전에서 JSON API + JavaScript `fetch` polling을 우선 적용하는 방향을 선택했다.
- 실시간성이 매우 중요한 파티 상태나 알림만 추후 Django Channels/WebSocket 대상으로 분류했다.
- 사진은 Supabase Storage로 이전할 계획을 유지했다.

모든 화면에 WebSocket을 바로 도입하지 않은 이유는 Redis 또는 채널 계층, 연결 관리, 재접속 처리, 배포 비용까지 추가되기 때문이다. 5~60초 단위 갱신이면 충분한 목록은 polling이 구현과 운영 측면에서 더 단순하다.

### 작동 원리 & 기술 설명

#### Railway 환경변수

Railway의 Variables 값은 프로세스 시작 시 OS 환경변수로 주입된다. Django는 다음처럼 값을 읽는다.

```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "local-development-only-secret-key")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
KAKAO_REDIRECT_URI = os.environ.get("KAKAO_REDIRECT_URI", "").strip()
```

로컬 `.env`는 개발 PC에서만 사용하고, 배포 서버에서는 Railway Variables가 같은 역할을 수행한다.

#### Kakao 로그인 흐름

```text
로그인 버튼
  → /login/kakao/
  → state와 redirect_uri를 세션에 저장
  → 카카오 인증 화면
  → /login/kakao/callback/?code=...&state=...
  → state 검증
  → 인증 코드로 access token 요청
  → 카카오 사용자 정보 조회
  → KakaoAccount와 Django User 연결
  → 로그인 세션 생성
```

#### 화면 갱신 개선안

```javascript
setInterval(async () => {
  const response = await fetch("/api/dashboard/status/");
  const data = await response.json();
  updateDashboard(data);
}, 5000);
```

내가 수행한 저장 요청은 응답 직후 DOM을 변경하고, 다른 사용자의 변경은 기능 중요도에 따라 5~60초 간격으로 조회하는 방식이 적합하다.

### 코드/파일

- `config/settings.py`
- `fitness/kakao.py`
- `fitness/urls.py`
- `requirements.txt`
- `railway.json`
- `.env.example`
- `fitness/migrations/0017_merge_20260921_0949.py`
- `docs/BACKEND_IMPLEMENTATION_CHECKLIST.md`

### 완료 상태

**부분 완료**

- 완료: Railway 공개 배포, Supabase DB 연결, 계정 생성 검증, migration 자동화, 정적 파일, 운영 보안 기본값, Kakao 설정 구조
- 진행 중: 화면 데이터 자동 갱신
- 미완료: Supabase Storage, WebSocket 기반 실시간 처리, 운영 모니터링·백업 자동화

---

## 2026-09-22 ~ 2026-09-25 — 완성일까지의 계획

> 아래 항목은 회고 작성일 이후 계획이며 완료 사실로 기록하지 않는다.

### 2026-09-22 — 데이터 자동 갱신

- 운동 기록·미션 상태 JSON API 설계
- 저장 성공 직후 DOM 반영
- 친구 요청·파티 초대 10초 polling
- 랭킹 30~60초 polling 또는 수동 갱신 버튼
- API 인증과 응답 schema 테스트

**예정 상태: 진행 예정**

### 2026-09-23 — 파일 저장과 운영 안정성

- 인증사진을 Supabase Storage로 이전
- DB에는 bucket 경로, 사용자, 미션, 등록 시각, 상태만 저장
- 비공개 bucket과 signed URL 적용 검토
- 다른 사용자의 수정·삭제 권한 차단 테스트
- 고아 파일 정리 정책 작성

**예정 상태: 진행 예정**

### 2026-09-24 — 통합 테스트와 발표 리허설

- 29·30·59·60·89·90분 배지 경계값 테스트
- 친구 요청·수락·거절·중복 테스트
- 파티 초대·정원·종료 파티 테스트
- Kakao 로그인과 일반 로그인 운영 환경 테스트
- 외부 API timeout/fallback 테스트
- 실제 DB 데이터와 데모 랭킹 분리 확인

**예정 상태: 진행 예정**

### 2026-09-25 — 최종 완성 및 발표 자료 확정

- `main` 배포 commit 고정
- Railway deployment log와 migration 결과 저장
- 시연용 계정과 데이터 확인
- 민감정보 노출 여부 확인
- PPT에 요청 URL, DB 테이블, 테스트 결과, 실제 화면 증거 배치
- 최종 회고록의 예정 상태를 실제 결과로 갱신

**예정 상태: 완성 목표일**

---

# 마일스톤과 최종 정리

## 1. 프로젝트 전체에서 구현한 주요 기능

### 계정과 인증

- Django 일반 회원가입·로그인·로그아웃
- Kakao OAuth 로그인
- Kakao 계정과 Django User 연결
- 사용자 생성 시 Profile과 CharacterCard 자동 생성
- 온보딩 완료 여부에 따른 이동 제어

### 운동·미션·성장

- 솔로·파티 일일 미션
- 직접 운동 기록
- 미션 완료 시 운동 기록 자동 생성
- 30·60·90분 기준 배지 지급
- 배지와 운동 기록 중복 생성 방지
- 레벨·XP·카드 등급 모델
- 브라우저 타이머와 로컬 복구

### 친구·파티

- 친구 요청, 수락, 거절
- 수락 시 양방향 친구 관계 생성
- 파티 초대, 수락, 거절
- 정원과 종료 여부 재검증
- 동시 수락을 고려한 행 잠금
- 파티 참여자의 미션 완료 상태 표시

### 공공데이터와 외부 API

- KSPO 공공체육시설 CSV 적재 명령
- 지역·카테고리·검색어 필터
- GPS 및 지역 대표 좌표 기반 거리 정렬
- 전남광주 통합 지역 값 반영
- Open-Meteo 날씨
- 스포츠 뉴스 RSS와 메모리 캐시

### 랭킹·배틀·게임화

- 지역·파티·친구 범위 랭킹
- 누적 배지 점수 정렬
- 캐릭터 의상 구매와 장착
- 운동 기록 기반 카드 전투력 계산
- 배틀 데이터와 결과 화면

### 품질·배포

- 백엔드 자동 테스트 39개 통과 기록
- Django system check 통과
- migration 계보 병합
- Railway 자동 migration과 Gunicorn 실행
- WhiteNoise 정적 파일 제공
- Supabase PostgreSQL 연결
- 운영 HTTPS·Secure Cookie 설정

## 2. 가장 어려웠던 부분과 해결 과정

### 여러 브랜치의 모델과 migration 통합

가장 어려운 점은 기능 코드만 합치는 것이 아니라 각 브랜치가 만든 DB schema 변경 순서를 함께 합치는 일이었다. 동일 번호 migration이 갈라지면서 한쪽 기능을 지우지 않고 두 계보를 모두 이어야 했다. merge migration을 만들고 실제 DB에 적용한 뒤 테스트하는 방식으로 해결했다.

### 데이터 중복과 동시성

미션 완료, 친구 요청, 파티 초대는 사용자가 한 번만 누른다는 가정으로 만들 수 없었다. 트랜잭션, unique constraint, `get_or_create`, 행 잠금을 함께 사용해 애플리케이션과 DB 두 계층에서 방어했다.

### 로컬과 운영 환경 차이

로컬 SQLite에서는 정상이어도 Supabase PostgreSQL에서는 migration 누락과 SSL 연결 문제가 나타날 수 있었다. 환경변수 기반 DB 선택, psycopg3, `dj-database-url`, 배포 전 migration 자동화로 차이를 줄였다.

### OAuth 주소 일치

카카오 로그인은 키만 있다고 동작하지 않는다. 카카오 디벨로퍼스의 사이트 도메인·Redirect URI와 Django가 전송하는 URI가 프로토콜, 도메인, 경로, 마지막 슬래시까지 같아야 한다. 로컬과 배포 URI를 환경변수로 분리해 해결했다.

### ‘실시간’에 대한 기대와 실제 구조

DB 저장은 즉시 완료됐지만 화면은 이전 HTML을 계속 보여주었다. 서버 렌더링, polling, WebSocket의 차이를 이해하고 기능별 요구 시간에 따라 기술을 선택하는 것이 필요했다. 전체 WebSocket보다 JSON API와 polling을 우선 적용하는 방향으로 범위를 조절했다.

## 3. 배운 기술과 개념

- Django ORM 모델 관계와 migration 계보
- 인증 데이터와 서비스 프로필 분리
- OAuth 2.0 authorization code 흐름과 `state` 검증
- DB transaction, unique constraint, row lock을 이용한 무결성 보장
- SQLite와 PostgreSQL의 개발·운영 분리
- Railway 환경변수와 배포 명령
- Supabase connection string과 비밀정보 관리
- Gunicorn과 WhiteNoise를 이용한 Django 운영 실행
- 파일 업로드에서 크기, MIME/실제 이미지, 소유권 검증
- 서버 렌더링, AJAX polling, WebSocket의 차이
- 자동 테스트와 수동 UI 테스트를 분리해 해석하는 방법
- Git branch 병합과 migration 충돌 해결

## 4. 다음에 개선할 점

### 높은 우선순위

1. 운동 시작 시각, 목표 시간, 완료 시각을 DB에 저장하고 서버 시간으로 운동시간을 검증한다.
2. 미션·운동 기록에 XP 지급을 실제로 연결하고 중복 지급을 방지한다.
3. 인증사진을 Supabase Storage의 비공개 bucket으로 이전한다.
4. 실제 사용자 랭킹과 데모 데이터를 완전히 분리한다.
5. 친구 삭제, 파티 탈퇴·추방·파티장 위임 기능을 추가한다.

### 운영 안정성

1. Sentry 또는 구조화 로그를 이용해 배포 오류를 추적한다.
2. Supabase 백업과 복구 절차를 문서화하고 실제 복구를 연습한다.
3. 주요 조회 필드의 인덱스와 랭킹 쿼리 성능을 점검한다.
4. 외부 API timeout, retry, rate limit 정책을 통일한다.
5. 비밀번호나 DB URL이 노출된 경우 즉시 회전하는 운영 규칙을 만든다.

### 테스트

1. PostgreSQL 기반 CI 테스트를 추가한다.
2. Selenium/Playwright 브라우저 버전을 고정한다.
3. 배지 경계값 전체와 동시 요청을 테스트한다.
4. 파일 직접 URL 접근과 다른 사용자 권한을 테스트한다.
5. Railway 배포 후 smoke test를 자동화한다.

## 5. 최종 회고

이번 프로젝트에서 가장 크게 배운 점은 **화면이 동작하는 것과 서비스 데이터가 안전하게 동작하는 것은 다르다**는 것이다. 초기에는 버튼을 누르고 결과 화면이 보이는 데 집중했지만, 실제 점검 과정에서는 권한 없는 요청, 중복 클릭, migration 누락, 배포 환경변수, DB 용량, OAuth 주소 같은 백엔드 문제가 서비스 신뢰성을 결정했다.

또한 Git, Railway, Supabase의 역할을 분리해서 이해하게 되었다. Git은 코드와 migration의 이력을 관리하고, Railway는 코드를 실행하며 환경변수를 주입하고, Supabase는 여러 실행 환경이 공유할 데이터를 보관한다. 이 구조를 이해한 뒤부터 ‘팀원이 만든 계정이 왜 pull 후 보이지 않는가’, ‘DB URL을 Git에 넣어야 하는가’, ‘배포 서버가 어느 브랜치를 실행하는가’ 같은 문제를 명확히 설명할 수 있었다.

남은 핵심 과제는 서버 기준 타이머, Supabase Storage, 자동 화면 갱신, 운영 모니터링이다. 완성일까지 이 항목의 범위를 현실적으로 조정하고, 구현하지 못한 기능은 발표에서 숨기지 않고 현재 상태와 개선 계획을 구분해 설명하는 것이 최종 목표다.

