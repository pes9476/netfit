# NetFit 개발 가이드

## NetFit 개발 및 배포 브랜치
- 기본 개발 브랜치는 testsv이며 upstream은 origin/testsv다.
- 코드 수정 전 git status와 현재 브랜치를 확인한다.
- 일반적인 개발·수정·저장 요청은 testsv에서 처리한다.
- 사용자가 push를 요청하면 기본 대상은 origin testsv다.
- runsv는 Railway 운영 자동 배포 브랜치다. 사용자가 운영 배포를 명시적으로 요청할 때만 runsv 병합·push를 수행한다.
- main과 netfit_tigger는 폐기된 원격 이름이다. 다시 생성하거나 push하지 않는다.
- 브랜치 전환 시 미커밋 변경과 로컬 전용 커밋을 보존한다. force push, reset --hard, 파일 삭제로 문제를 해결하지 않는다.
- DB migrate는 현재 연결된 DB에 적용된다. 개발 실행 전 로컬 설정이 운영 Supabase를 가리키는지 값 노출 없이 확인한다.
- 비밀번호, SECRET_KEY, DATABASE_URL, .env와 개인 업로드 파일을 Git에 커밋하지 않는다.
