# 배포 전 확인 사항

이 저장소는 구름의 개인용 비공식 빌드 도구입니다. 워크플로와 아래 산출물이
라이선스 검토의 완료나 배포 허가를 뜻하지는 않습니다.

- 구름의 정확한 커밋에 포함된 `COPYING`을 확인하고 바이너리에 필요한 고지를 유지합니다.
- `COPYING`이 별도로 다루는 로고·아이콘의 이용 및 재배포 조건을 확인합니다.
- libhangul-objc/libhangul, 다른 서브모듈, 실제로 resolve된 Swift 패키지와
  포함된 바이너리 구성 요소 각각의 조건을 확인합니다. LGPL의 소스 제공·수정·재링크
  등 해당하는 의무는 단순한 출처 링크나 라이선스 파일 복사만으로 해결되지 않을 수 있습니다.
- `source.tar.gz`에는 upstream/재귀 서브모듈/SPM checkout의 정확한 커밋에 있는
  추적 파일, Package.resolved, 빌드 변경 내역을 담습니다. 별도 바이너리 의존성의
  완전한 대응 소스나 모든 재링크 자료까지 확보했다는 뜻은 아닙니다.
- 앱 내부와 `licenses.tar.gz`에 발견된 원본 고지를 보존합니다. 파일명 기반 수집이므로
  누락 여부와 실제 포함 구성 요소를 사람이 검토해야 합니다.
- 공식 배포·승인·보증으로 오해되지 않도록 개인용 비공식 빌드임을 표시합니다.

공개 저장소의 Actions 산출물도 접근 가능한 사용자에게 다운로드될 수 있습니다.
`publish_release=false`는 Release 게시를 막는 옵션이며, 비공개 보관을 보장하지 않습니다.
처음 실행하기 전에도 저장소 공개 범위와 포함 자료의 조건을 확인하세요.

## 서명·설치·동작

앱은 Apple 개발자 인증서 없이 ad-hoc 서명합니다. 설치 패키지는 unsigned이며,
공증과 hardened runtime은 사용하지 않습니다. macOS의 Gatekeeper·입력 모니터링 권한을
자동으로 해제하거나 변경하지 않습니다. `Gureum.app`의 번들 ID와 설치 경로는 upstream과
같아 공식 설치본과 공존하지 않으며, 설치·업데이트 시 이를 교체합니다.

설치 전에는 OS 기본 입력기로 바꾸고 설치 후 로그아웃/로그인하세요. 교체 후
입력 모니터링 권한을 다시 승인해야 할 수 있습니다. `Gureum.app`을 직접 실행하지 마세요.
단위 테스트와 서명·아키텍처 검사가 실제 입력기 동작 검증을 대체하지는 않습니다.
TextEdit와 Terminal 등 실제 사용할 앱에서 별도로 확인해야 합니다.

upstream 앱 로직은 변경하지 않습니다. 빌드 옵션으로 arm64, macOS 11 배포 대상,
숫자 버전과 ad-hoc 서명을 지정합니다. 포함된 universal Swift 런타임은 arm64 slice를
남기고 재서명하며, Preferences 번들에는 upstream entitlement를 명시해 서명합니다.
Firebase 초기화·Crashlytics 등 upstream의 네트워크/진단 동작은 제거하거나 별도
개인 서비스로 바꾸지 않습니다.

## 참고

- [Upstream COPYING](https://github.com/gureum/gureum/blob/main/COPYING)
- [Upstream 개발 안내](https://github.com/gureum/gureum/blob/main/HACKING.md)
- [libhangul-objc COPYING](https://github.com/gureum/libhangul-objc/blob/gureum/COPYING)
