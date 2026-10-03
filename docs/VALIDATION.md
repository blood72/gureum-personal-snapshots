# 구현 검증 기록

기준일: 2026-10-03 (한국 시간).

## 확인한 upstream

- 기준 main: `46c62e51a311c89ee084ce14eb8071b6d81f765d`
- [실제 성공한 upstream CI](https://github.com/gureum/gureum/actions/runs/36431608700/job/108958924236):
  2026-09-28, 45개 테스트 통과. macOS 26.6.2 arm64, Xcode 26.6, macOS SDK 26.5.
- [CI 정의](https://github.com/gureum/gureum/blob/46c62e51a311c89ee084ce14eb8071b6d81f765d/.github/workflows/ci.yaml):
  재귀 서브모듈과 OSX scheme의 build/test 사용.
- [빌드 프로젝트](https://github.com/gureum/gureum/blob/46c62e51a311c89ee084ce14eb8071b6d81f765d/Gureum.xcodeproj/project.pbxproj):
  ScriptSupport의 Version.xcconfig 쓰기, SPM resolve, Release 서명 설정 확인.
- [OSX scheme](https://github.com/gureum/gureum/blob/46c62e51a311c89ee084ce14eb8071b6d81f765d/Gureum.xcodeproj/xcshareddata/xcschemes/OSX.xcscheme):
  archive post-action이 upstream 개발자 인증서/공증 흐름으로 이어지므로 일반 build 사용.
- [GitHub 러너 문서](https://docs.github.com/en/actions/reference/runners/github-hosted-runners),
  [macOS 26 arm64 이미지](https://github.com/actions/runner-images/blob/main/images/macos/macos-26-arm64-Readme.md).

## 로컬에서 수행한 검사

Linux 환경에서 Python 표준 라이브러리 단위 테스트, Python/Bash 구문 검사,
actionlint 1.7.12, ShellCheck 0.11.0으로 검증했습니다.
테스트는 입력 검증, 버전/revision 규칙, cask 생성, git 추적 파일만 소스에 포함,
체크섬 검증, GitHub 조회 오류 시 안전하게 중단하는 동작을 다룹니다.
인계 ZIP SHA256과 내부 manifest를 확인한 뒤 실제 upstream main, 재귀 서브모듈,
공식 macOS 26 arm64 러너의 Xcode 26.6 경로와 Actions 고정 SHA를 다시 확인했습니다.
현재 로컬 단위 테스트는 10개이며 모두 통과했습니다. 추가한 테스트는 체크섬을 다시
계산해도 앱 안의 원본 SHA가 metadata와 다르면 산출물 검증이 실패하는지 확인합니다.
CI에서 앱·소스 압축 파일의 메타데이터/lockfile, 고지 파일, cask와 전체 체크섬을
검증하고 unsigned pkg를 펼쳐 앱 서명과 내장 메타데이터를 재검증하도록 보강했습니다.
별도 코드 리뷰에서 CURRENT_PROJECT_VERSION에 SHA를 넣으면 생성 C 코드가 깨질 수 있음을
확인해 숫자 bundle/build 버전과 SHA release/cask 버전을 분리했습니다.
Resources 안의 Preferences.prefPane은 별도로 서명·entitlement를 검사합니다.

이 검사는 워크플로·보조 코드의 검증입니다. upstream CI 성공은 이 저장소의 별도
Release 빌드/서명/패키징이 성공했다는 증거가 아닙니다.

## 아직 수행하지 않은 검사

- 이 저장소 workflow_dispatch 실행
- Xcode Debug 테스트와 Release 빌드
- 실제 빌드 앱의 entitlement/서명/아키텍처 및 source bundle 검사
- unsigned pkg 설치, Homebrew cask 설치·업데이트
- TextEdit/Terminal 등에서 입력기 동작과 권한 재승인
- Release 업로드·게시, tap 반영
- 로고/아이콘 및 제3자 구성 요소의 배포 조건 검토 완료

이번 설정 요청은 `publish_release=false`로 실제 Actions 실행과 산출물 검증을
포함합니다. 현재 클라우드의 GitHub API 접근이 프록시 403으로 차단되어 있어
실행·결과 검증은 아직 완료하지 못했습니다. 실제 성공 결과는 실행 후에만 기록합니다.
Release 게시, tap 수정 및 실제 Mac 설치·입력 테스트는 이번 CI 검증에 포함하지 않습니다.
