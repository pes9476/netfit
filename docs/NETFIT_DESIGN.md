# NetFit 스타일 적용

- 네이비 배경, 민트 기본 버튼, 인디고 내비게이션, 오렌지 배틀 버튼.
- `fitness/static/fitness/css/netfit-theme.css`: 기존 Django 화면을 위한 시각 스타일.
- `fitness/static/fitness/css/netfit-mascots.css`: 네 캐릭터 이미지와 움직임.
- `fitness/static/fitness/img/netfit-mascots.png`: 첨부 이미지를 바탕으로 배경을 제거·재구성한 PNG 시트. 원본 파일의 단순 복사는 아니며 AI 이미지 편집 결과입니다.
- 네 마스코트는 프로필에서 직접 선택합니다. 인바디·BMI·나이·성별로 자동 변경하지 않습니다.
- 기존 avatar_preference 저장값을 호환용으로 유지합니다. ACTIVE/AUTO/SLIM=백호, MUSCULAR=백곰, SOFT=햄스터, BALANCED=아기공룡. DB 구조 변경은 없습니다.
- 인바디 기록, BMI 계산, 로그인, 회원가입, 운동 경험치, 랭킹, 친구, 배틀, 시설, 튼튼머니 팝업 유지.
- 캐릭터 움직임은 CSS 애니메이션이며 3D 모델 렌더링이 아닙니다. 동작 줄이기 설정을 존중합니다.

## 이미지 편집

Built-in image_gen 사용. 입력은 사용자 첨부 캐릭터 이미지 네 장입니다. 출력 시트 순서는 왼쪽 위 백호, 오른쪽 위 백곰, 왼쪽 아래 햄스터, 오른쪽 아래 아기공룡입니다.

사용한 프롬프트:

> Use case: background-extraction and compositing. Edit targets: the four most recent user-attached mascot pictures: orange chubby hamster with black headband, white tiger jogging in cyan headband/shoes, green baby dinosaur with rainbow wristbands, white bear in purple tank holding rainbow dumbbell. Create ONE production PNG sprite atlas, 2048x2048 square, with actual transparent alpha background. Arrange these exact four unchanged full-body characters in a strict equal 2x2 grid: top-left WHITE TIGER, top-right WHITE BEAR, bottom-left ORANGE HAMSTER, bottom-right GREEN DINOSAUR. Each character centered in its own 1024x1024 quadrant with 10% padding and no crossing quadrant edges. Remove only the white backgrounds and floor shadows. Preserve their original faces, expressions, poses, fur or skin texture, accessories, proportions and colors as faithfully as possible. No redesigns, no extra objects, no text, no labels, no gridlines, no backdrop, no checkerboard baked in. This is a website sprite asset, not an illustration of a sheet. Keep complete limbs and ears within each cell.

## 검증

회원가입·일반/카카오 로그인(모의 응답)·로그아웃·운동 경험치·수동 마스코트 선택 및 인바디 독립성 테스트 19개 통과. PC/모바일에서 페이지 렌더링, 가로 넘침, JS 오류, BMI 미리보기, 배틀 결과 표시 확인. 실제 운영 DB는 수정하지 않았습니다.
