# gureum-personal-snapshots

[구름 입력기](https://github.com/gureum/gureum)의 특정 커밋을 직접 빌드하고 사용하기 위한 개인용 비공식 스냅샷 저장소입니다. 공식 릴리스 사이의 변경 사항을 개인 환경에서 확인하고, 설치와 업데이트를 편하게 관리하려고 만들었습니다.

## 현재 상태

수동 실행 전용 GitHub Actions 워크플로와 빌드·패키징 스크립트가 있습니다.
구름 소스 코드나 바이너리를 이 저장소에 직접 커밋하지 않습니다.

- 공식 `gureum/gureum`의 `main` 또는 `main`에 속한 전체 커밋 SHA를 빌드
- Apple Silicon(arm64), Xcode 26.6, `OSX` scheme 사용
- 빌드 옵션으로 macOS 배포 대상을 11.0으로 지정해 Intel 전용 구형 Swift 런타임 포함 방지
- 포함된 universal Swift 런타임은 arm64 slice를 남기고 ad-hoc 재서명한 뒤 검사
- Debug 단위 테스트 후 Release 빌드, ad-hoc 서명·아키텍처·entitlement 검사
- 앱 `.tar.gz`, unsigned `.pkg`, 소스 묶음, 라이선스 고지, SHA256, cask 예제 생성
- 압축 파일의 내장 SHA·메타데이터·lockfile과 체크섬 확인, pkg를 펼쳐 앱 서명 재검증
- 기본값은 Actions 산출물 보관이며, 검토 후 직접 선택해야 GitHub prerelease 게시
- Homebrew tap 업데이트는 수동으로 진행하며 이 워크플로는 tap에 쓰지 않음

2026-10-03 [실제 Actions 실행](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37100051527)에서
upstream `46c62e51a311c89ee084ce14eb8071b6d81f765d`의 지원 테스트 16개·Debug 테스트 45개, Release 빌드,
arm64·ad-hoc 서명·패키징 검증과 산출물 업로드가 성공했습니다. 다운로드한 파일 10개와
체크섬 9개도 확인했습니다. 표시 버전은 `1.13.2-snapshot`, 앱 short 버전은 `1.13.2`,
build/pkg 버전은 `1.0.1`입니다. 이 산출물의 앱 선언·metadata·cask·installer는 macOS 11.0 이상을
요구합니다. [스냅샷 artifact](https://github.com/blood72/gureum-personal-snapshots/actions/runs/37100051527/artifacts/11266300212)는
14일 보관됩니다.
실제 Mac 설치와 입력기 동작은 별도로 검증해야 합니다.
구현 일정, 빌드 주기, 지속적인 배포나 지원은 약속하지 않습니다.

## 실행 전 필요한 것

1. 이 저장소에서 GitHub Actions와 `actions/checkout`, `actions/upload-artifact`,
   `actions/download-artifact` 실행이 허용되어 있어야 합니다. Actions는 커밋 SHA로 고정했습니다.
2. GitHub-hosted `macos-26` arm64 러너와 `/Applications/Xcode_26.6.app`을 사용합니다.
   러너 이미지에서 해당 Xcode가 사라지면 워크플로의 경로를 검토해 변경해야 합니다.
3. 빌드에는 별도 PAT, Apple 개발자 인증서, 공증 시크릿이 필요하지 않습니다.
   기본 `GITHUB_TOKEN`은 읽기 전용이며, 명시적으로 선택한 게시 job만 이 저장소의
   `contents: write` 권한을 요청합니다. 저장소·조직 정책이 이를 허용해야 게시할 수 있습니다.
4. 처음 실행하기 전에도 [배포 전 확인 사항](docs/DISTRIBUTION.md)을 읽어야 합니다.
   공개 저장소의 Actions 산출물은 비공개 저장소가 아닙니다. `publish_release=false`만으로
   바이너리나 소스가 외부에 공개되지 않는다고 가정하면 안 됩니다.

로컬 Mac의 Xcode나 Homebrew 사전 설치는 GitHub Actions 실행에 필요하지 않습니다.
실제 설치 대상은 Apple Silicon Mac입니다. cask의 최소 macOS 버전은 앱과 포함된 Mach-O의
macOS 배포 대상 중 가장 높은 값(최소 macOS 11)으로 앱 선언·metadata·cask를 맞춥니다.
Mac Catalyst/iOS 대상 값은 제외하며, 실행 중 API 호환성까지 보장하지는 않습니다.

## 수동 실행

Actions → **Build Gureum personal snapshot** → **Run workflow**에서 실행합니다.

- `upstream_ref`: `main` 또는 40자리 전체 SHA. 태그, 임의 브랜치, fork 커밋은 받지 않습니다.
  SHA가 실행 시점 공식 `main`의 조상이 아니면 중단합니다.
- `build_revision`: 기본 `1`. 동일 SHA를 다시 배포해야 하면 `2`, `3` 등으로 올립니다.
- `publish_release`: 기본 `false`. 테스트·빌드 후 Actions 산출물만 받으려면 그대로 둡니다.
- `distribution_reviewed`: 기본 `false`. 소스·제3자 구성 요소·로고·아이콘과 적용되는
  재배포 의무를 검토한 뒤 게시할 때만 선택합니다. 이 체크가 검토 자체를 수행하지는 않습니다.

Release 게시에는 마지막 두 옵션 모두 `true`가 필요하며 이 저장소의 `main`에서만 허용합니다.
`push`, PR, cron으로 실행하거나 자동 배포하지 않습니다.

성공한 실행의 `gureum-snapshot-<run id>-<attempt>`에서 산출물을 받을 수 있습니다.
보관 기간은 14일이고 진단 로그·테스트 결과는 7일입니다. 빌드 실패 시에도 가능한 진단 자료를 남깁니다.

## 산출물과 버전

표시용 버전은 소스의 `X.Y.Z`에 `-snapshot`을 붙입니다. 명시적인 숫자
`OSX/Version.xcconfig`가 있으면 그 값을 사용하고, 현재처럼 생성용 빈 파일이면 upstream의
`git describe --tags`가 선택하는 가장 가까운 태그에서 기본 버전을 읽습니다.
모르는 형식이면 중단하며, 커밋이 추가됐다는 이유만으로 차기 버전을 추정하지 않습니다.

2026-10-03 확인한 main은 `1.13.2-27-g46c62e5`입니다. 최신 공식 stable Release도
[`1.13.2`](https://github.com/gureum/gureum/releases/tag/1.13.2)이며, 버전 파일·전체 태그·릴리스에서
차기 버전을 확정할 근거가 없어 **`1.13.2-snapshot`**을 적용합니다.
이는 공식 차기 버전명이나 공식 릴리스가 아닙니다. 판단 근거는 `metadata.json`의
`version_evidence`에 기록합니다.

| 용도 | 기본 revision 1 값 | 관리 방식 |
| --- | --- | --- |
| 사람에게 표시하는 버전 | `1.13.2-snapshot` | 앱 정보 창, `CFBundleGetInfoString`, `PersonalSnapshotVersion`, 문서 |
| `CFBundleShortVersionString` | `1.13.2` | 소스 기본 버전의 세 숫자, 접미사 없음 |
| `CFBundleVersion` / `CURRENT_PROJECT_VERSION` | `1.0.1` | `1.<revision // 100>.<revision % 100>`, 빌드 식별용 숫자 |
| pkg component / product 버전 | `1.0.1` | 숫자 빌드 버전, 생성한 PackageInfo/Distribution 검증 |
| cask 버전 | `1.13.2-snapshot,<전체 SHA>` | 표시 버전과 원본 식별을 함께 보존 |
| Release 태그 | `snapshot-<전체 SHA>` | 원본 SHA로 불변 식별, 태그 대상은 빌드 도구 저장소 커밋 |

revision 2부터 cask의 SHA 부분·Release 태그·파일명의 SHA 뒤에 `-r2`를 붙입니다.
표시 버전과 소스 기본 버전은 그대로이고 숫자 빌드/pkg 버전은 `1.0.2`가 됩니다.
Apple의 숫자 버전은 공식 버전과의 시간순 비교를 뜻하지 않습니다.
전체 SHA는 `PersonalSnapshotUpstreamSHA`, 내장/외부 metadata, 소스 묶음과 파일명에도 보존합니다.
앱 정보 창만 표시용 키를 읽도록 작은 빌드 overlay를 적용하며 변경 diff를 소스 묶음에 기록합니다.
`Bundle.version`과 공식 업데이트 기능은 변경하지 않습니다. 따라서 업데이트 대화상자의
현재 버전 표시는 upstream이 읽는 숫자 `CFBundleVersion`입니다.

- `Gureum-1.13.2-snapshot-<전체 SHA>[-rN]-arm64.app.tar.gz`: ad-hoc 서명된 `Gureum.app`
- 같은 stem의 `.unsigned.pkg`: 같은 앱을 `/Library/Input Methods`에 설치
- 같은 stem의 `.source.tar.gz`: 정확한 소스/서브모듈/SPM checkout 및 빌드 정보
- `metadata.json`, `Package.resolved`, `licenses.tar.gz`, `DISTRIBUTION.md`
- `SHA256SUMS`, `RELEASE_NOTES.md`, `gureum-snapshot.rb`

## 공식 업데이트 알림

upstream의 [UpdateManager](https://github.com/gureum/gureum/blob/46c62e51a311c89ee084ce14eb8071b6d81f765d/OSX/UpdateManager.swift)는
공식 `gureum.io` 버전 정보와 `CFBundleVersion`을 읽어 **문자열이 서로 다르면** 자동 알림을
보냅니다. 더 최신인지를 비교하지 않습니다. 이 빌드의 `1.0.1`은 공식 버전과 다를 수 있으므로
스냅샷에서도 공식판 안내가 나타날 수 있습니다. 차기 버전이나 `-snapshot` 표기를 적용하는
것만으로 이 문제가 해결되지는 않습니다. 공식판 안내는 개인 스냅샷 업데이트나 새 SHA의
존재를 뜻하지 않으며, 안내 링크는 공식 배포 경로입니다.

자동 알림을 끄려면 구름 입력기 메뉴의 **환경설정**을 열고 **업데이트 설정**의
**“업데이트 알림을 받겠습니다”** 체크를 해제하세요. 실험 버전 체크만 해제하면 stable
알림은 계속될 수 있습니다. 주 체크를 해제하면 실험 버전을 포함한 자동 조회/알림이
중단됩니다. 메뉴의 수동 **업데이트 확인**·**최신 실험 버전 확인**은 별도이므로 계속
공식 서버를 조회할 수 있습니다. 설정 기본값과 공식 업데이트 코드는 바꾸지 않았습니다.

Release는 draft 상태로 파일을 올려 이름·크기·가능한 서버 체크섬을 확인한 후 prerelease로
게시하며 latest로 지정하지 않습니다. 기존 태그·draft·Release는 수정하거나 덮어쓰지 않습니다.
업로드 중 실패하면 draft가 남을 수 있습니다. 해당 상태를 직접 확인하고 같은 소스를 새로 빌드하려면
revision을 올리세요. 기존 Release를 유지할 때는 그 Release에 첨부된 cask와 체크섬을 사용해야 합니다.

SPM lockfile이 upstream에 커밋되어 있지 않아 **같은 upstream SHA라도 나중에 resolve되는
의존성이 달라질 수 있습니다.** 생성된 lockfile과 실제 checkout 커밋을 보존하지만 비트 단위
재현 빌드를 보장하지 않습니다. 다른 결과물을 배포하려면 revision을 올립니다.

## Homebrew tap에 연결

해당 Release가 게시되고 배포 조건을 검토한 뒤 첨부된 `gureum-snapshot.rb`를 원하는 tap의
`Casks/gureum-snapshot.rb`에 수동으로 반영합니다. cask에는 해당 릴리스의 정확한 tarball URL과
SHA256이 들어갑니다. Actions 산출물만 만든 경우 이 Release URL은 아직 존재하지 않습니다.
다른 cask가 함께 있는 일반 개인 tap에서도 사용할 수 있는 독립된 cask 예제입니다.

공식 `gureumkim` cask와 충돌하도록 표시하며, 같은 앱 이름·번들 ID·설치 경로를 사용합니다.
설치·업데이트 전 기본 입력기로 전환하고, 이후 로그아웃/로그인하세요.
서명·보안·실제 입력기 확인에 관한 내용은 [배포 전 확인 사항](docs/DISTRIBUTION.md)을 참고하세요.

## 개발과 검증

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
for script in scripts/*.sh; do bash -n "$script" || exit; done
shellcheck scripts/*.sh
actionlint .github/workflows/gureum-snapshot-release.yml
```

Actions 산출물을 다운로드한 뒤 저장소 루트에서 다음 명령으로 파일 구성, 체크섬,
앱·소스의 내장 메타데이터와 cask를 확인할 수 있습니다. `<builder SHA>`는 해당 실행의
빌드 도구 커밋 전체 SHA입니다. 이 검사는 Linux에서도 가능하며 Mac 설치 테스트는 아닙니다.

```sh
python3 scripts/verify-artifacts.py /path/to/downloaded/artifact '<builder SHA>'
```

위 정적 검사와 단위 테스트는 macOS 빌드가 아닙니다. 실제 Xcode 테스트, Release 빌드,
서명·패키지·설치 확인은 별도로 실행해야 합니다. 상세 검증 기준과 근거는
[개발 메모](docs/VALIDATION.md)에 있습니다.

## 사용 안내

개인적인 사용 편의를 위한 저장소이며, 다른 사용자에게 적극적으로 사용을 권장하기 위한 목적은 없습니다. 일반적인 사용에는 [구름 공식 릴리스](https://github.com/gureum/gureum/releases)를 권장합니다.

이 저장소는 구름 프로젝트와 독립적으로 운영되며, 공식 배포처가 아니고 원 개발자의 승인·보증·지원을 뜻하지 않습니다. 향후 제공될 스냅샷은 충분히 검증되지 않은 변경 사항을 포함할 수 있으므로 사용 여부와 위험은 사용자가 직접 판단해야 합니다.

## 라이선스와 권리

구름과 그 의존성, 로고·아이콘의 권리는 각 권리자에게 있습니다. 이 저장소는 해당 구성 요소의 라이선스를 변경하거나 새로운 권한을 부여하지 않습니다.

- 구름의 사용·재배포 조건은 [upstream COPYING](https://github.com/gureum/gureum/blob/main/COPYING)을 따릅니다. 이 문서에는 로고와 아이콘에 별도 라이선스가 적용된다고 명시되어 있으므로, 배포 전에 해당 조건을 따로 확인해야 합니다.
- [libhangul-objc의 LGPL 2.1](https://github.com/gureum/libhangul-objc/blob/gureum/COPYING) 등 실제 빌드에 포함되는 제3자 구성 요소의 라이선스도 각각 적용됩니다. 단순한 출처 표기만으로 모든 의무를 충족하는 것은 아니며, 소스 제공 등 적용되는 조건을 확인해야 합니다.
- 바이너리를 배포하기 전에는 사용한 정확한 소스와 구성 요소를 기준으로 저작권·라이선스 고지 및 그 밖의 배포 의무를 충족해야 합니다. 현재 README는 그 검토가 완료되었다는 선언이 아닙니다.

현재 별도의 저장소 전체 `LICENSE`는 두지 않습니다. 이 선택은 upstream이나 제3자 자료의 기존 라이선스에 영향을 주지 않습니다.

## 보증과 책임

이 저장소의 자료 및 향후 스냅샷은 적용 법률이 허용하는 범위에서 있는 그대로 제공하며, 안정성·호환성·특정 목적에 대한 적합성을 보증하지 않습니다. 사용에 따른 위험은 사용자가 부담하며, 관리자는 적용 법률이 허용하는 범위에서 그로 인한 손해에 책임을 지지 않습니다.
