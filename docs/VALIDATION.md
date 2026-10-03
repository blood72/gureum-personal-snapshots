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

- Xcode Debug 테스트와 Release 빌드의 성공 확인
- 실제 빌드 앱의 entitlement/서명/아키텍처 및 source bundle 검증 완료
- unsigned pkg 설치, Homebrew cask 설치·업데이트
- TextEdit/Terminal 등에서 입력기 동작과 권한 재승인
- Release 업로드·게시, tap 반영
- 로고/아이콘 및 제3자 구성 요소의 배포 조건 검토 완료

## 첫 실제 Actions 실행

- [실행 37093581005](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37093581005)
  (2026-10-03 한국 시간), builder `e16dfea8183e737d9030c1d05f3750219a2c2a47`.
- 입력: `upstream_ref=main`, `build_revision=1`, `publish_release=false`,
  `distribution_reviewed=false`.
- 러너 준비, builder 체크아웃, 지원 코드 테스트, 공식 소스·서브모듈 체크아웃 성공.
- `Test, build, verify and package arm64 snapshot` 단계가 exit code 1로 실패.
  이후 확보한 로그에서 upstream Debug 테스트 45개(실패 0개)와 Release 빌드 성공을 확인했습니다.
  실패는 빌드 뒤의 arm64 검사에서 발생했습니다. upstream의 macOS 10.13 배포 대상에 따라
  Xcode가 Intel 전용 구형 Swift 런타임을 포함했고 `libswiftCore.dylib: x86_64`가 검출됐습니다.
  소스 수정 없이 공통 Xcode 옵션에 `MACOSX_DEPLOYMENT_TARGET=11.0`을 추가해 재검증합니다.
- snapshot artifact 업로드는 건너뛰었으며,
  `gureum-diagnostics-37093581005-1` 진단 artifact만 생성됐습니다.
- 게시 job은 건너뛰었습니다. Release와 tap은 변경하지 않았습니다.

클라우드의 GitHub API, 로그 다운로드 및 진단 artifact 접근은 도메인 허용 변경 후
정상화됐습니다. 첫 실행 로그와 진단 파일을 다운로드해 위 실패 원인을 확인했습니다.
새 자격 증명은 추가하지 않았습니다.

## 두 번째 실제 Actions 실행

- [실행 37094222756](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37094222756),
  builder `c063fd537b7688f736426b57e911bd75bff205e9`.
- macOS 11 배포 대상으로 Debug 테스트와 Release 빌드가 성공했고 Intel 전용 구형
  Swift 런타임 문제는 해결됐습니다. 이후 `libswift_Concurrency.dylib: x86_64 arm64`가
  검출되어 arm64-only 검사에서 실패했습니다. Xcode가 복사한 concurrency 역호환
  런타임은 universal 바이너리였습니다.
- 포함된 최상위 `libswift*.dylib`에 실제 arm64 slice가 있는지 먼저 확인하고,
  `lipo -thin arm64`로 해당 slice를 보존한 뒤 ad-hoc 재서명·검증하도록 수정했습니다.
  나머지 Mach-O 및 최종 앱의 엄격한 arm64·서명 검사는 유지합니다.
- snapshot artifact와 Release는 생성하지 않았습니다. 수정 후 재검증합니다.

## 세 번째 실제 Actions 실행

- [실행 37094544382](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37094544382),
  builder `1daaf8e5e48963b4673060322bebcac8296e2457`.
- Swift concurrency 런타임의 arm64 slice 보존·재서명과 전체 Mach-O arm64 검사가 성공했습니다.
  앱, Preferences 및 프레임워크의 codesign 검증도 성공했습니다.
- 이후 Preferences의 entitlement 출력을 plist로 읽는 검사에서 실패했습니다.
  빌드 로그에는 원래 Preferences에 entitlements를 지정해 서명한 뒤 Release Resources
  복사 과정에서 strip하는 명령이 있습니다. 최종 복사본에 원본
  `OSX/Gureum.entitlements`를 명시해 ad-hoc 재서명한 뒤 바깥 앱을 서명하도록 수정합니다.
- 상세 로그는 확보했으며 진단 artifact의 새 저장소
  `productionresultssa2.blob.core.windows.net`은 클라우드에서 프록시 403으로 차단됐습니다.
  해당 호스트를 환경 설정 초안에 추가했습니다. 다음 실행에서 검증을 계속합니다.

전체 SHA 입력 경로는 Linux에서 지원 스크립트를 실제 실행해 확인했습니다.
`46c62e51a311c89ee084ce14eb8071b6d81f765d`의 공식 main 조상 확인, 재귀 서브모듈
체크아웃, 숫자 bundle 버전 `1.0.1`과 전체 원본 SHA의 분리 기록이 성공했습니다.

이번 설정 요청은 `publish_release=false`로 실제 Actions 실행과 산출물 검증을
포함하며 아직 완료하지 못했습니다. 실제 성공 결과는 확인 후에만 기록합니다.
Release 게시, tap 수정 및 실제 Mac 설치·입력 테스트는 이번 CI 검증에 포함하지 않습니다.
