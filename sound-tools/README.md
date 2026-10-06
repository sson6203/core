# 음향 현장 도구 (통합본)

최신 도구 네 개를 HTML 파일 하나로 합쳤습니다. 위쪽 카테고리 탭이나 첫 화면의 카드를 누르면 해당 도구가 열립니다.

| 카테고리 | 원본 (`sson6203/speaker-rigging`) |
|---|---|
| QSD 현장 배치 판단 v4 | `QSD-v4/` (브랜치 `claude/gallant-davinci-3jr45t`). 여러 JS/CSS 파일을 한 파일로 인라인했습니다. |
| View Point v1.3 | `View-Point-v1.3.html` (`main`) |
| 케이블 판독기 | `케이블판독기.html` (`main`) |
| 스피커 리깅 산정 v9.4 | `스피커-리깅-산정-v9.4.html` (`main`) |

## 결과물 (`dist/`)

| 파일 | 용도 |
|---|---|
| `음향도구-통합.html` | 그대로 더블클릭해서 쓰는 단일 파일. 인터넷 연결 없이 동작합니다. |
| `sound-tools-amd64.tar` | 시놀로지 Container Manager에서 가져올 이미지 (Intel/AMD CPU 모델: DS224+, DS923+, DS1522+ 등 대부분의 Plus 모델) |
| `sound-tools-arm64.tar` | ARM CPU 모델용 이미지 (DS223, DS423, DS124 등) |

어느 쪽인지 모르겠으면 DSM **제어판 → 정보 센터 → 일반 → CPU**를 보세요. Intel·AMD면 amd64, Realtek 같은 ARM 칩이면 arm64입니다.

탭 사이를 옮겨 다녀도 각 도구에 입력한 내용은 남아 있습니다. 주소 끝에 `#qsd`, `#viewpoint`, `#cable`, `#rigging`을 붙이면 그 도구가 바로 열립니다. 오른쪽 위 **새 탭** 버튼은 지금 보는 도구만 따로 새 탭에 엽니다(인쇄가 이상할 때 유용합니다).

## 시놀로지 NAS에 올리기 (DSM 7.2 Container Manager)

1. **패키지 센터**에서 **Container Manager**를 설치합니다.
2. **Container Manager → 이미지 → 가져오기 → 파일에서 추가**를 누르고 `sound-tools-amd64.tar`(또는 arm64)를 고릅니다.
   - DSM 7.1 이하의 Docker 패키지는 **이미지 → 추가 → 파일에서 추가**입니다.
3. 목록에 생긴 `sound-tools:latest`를 선택하고 **실행**을 누릅니다.
4. 설정
   - 컨테이너 이름: `sound-tools`
   - **자동 재시작 활성화** 체크
   - 포트 설정: 로컬 포트 `8080` → 컨테이너 포트 `8080` (8080을 이미 쓰고 있으면 로컬 포트만 다른 번호로)
   - 볼륨·환경 변수는 필요 없습니다.
5. 브라우저에서 `http://NAS-IP:8080` 을 엽니다.

Container Manager의 **프로젝트** 기능을 쓰려면 이미지를 가져온 뒤 이 폴더의 `docker-compose.yml`을 그대로 쓰면 됩니다.

### 새 버전으로 바꾸기

컨테이너를 정지·삭제하고, 이미지 `sound-tools`도 삭제한 뒤 새 tar로 2~4단계를 다시 하면 됩니다. 브라우저에 저장된 작업 내용은 그대로 남습니다.

### 알아 둘 점

- 각 도구의 자동 저장 내용은 **브라우저**에 저장됩니다(NAS에 저장되지 않음). 같은 브라우저라도 접속 주소가 다르면(`192.168.0.10:8080` 과 QuickConnect 주소 등) 저장 공간이 따로입니다. 기기를 옮길 때는 각 도구의 저장·내보내기(JSON) 기능을 쓰세요.
- 외부에서 HTTPS로 쓰려면 DSM **제어판 → 로그인 포털 → 고급 → 역방향 프록시**에서 `https://도메인` → `http://localhost:8080` 으로 연결하면 됩니다.
- 이미지는 정적 웹 서버 하나와 HTML 파일 하나만 들어 있는 약 11 MB짜리이고, 권한 없는 사용자(65534)로 실행됩니다. 전송할 때 gzip으로 압축해 약 1.8 MB만 내려받습니다.

## 다시 만들기

```bash
./build.sh /path/to/speaker-rigging   # Go 1.22+, Python 3.11+ 필요
```

- `build.py` — 원본 저장소에서 네 도구를 읽어 `launcher.html`에 넣고 `dist/음향도구-통합.html`을 만듭니다. 어떤 브랜치·파일을 쓸지는 `build.py`의 `TOOLS` 목록에서 바꿉니다.
- `server/` — 이미지 안에서 도는 정적 웹 서버(Go, 외부 의존성 없음).
- `make_image.py` — Docker 없이 `docker load`용 tar를 만듭니다.
- `Dockerfile` — Docker가 있는 PC에서 `docker buildx`로 직접 빌드하고 싶을 때 씁니다.
