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
초기 설정 완료 시 로컬 단위 테스트는 12개이며 모두 통과했습니다. 추가한 테스트는 체크섬을 다시
계산해도 앱 안의 원본 SHA가 metadata와 다르면 산출물 검증이 실패하는지 확인합니다.
CI에서 앱·소스 압축 파일의 메타데이터/lockfile, 고지 파일, cask와 전체 체크섬을
검증하고 unsigned pkg를 펼쳐 앱 서명과 내장 메타데이터를 재검증하도록 보강했습니다.
별도 코드 리뷰에서 CURRENT_PROJECT_VERSION에 SHA를 넣으면 생성 C 코드가 깨질 수 있음을
확인해 숫자 bundle/build 버전과 SHA release/cask 버전을 분리했습니다.
Resources 안의 Preferences.prefPane은 별도로 서명·entitlement를 검사합니다.

이 검사는 워크플로·보조 코드의 검증입니다. upstream CI 성공은 이 저장소의 별도
Release 빌드/서명/패키징이 성공했다는 증거가 아닙니다.

## 별도로 남은 검사

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

## 네 번째 실제 Actions 실행

- [실행 37095131394](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37095131394),
  builder `59aa8311333df5e88053d331bb15ddc61ae0c35f`.
- 명시적으로 재서명해도 Preferences entitlement 출력은 0바이트였고 같은 검사에서 실패했습니다.
  복사 과정만의 문제가 아니었습니다. Apple의 현재 코드 서명 구현은 main executable이
  아닌 Mach-O 라이브러리/번들에 entitlement를 넣으려면 별도 옵션을 요구합니다.
  [Apple SecCodeSigner.h](https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/SecCodeSigner.h)의
  `kSecCodeSignerForceLibraryEntitlements` 설명과
  [signer.cpp](https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/signer.cpp)의
  `mainBinary || state.mForceLibraryEntitlements` 조건을 확인했습니다.
- Preferences 서명에 `--force-library-entitlements`를 추가합니다. 비용이 큰 Xcode 빌드
  전에 작은 arm64 Mach-O bundle을 실제로 서명하고 원본 entitlement와 비교하는 검증도
  추가해 이 전제조건을 먼저 확인합니다. 실제 Preferences의 서명·entitlement 검사는 유지합니다.
- 진단 artifact 저장소 접근은 이후 정상화돼 앞선 실행들의 파일을 직접 확인했습니다.

## 다섯 번째 실제 Actions 실행과 산출물 확인

- [실행 37095756497](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37095756497),
  builder `9d3fa75f8ea02c98fd5575c79cd9c2454d393103`: 성공.
- Mach-O library 서명 사전 검사, upstream Debug 테스트 45개(실패 0개), Release 빌드,
  5개 Mach-O의 arm64 검사, 앱·Preferences의 원본 entitlement/서명 검사가 통과했습니다.
  unsigned pkg를 펼친 앱의 서명 검증, cask Ruby 구문 검사, artifact 업로드도 성공했습니다.
- artifact를 내려받아 파일 10개, 체크섬 9개, 앱·소스 내장 metadata/lockfile,
  cask와 app tarball SHA256의 일치를 확인했습니다. 앱 archive의 실행 권한과
  프레임워크 심볼릭 링크도 보존됐습니다.
- 확인 중 최소 OS 계산 오류를 발견했습니다. Swift concurrency 런타임의 macOS
  `LC_BUILD_VERSION`(platform 1, minos 11.0)과 Mac Catalyst 대상(platform 6, minos 14.0)을
  함께 읽어 metadata/cask가 macOS 14.0을 요구했습니다. 실제 macOS 대상은 11.0입니다.
  [Apple Mach-O loader.h](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h)의
  플랫폼 상수를 확인했으며, macOS 대상과 legacy `LC_VERSION_MIN_MACOSX`만 읽도록 수정합니다.
- 플랫폼 구분과 malformed load command에 대한 단위 테스트를 추가했습니다.
  앱 Info.plist의 `LSMinimumSystemVersion`도 계산된 macOS 요구 버전과 맞추고,
  metadata·압축 앱·cask가 이를 일관되게 사용하도록 검증합니다. 이 수정으로 재실행합니다.

전체 SHA 입력 경로는 Linux에서 지원 스크립트를 실제 실행해 확인했습니다.
`46c62e51a311c89ee084ce14eb8071b6d81f765d`의 공식 main 조상 확인, 재귀 서브모듈
체크아웃, 숫자 bundle 버전 `1.0.1`과 전체 원본 SHA의 분리 기록이 성공했습니다.

## 최종 검증 결과

- [실행 37096433424](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37096433424): 성공.
  검증한 builder는 `a8403efd7a8128ac44adabcccc1100e0c797f577`,
  실제 upstream은 `46c62e51a311c89ee084ce14eb8071b6d81f765d`입니다.
- macOS 26.6.2 arm64 / Xcode 26.6 / macOS SDK 26.5에서 지원 코드 테스트 12개,
  Mach-O bundle 서명 사전 검사, upstream Debug 테스트 45개(실패 0개), Release 빌드 성공.
- 최종 Mach-O 5개가 모두 arm64이며, 앱·Preferences의 원본 entitlement와 ad-hoc
  서명, 포함 프레임워크 서명, pkg를 펼친 앱 서명이 유효했습니다. pkg는 `Status: no signature`입니다.
- [스냅샷 artifact](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37096433424/artifacts/11265050808):
  `gureum-snapshot-37096433424-1`. 앱 tar.gz, unsigned pkg, source tar.gz, 라이선스 고지,
  Package.resolved, metadata, SHA256SUMS, 릴리스 노트 및 cask 예제까지 파일 10개입니다.
  다운로드 후 체크섬 9개, 앱·소스에 내장한 metadata/lockfile과 cask 체크섬을 다시 확인했습니다.
- 앱 선언·metadata·cask의 최소 macOS는 모두 `11.0`, 숫자 Apple 버전은 `1.0.1`입니다.
  arm64 slice 안의 Mac Catalyst 대상 값은 최소 macOS 계산에서 제외합니다.
  앱 tarball의 실행 권한 `0755`와 프레임워크 심볼릭 링크 6개도 보존됐습니다.
- 앱 tar.gz SHA256: `a88d6022b289b6e499f7c86db0fee944111f7171e803df3b4e078494b6f494fa`
- unsigned pkg SHA256: `8cc1ceb4ba1a38d8ae2bfa22be7df34dba346e40a3523877290730c9ca21c745`
- [진단 artifact](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37096433424/artifacts/11264841616)에
  Xcode 로그, xcresult, 서명·entitlement·아키텍처 검사 및 패키지 검사 결과를 보관합니다.
  스냅샷 artifact는 2026-10-17 13:33 KST까지(14일), 진단 artifact는 7일 보관입니다.
- 로컬 Python/Bash 검사, ShellCheck 0.11.0, actionlint 1.7.12와 단위 테스트 12개가 통과했습니다.

이번 설정 요청의 artifact 생성·다운로드 검증은 완료했습니다. Release job은 건너뛰었으며
기존 Release/태그/산출물을 덮어쓰거나 삭제하지 않았습니다. tap도 변경하지 않았습니다.
Release 게시, tap 수정 및 실제 Mac 설치·입력 테스트는 이번 CI 검증에 포함하지 않습니다.

## 스냅샷 표시 버전 추가

2026-10-03 upstream main, 모든 태그와 Release 목록을 다시 확인했습니다.
`OSX/Version.xcconfig`는 `// Do not commit this file`만 있는 생성용 파일이며,
프로젝트 빌드 단계는 `git describe --tags`에서 버전을 만듭니다.
실제 describe는 `1.13.2-27-g46c62e5`, 가장 가까운 태그와 최신 stable Release는
`1.13.2`입니다. 차기 버전을 지정한 파일·태그·릴리스가 없어 임의 증가 없이
`1.13.2-snapshot`으로 표시합니다. 명시적 숫자 버전 파일이 있으면 그 근거를 우선합니다.

버전 필드는 각각 관리합니다.

- [CFBundleShortVersionString](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundleshortversionstring):
  점으로 구분한 세 개의 숫자 버전이므로 `1.13.2`로 유지합니다.
- [CFBundleVersion](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html):
  숫자 빌드 버전입니다. Apple이 문서화한 개발 접미사는 `d`, `a`, `b`, `fc`이며
  임의의 `-snapshot`은 해당하지 않습니다. 기존 revision 규칙의 `1.0.1`을 유지합니다.
- pkgbuild/productbuild: component/product 버전은 숫자 빌드 버전 `1.0.1`입니다.
  pkgbuild/productbuild의 `--version`은 버전 문자열을 받으며 CFBundleShortVersionString과
  같은 세 숫자 필드 제약으로 단정하지 않습니다. 문서는 `-snapshot` 접미사의 비교 순서를
  보장하지 않으므로 이번 빌드에서는 숫자 버전을 사용합니다. suffix를 가진 pkg의 실제
  설치·업그레이드/다운그레이드 동작은 검증하지 않았습니다.
  PackageInfo/Distribution의 실제 XML과 포함 앱의 두 버전 필드를 검사합니다.
- 사용자 표시는 `PersonalSnapshotVersion`·`CFBundleGetInfoString`과 앱 정보 창의
  `applicationVersion` 옵션으로 분리합니다. 숫자 필드 전체 문자열 치환은 하지 않습니다.
- 파일명과 cask의 comma-separated 버전에 표시 버전과 전체 SHA를 함께 넣고,
  기존 SHA 기반 Release 태그와 revision 규칙을 유지합니다.

upstream `Bundle.version`은 CFBundleVersion을 읽습니다. UpdateManager의 자동 알림과
GureumMenu의 수동 확인은 공식 feed와의 문자열 불일치를 기준으로 동작합니다.
해당 접근자·업데이트 조회·비교·설정은 수정하지 않습니다. About panel에 전달하는
표시 옵션만 overlay로 수정하며, 빌드 후 보호 대상 파일의 git diff가 없는지 검사합니다.
`Configuration.updateMode`는 주 알림 설정이 false면 nil을 반환하므로 README의
알림 해제 방법은 Preferences.xib의 실제 체크박스 문구와 해당 코드에 근거합니다.

라이선스·LGPL 재링크 자료·로고/아이콘 이용 조건의 추가 검토는 다음 작업으로 남습니다.
이번 버전 변경과 기존 고지 보존은 라이선스 검토 완료나 배포 권한 확인을 뜻하지 않습니다.

### 표시 버전 첫 실제 실행과 수정

- [실행 37099517668](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37099517668),
  builder `691e1d4228ce0732421f69cb9b4b75aa39dc709d`.
- 지원 테스트 16개, upstream Debug 테스트 45개(실패 0개), Release 빌드,
  숫자/표시 버전과 앱·Preferences의 ad-hoc 서명/entitlement 검사가 통과했습니다.
- productbuild는 pkg를 생성했지만 내부 `PackageInfo` component 버전이 metadata의
  `1.0.1`과 달라 실제 산출물 검증에서 중단했습니다. `productbuild --version`은 product의
  버전을 지정하며 자동 생성 component의 버전을 함께 지정하는 옵션이 아니었습니다.
- `pkgbuild --version`으로 component를 따로 만들고 `productbuild --version --package`로
  product를 생성하도록 수정합니다. requirements plist로 기존 arm64/최소 macOS 조건을
  명시하고 Distribution의 실제 조건과 설치 경로도 검사합니다.
- pkg XML을 진단 artifact에 보존하고, 검증 helper의 부수 출력으로 JSON 검사 결과가
  깨지지 않도록 수정했습니다. 로컬 회귀 테스트와 정적 검사 후 다시 실행합니다.
- [productbuild man page 미러](https://github.com/keith/xcode-man-pages/blob/main/docs/productbuild.1.html)의
  product-version, package, product requirements 옵션을 확인했습니다. 실제 러너의
  pkgbuild/productbuild man page도 진단 artifact에 보존합니다.
- 실패한 실행은 스냅샷 artifact 업로드와 Release 게시를 건너뛰었습니다.

### 표시 버전 최종 검증 결과

- [성공 실행 37100051527](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37100051527),
  검증한 builder `a8f74d245654960c6b7f2692db4d5a6e7f0c8b09`.
- 실제 upstream `46c62e51a311c89ee084ce14eb8071b6d81f765d`, 근거 `1.13.2-27-g46c62e5`.
  표시 `1.13.2-snapshot`, CFBundleShortVersionString `1.13.2`,
  CFBundleVersion/CURRENT_PROJECT_VERSION 및 pkg component/product `1.0.1`.
- 지원 단위 테스트 16개, upstream Debug 테스트 45개(실패 0개), Release 빌드 성공.
  표시용 About overlay가 실제로 컴파일됐습니다. 실제 Mac의 정보 창을 직접 열어 확인하거나
  설치·입력 동작을 테스트한 것은 아닙니다.
- Mach-O 5개 모두 arm64, 앱·Preferences 원본 entitlement와 ad-hoc 서명 검증,
  포함 프레임워크 서명, pkg를 펼친 앱 서명 검증 성공. pkg는 `Status: no signature`, 공증 없음.
- PackageInfo의 component 버전과 Distribution의 product/pkg-ref 버전은 모두 `1.0.1`.
  설치 경로 `/Library/Input Methods`, relocatable=false, arm64 및 최소 macOS `11.0` 확인.
  cask Ruby 구문과 생성된 artifact-inspection.json의 JSON 형식도 정상입니다.
- [스냅샷 artifact](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37100051527/artifacts/11266300212):
  `gureum-snapshot-37100051527-1`, 10개 파일. 2026-10-17 14:35:51 KST까지 보관.
  다운로드 후 체크섬 9개와 앱·Preferences·소스의 버전/metadata/lockfile,
  cask tarball checksum, pkg XML까지 다시 검증했습니다.
- 파일 stem:
  `Gureum-1.13.2-snapshot-46c62e51a311c89ee084ce14eb8071b6d81f765d-arm64`.
  app tar.gz, unsigned.pkg, source.tar.gz가 같은 stem을 사용합니다.
- 앱 tar.gz SHA256: `c79d2cd2fe553687ff6e071ff1137512f30efed2e8e65bcecf4e387255435541`
- unsigned pkg SHA256: `7b9f576c342869eb8878d99d2e6bfd454deef1d96996f7c5ec94bc67c127f338`
- source tar.gz SHA256: `18274ce334f4b8b19a027a7c41befd0e97de66d05aa3cb5e00f2644b101c3bc1`
- [진단 artifact](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37100051527/artifacts/11265304653)는
  7일 보관되며 실제 pkg XML, pkgbuild/productbuild man page, Xcode 로그와 xcresult,
  서명·entitlement·아키텍처 검사를 포함합니다.
- 소스 archive의 변경 diff는 GureumMenu의 About 표시와 생성된 Version.xcconfig뿐입니다.
  Bundle.version, UpdateManager, 업데이트 설정 코드는 변경하지 않았습니다.
- 로컬 Python/Bash 검사, ShellCheck 0.11.0, actionlint 1.7.12 및 단위 테스트 16개 통과.
  기존 README의 개인용 목적과 사용 안내·면책 문구를 원문과 대조해 보존했습니다.

Release job은 건너뛰었고 tap과 기존 산출물은 변경하지 않았습니다.
라이선스 추가 검토, 실제 Mac 설치·입력 및 Homebrew 설치 테스트는 다음 작업으로 남습니다.
이 결과 기록 이후의 문서 커밋은 위 검증한 builder 코드와 구분합니다.
