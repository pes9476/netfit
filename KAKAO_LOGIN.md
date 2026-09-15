# 카카오 로그인 설정

로그인 화면에서 아이디·비밀번호 로그인과 카카오 로그인을 모두 제공합니다. /register/에서 일반 회원가입 후 프로필을 설정할 수 있습니다.
기존 일반 계정 데이터와 Django 관리자 로그인은 보존합니다. 일반 계정의 기존 기록을 카카오 계정으로 자동 이전하지 않습니다.
카카오 최초 로그인 시 별도 회원, 프로필, 캐릭터 카드가 생성됩니다.
기존 일반 계정과 자동으로 합치지 않습니다. 카카오 이메일/닉네임 동의는 필요하지 않습니다.
닉네임을 정하지 않은 카카오 회원은 로그인 후 프로필로 이동하며, 임시 ID를 이름으로 표시하지 않습니다.
프로필에서 저장한 닉네임이 화면에 표시됩니다. 현재는 기존 username 필드를 사용하며 별도 닉네임 DB 필드를 추가하지 않았습니다.

## 카카오 개발자 앱

1. https://developers.kakao.com/ 에 로그인하고 앱을 생성합니다.
2. [카카오 로그인] > [사용 설정]에서 상태를 ON으로 설정합니다.
3. [앱] > [플랫폼 키] > [REST API 키]에서 REST API 키와 클라이언트 시크릿을 확인합니다. 어드민 키가 아닙니다.
4. REST API 키의 리다이렉트 URI에 다음 주소를 등록합니다.

```text
http://127.0.0.1:8000/login/kakao/callback/
```

## 실행 (PowerShell)

로컬에서는 프로젝트 루트의 `kakao.local.json`에 `KAKAO_REST_API_KEY`와
`KAKAO_CLIENT_SECRET`을 저장할 수도 있습니다. 이 파일은 Git에서 제외되며
서버 시작 시 자동으로 읽습니다. 환경변수가 있으면 환경변수가 우선합니다.
설정 변경 후 서버를 재시작하세요.

프로젝트 폴더의 터미널에서 실제 값을 입력합니다. 키를 소스 파일이나 GitHub에 넣지 마세요.

```powershell
$env:KAKAO_REST_API_KEY = "발급받은 REST API 키"
$env:KAKAO_CLIENT_SECRET = "발급받은 클라이언트 시크릿"
$env:KAKAO_REDIRECT_URI = "http://127.0.0.1:8000/login/kakao/callback/"
py manage.py migrate
py manage.py runserver
```

같은 터미널에서 서버를 실행해야 환경변수가 적용됩니다. 이 프로젝트는 .env 파일을 자동으로 읽지 않습니다.
http://127.0.0.1:8000/login/ 에 접속해 카카오 로그인 버튼을 누르세요.
localhost와 127.0.0.1은 서로 다른 호스트이므로 섞어 사용하지 마세요.
배포 시 HTTPS 사이트 주소로 리다이렉트 URI와 환경변수를 함께 바꾸고 ALLOWED_HOSTS도 설정해야 합니다.

카카오 토큰은 서버에서 사용자 확인에만 사용하며 DB나 세션에 저장하지 않습니다.
로그아웃은 이 프로젝트의 로그인 세션만 종료합니다.

## 검사

```powershell
py manage.py check
py manage.py test fitness.test_kakao
```

자동 테스트는 카카오 응답을 모의 처리합니다. 실제 키 등록 후 브라우저에서 동의, 로그인, 재로그인을 확인해야 합니다.

공식 문서:
- https://developers.kakao.com/docs/ko/kakaologin/rest-api
- https://developers.kakao.com/docs/ko/kakaologin/prerequisite
- https://developers.kakao.com/docs/ko/getting-started/quota
