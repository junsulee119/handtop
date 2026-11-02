# Handtop Comprehensive Codebase Audit

> 감사 기준일: 2026-10-30 (Asia/Seoul)  
> 대상 커밋: **6ef72a9535f4ff0b5767068a4045ad4155ed964e**  
> 대상 배포물: **Handtop v0.3.5, DDR3 / DDR4**  
> 보고서 언어: 한국어  
> 수행 범위: 현재 PC에서 가능한 정적 분석, 배포 이미지 읽기 전용 분석, 하드웨어 없는 재현  
> 상태: **검토 완료 (Reviewed)**, 2026-11-02, Claude. 검토 의견은 [9장](#review) 참고

## 1. 감사 개요

Handtop의 주요 모듈과 의존성을 검토한 결과, **High 2건, Medium 13건, Low 3건으로 총 18건의 코드·구성 문제**를 확인했다. Critical로 확정할 근거는 발견하지 못했다. 적용 조건이나 실행 경로를 더 확인해야 하는 의존성 보안 권고는 별도 후보로 분리했다.

소스 코드와 배포 이미지 원본은 변경하지 않았다. 수정 커밋, PR 생성, 배포, 실기기 제어는 수행하지 않았다. 감사 완료 시 Git 작업 트리는 깨끗했다.

### 1.1 기준 및 무결성

- 기준 저장소: [junsulee119/handtop](https://github.com/junsulee119/handtop).
- 기준 커밋: [6ef72a9](https://github.com/junsulee119/handtop/commit/6ef72a9535f4ff0b5767068a4045ad4155ed964e).
- 분석 이미지:
  - handtop-20261029-v0.3.5-DDR3.img.xz
  - handtop-20261029-v0.3.5.img.xz
- 두 이미지의 SHA-256이 동봉된 체크섬과 일치했다.
- 두 이미지의 설치 패키지 목록은 각각 **809개**로 동일했다.
- 이미지별로 대조한 주요 실행 스크립트와 입력 모듈 **39개**는 저장소 소스와 일치했다.
- 두 이미지에서 추출한 내장 커널 설정도 동일했다.

본문의 소스 링크는 감사 기준 커밋으로 고정했다. 로컬 소스의 줄 번호와 동일한 기준이며, 이후 브랜치 변경과 구분된다.

### 1.2 확인 수준

| 표기 | 의미 |
|---|---|
| 재현 완료 | 실제 코드의 함수 또는 스크립트를 가짜 장치·소켓·명령으로 실행해 해당 결함을 확인 |
| 코드 경로 확인 | 조건에서 문제가 발생하는 호출·데이터·자원 수명 경로를 소스로 확인 |
| 배포물 확인 | 실제 배포 이미지의 파일·버전·메타데이터를 추출해 확인 |
| 실기기 검증 필요 | 무선·USB·커널·전원·화면에서의 최종 영향이나 발생 빈도는 실측하지 않음 |
| 추가 조사 후보 | 버전 또는 코드상 단서는 있으나 적용 조건·실행 경로가 불충분하여 확정 건수에서 제외 |

재현 완료는 RG35XX H에서의 재현을 의미하지 않는다. 실제 입력 장치, 진동 모터, GPIO, 무선 장치, USB gadget, 전원 상태를 변경하는 프로그램은 실행하지 않았다.

### 1.3 보안 판단 기준

일반 사용자에서 root로의 경계, 외부 Bluetooth·USB 입력, 로컬 IPC, FAT 설정 파일, 다운로드와 빌드 과정을 검토했다. 문서화된 편의 기능 자체를 취약점으로 판정하지 않고, 의도한 기능보다 넓은 승인 범위나 추가 영향이 있는지 구분했다.

기본 비밀번호와 자동 로그인은 문서화된 제품 동작으로 다뤘다. SSH가 기본적으로 비활성화된 점을 함께 고려했으며, 기본 비밀번호 존재만으로 별도 취약점을 추가하지 않았다.

## 2. 심각도별 요약

| 심각도 | 건수 | 주요 영향 |
|---|---:|---|
| Critical | 0 | 확정 근거 없음 |
| High | 2 | FFmpeg 보안 수정 누락, Bluetooth 승인 범위 초과 |
| Medium | 13 | 입력 상태 고착, 진동 정리 누락, 복구·종료 실패, 화면 배치 오류 |
| Low | 3 | 테스트 누락, 빌드 캐시 무효화 누락, 공백 경로 처리 오류 |

| ID | 심각도 | 발견 사항 | 확인 수준 |
|---|---|---|---|
| [H01](#h01) | High | FFmpeg 보안 수정 누락 및 패키지 메타데이터 불일치 | 코드·배포물 확인 |
| [H02](#h02) | High | Bluetooth 기본 에이전트의 과도한 승인·영구 신뢰 | 코드 경로 확인 |
| [M01](#m01) | Medium | Bluetooth 전송 실패 후 최종 입력 상태 재전송 누락 | 재현 완료 |
| [M02](#m02) | Medium | 게임패드 종료 후 대기 진동 요청 실행 | 재현 완료 |
| [M03](#m03) | Medium | 중복 L2CAP 채널 교체 시 이전 GLib watch 잔존 | 등록 누락 재현 |
| [M04](#m04) | Medium | 입력 설정의 숫자·불리언·키 이름 검증 부족 | 재현 완료 |
| [M05](#m05) | Medium | 입력 타이머 실패를 감지하지 못하는 watchdog | 실패 조건 재현 |
| [M06](#m06) | Medium | SYN_DROPPED 이후 입력 상태 재동기화 누락 | 재현 완료 |
| [M07](#m07) | Medium | grab 실패 장치를 게임패드·모터 소유자로 사용 | 재현 완료 |
| [M08](#m08) | Medium | USB 초기화 중 SIGTERM 처리·정리 누락 | 코드 경로 확인 |
| [M09](#m09) | Medium | 배율을 반영하지 않은 HDMI 확장 배치 | 재현 완료 |
| [M10](#m10) | Medium | UI 루프에 종속된 HDMI 자동 복귀 | 코드 경로 확인 |
| [M11](#m11) | Medium | 새 Wi-Fi 프로필 검증 전 기존 프로필 삭제 | 재현 완료 |
| [M12](#m12) | Medium | 세션 종료 시 Screen off 시스템 상태 미복원 | 코드 경로 확인 |
| [M13](#m13) | Medium | arm64 호스트에 x86_64 커널 도구 체인 선택 | 코드 경로 확인 |
| [L01](#l01) | Low | 이미지 빌드에서 입력 테스트 2개 누락 | 재현 완료 |
| [L02](#l02) | Low | 로컬 커널 패치 변경에 대한 캐시 무효화 누락 | 코드 경로 확인 |
| [L03](#l03) | Low | 공백이 있는 Wi-Fi 명령 경로 실행 실패 | 재현 완료 |

## 3. High 발견 사항

<a id="h01"></a>
### H01. FFmpeg 보안 수정이 빠진 바이너리를 최신 Debian 패키지로 표시하고 업데이트도 보류함

**분류:** 보안, 의존성 관리, 배포 추적성  
**확인 수준:** 코드와 배포물 확인. 악성 미디어 실행 및 실제 코드 실행은 미검증.  
**위치:** [build/config.sh:38][config-38], [build/04c-v4l2-ffmpeg.sh:93][ffbuild-93], [build/04c-v4l2-ffmpeg.sh:155][ffbuild-155].

**원인과 영향**

빌드가 fad85d9 기반 FFmpeg를 /usr에 직접 설치해 Debian 소유 파일을 덮어쓴다. dpkg는 여전히 7:7.1.5-0+deb13u1로 표시하며, 관련 라이브러리 8개는 hold 상태다. 패키지 버전만 검사하면 실제 코드의 패치 상태를 잘못 판단할 수 있고, 보안 업데이트도 자동 반영되지 않는다.

배포된 libavcodec에서 해당 기준 커밋의 식별자를 확인했고, dpkg의 원래 파일 체크섬과도 다름을 확인했다. 기준 소스에는 CVE-2026-8461 수정이 없다. 교체된 libswscale의 기준 소스에도 CVE-2026-38347 수정이 없다. 두 공식 수정 패치 모두 기준 소스에 변경 없이 적용되는 것을 확인했다.

**발생 조건 및 확인 근거**

- 영향받는 MagicYUV 디코더나 스케일러 경로로 조작된 미디어를 처리하는 경우다.
- 공식 권고는 메모리 경계 오류에 따른 충돌과 일부 경우 코드 실행 가능성을 설명한다.
- 기준 소스에 대한 패치 적용 검사를 수행했으며, 배포 바이너리를 대상으로 한 악성 입력 실행은 수행하지 않았다.
- libavformat 등 일부 라이브러리는 Debian 파일이 유지되어 있다. 모든 FFmpeg 라이브러리가 동일한 방식으로 교체됐다고 가정해서는 안 된다.

**수정 방안**

V4L2 Request API와 로컬 DRM 변경을 보안 수정이 반영된 기반으로 옮기고, 별도 버전의 Debian 패키지로 관리한다. 패키지 DB, 실제 바이너리, 소스 커밋, 적용 패치를 함께 추적하고 업데이트 경로를 마련한다. hold만 해제하면 하드웨어 디코딩이 사라질 수 있으므로 패키징과 업데이트 정책을 함께 바꿔야 한다.

**회귀 검증**

보안 수정 포함 여부, 실제 로드되는 라이브러리, apt 업그레이드 이후 상태를 확인한다. H.264·HEVC·MPEG-2·VP8 디코딩과 mpv·Moonlight 사용 경로를 실기기에서 확인한다.

**권고 및 보안 분류**

- [CVE-2026-8461 — Debian 보안 추적기](https://security-tracker.debian.org/tracker/CVE-2026-8461)
- [CVE-2026-38347 — Debian 보안 추적기](https://security-tracker.debian.org/tracker/CVE-2026-38347)
- [MagicYUV 수정 커밋](https://github.com/FFmpeg/FFmpeg/commit/15882781ac5267a653e4e55f5fa656ba9db688fd)
- [스케일러 수정 커밋](https://github.com/FFmpeg/FFmpeg/commit/bb88e295394e5db584063bde790bfbdba04d54ec)
- 관련 결함 유형: 메모리 경계 오류(CWE-125 / CWE-787), 실제 코드와 패키지 메타데이터의 불일치.

<a id="h02"></a>
### H02. 외부 컨트롤러의 Bluetooth 에이전트가 관계없는 서비스까지 승인하고 영구 신뢰함

**분류:** 보안, 권한 검증  
**확인 수준:** 코드 경로 확인. 실제 무선 공격과 입력 주입 영향은 실기기 검증 필요.  
**위치:** [rg35xxh-btpad:319][bt-319], [rg35xxh-btpad:846][bt-846], [rg35xxh-btpad:877][bt-877], [rg35xxh-switchbt:230][classic-230].

**원인과 영향**

컨트롤러용 에이전트를 시스템 기본 에이전트로 등록하고 AuthorizeService, RequestAuthorization, RequestConfirmation에서 기기나 서비스 UUID를 제한하지 않는다. BLE 구현은 임의 기기의 Paired=True 신호를 받으면 해당 기기를 Trusted=True로 설정한다.

의도한 게임패드 연결보다 승인 범위가 넓으며, 새 기기의 신뢰 상태는 모드 종료 후에도 남는다. 문제는 게임패드의 간편 페어링 자체가 아니라 관계없는 서비스와 기기까지 승인하는 범위다.

**발생 조건 및 확인 근거**

외부 컨트롤러 모드 중 새 기기가 페어링 또는 관계없는 서비스 승인을 요청하는 경우다. 코드에 선택된 상대나 요청 서비스에 대한 제한이 없다. BlueZ API에서는 빈 정상 응답이 승인을 의미한다.

BLE HID 기기를 통한 입력 주입 등 추가 영향은 실기기에서 확인해야 한다. 이번 감사에서 실제 입력 주입, 권한 상승 또는 원격 코드 실행을 수행한 것은 아니다.

**수정 방안**

현재 연결하려는 상대와 허용할 서비스·역할을 한정하고, 확인된 컨트롤러 상대만 신뢰로 등록한다. 모드가 끝났을 때 세션에 한정된 승인이 남지 않도록 한다. 새 기기 확인 단계를 추가한다면 기존 페어링 편의성에 미치는 영향을 결정해야 한다.

**회귀 검증**

알 수 없는 HID·오디오 서비스 요청, 기존 주변기기 재연결, 정상 Xbox BLE·Classic·Switch 페어링을 각각 검사한다. 모드 종료 후 신뢰 상태도 확인한다.

**권고 및 보안 분류**

- [BlueZ 공식 Agent API](https://bluez.readthedocs.io/en/latest/agent-api/)
- 관련 유형: 부적절한 권한 검증(CWE-863), 인증·승인 정책 범위 초과.

## 4. Medium 발견 사항

<a id="m01"></a>
### M01. Bluetooth 전송 실패를 성공으로 기록해 마지막 버튼 해제 상태를 잃음

**분류:** 입력 정확성, 전송 실패 처리  
**확인 수준:** 재현 완료. 실제 무선 환경의 발생 빈도는 미측정.  
**위치:** [rg35xxh-btpad:390][bt-390], [rg35xxh-btpad:235][bt-235], [rg35xxh-switchbt:607][classic-607].

**원인과 영향**

BLE flush()와 Classic Xbox의 _xbox_send()가 실제 전송 성공 전에 마지막 상태를 갱신한다. 전송이 EAGAIN으로 실패해도 같은 상태는 이후 전송 대상에서 제외된다. 상대 장치에서 버튼이나 스틱이 눌린 상태로 남을 수 있다.

**재현 조건과 결과**

마지막 버튼 해제 보고서의 첫 전송만 BlockingIOError로 실패시키고 같은 상태로 다시 호출했다. Classic 구현에서는 전송 시도 1회, 성공 0회였고 재전송되지 않았다. BLE 구현도 실패한 상태를 캐시해 같은 상태의 쓰기를 다시 시도하지 않았다.

**수정 방안**

전송 성공 후에만 캐시를 갱신한다. 실패한 최신 상태 하나를 보관하고 제한된 주기로 재시도한다. 성공 여부를 전달하도록 내부 전송 함수의 반환 규약을 정리할 필요가 있다. HID wire 형식 변경은 필요하지 않다.

**회귀 검증**

버튼 해제와 스틱 중앙 복귀에서 일시적인 EAGAIN을 주입한다. 후속 입력이 없어도 최종 상태가 전달되는지 확인한다.

<a id="m02"></a>
### M02. 게임패드 모드 종료 뒤 대기 중이던 진동 요청이 실행됨

**분류:** 자원 수명, 하드웨어 상태  
**확인 수준:** 재현 완료. 실제 모터는 구동하지 않음.  
**위치:** [daemon.py:408][daemon-408], [daemon.py:1056][daemon-1056].

**원인과 영향**

_destroy_pad()는 현재 등록된 효과는 정리하지만 motor_pending_upload, motor_pending_play와 예약된 motor 작업을 정리하지 않는다. 종료 직후 대기 작업이 새 효과를 업로드하고 재생할 수 있다.

**재현 조건과 결과**

업로드와 재생 요청을 큐에 넣고 가상 패드를 제거한 다음 _motor_flush()를 실행했다. 패드가 없는 상태에서 효과 업로드 1회와 재생 쓰기 1회가 발생했다.

**수정 방안**

모드를 떠날 때 해당 패드의 대기 요청과 예약 작업을 무효화한다. 이전 모드에서 생성한 작업이 뒤늦게 적용되지 않도록 작업의 소속이나 세대를 검사한다.

**회귀 검증**

업로드 직전, 재생 직전, 효과 갱신 중에 모드를 종료한다. 종료 뒤에는 새 효과가 생성되거나 재생되지 않고 모든 효과가 추적·정리되는지 확인한다.

<a id="m03"></a>
### M03. 중복 L2CAP 채널 교체 시 이전 GLib watch를 제거하지 않음

**분류:** 연결 수명, 예외 경로, 성능  
**확인 수준:** watch 등록·정리 누락 재현. 실제 GLib 부하와 무선 영향은 미측정.  
**위치:** [rg35xxh-switchbt:521][classic-521], [rg35xxh-switchbt:535][classic-535], [rg35xxh-switchbt:670][classic-670].

**원인과 영향**

두 채널이 모두 연결되기 전에는 같은 상대의 동일 PSM 연결을 다시 받아 기존 채널을 교체한다. 이전 watch는 남으며, 콜백은 전달받은 fd 대신 현재 self.ctrl 또는 self.itr를 읽는다. 오래된 watch와 현재 연결의 대응이 깨질 수 있다.

**재현 조건과 결과**

동일 control PSM을 두 번 연결하면 watch가 2개 등록되고 이전 watch 제거는 없다. 실제 소켓 객체를 사용한 보완 검사에서는 이전 소켓 객체가 GC로 정리됐다. 따라서 소켓 fd 누수로 단정하지 않으며, 확정된 결함은 watch 정리 누락이다.

**수정 방안**

PSM별 소켓과 watch를 함께 관리하고 교체 전에 이전 watch를 제거한다. 중복 채널과 반쪽 연결에 대해 일관된 제한과 만료 정책을 둔다.

**회귀 검증**

fd 재사용, 동일 PSM 반복 연결, 한 채널만 연결한 상태의 만료, 연결 도중 종료를 검사한다. 실제 GLib 환경에서 watch 개수와 CPU 사용도 확인한다.

**근거 해석 주의**

초기 가짜 소켓 결과의 duplicate_l2cap_channel_leaks라는 이름은 누수를 확정하는 근거가 아니다. [실제 소켓 보완 결과](audit-evidence-20261030/l2cap-watch-probe.json)를 우선한다.

<a id="m04"></a>
### M04. 입력 설정의 숫자·불리언·키 이름 검증이 부족함

**분류:** 설정 파싱, 예외 처리  
**확인 수준:** 재현 완료.  
**위치:** [config.py:38][input-config-38], [config.py:55][input-config-55], [core.py:324][core-324].

**원인과 영향**

숫자로 변환 가능한 값이면 범위와 유한성을 확인하지 않고 수용한다. 불리언 변환 오류는 잡지 않으며, 키 이름은 정규식만 검사한다. FAT 파티션의 설정 오타가 데몬 시작 실패나 입력 콜백 예외로 이어진다.

**재현 조건과 결과**

| 설정·입력 | 결과 |
|---|---|
| invert_lx=maybe | ValueError: Not a boolean |
| pointer_max_speed=inf 후 이동 | ValueError: cannot convert float NaN to integer |
| deadzone=1 후 대각선 입력 | ZeroDivisionError |
| key:KEY_DOES_NOT_EXIST | 설정에서 허용되고 존재하지 않는 키 액션이 생성됨 |

**수정 방안**

항목별 허용 범위, 유한성, 실제 지원 키를 검사한다. 잘못된 항목은 기본값으로 복구하고 사용자에게 보이는 로그를 남긴다. 설정 파서 오류와 변환 오류의 복구 범위를 통일한다.

**회귀 검증**

손상·누락 파일, BOM·CRLF, 잘못된 불리언, NaN·Inf, 경계값, 알 수 없는 키를 검사한다. 잘못된 설정 하나 때문에 전체 입력 제어가 사라지지 않아야 한다.

<a id="m05"></a>
### M05. 입력 처리 타이머가 죽어도 watchdog은 정상으로 판단함

**분류:** 장애 복구, 아키텍처  
**확인 수준:** 실제 함수의 실패 조건과 heartbeat 지속을 재현. GLib 처리 방식은 해당 버전 소스로 확인.  
**위치:** [daemon.py:568][daemon-568], [daemon.py:1143][daemon-1143], [daemon.py:1161][daemon-1161].

**원인과 영향**

입력 처리 _tick과 heartbeat가 별도 타이머다. _tick에서 처리되지 않은 예외가 발생해 타이머가 제거돼도 heartbeat는 계속 기록될 수 있다. 포인터 이동, 반복 처리, 길게 누르기 등이 멈추고 자동 재시작은 작동하지 않는다.

M04는 잘못된 값을 수용하는 검증 결함이고, 이 항목은 입력 처리만 실패한 상태를 정상으로 판단하는 복구 결함이다.

**재현 조건과 결과**

실제 _tick()에서 예외를 발생시킨 뒤 _heartbeat()를 두 번 호출했으며 카운터가 계속 증가했다. 배포된 python3-gi 버전은 3.50.0-4+b1이다. [해당 PyGObject 버전의 콜백 구현](https://raw.githubusercontent.com/GNOME/pygobject/3.50.0/gi/pygi-source.c)은 예외 발생 시 타이머가 제거되는 반환값을 사용한다.

**수정 방안**

성공한 입력 처리 주기에서 heartbeat를 갱신하거나, 예상 밖 입력 콜백 예외를 기록한 뒤 데몬을 정상 종료해 재시작하도록 한다. heartbeat는 입력 경로의 실제 진행을 나타내야 한다.

**회귀 검증**

메인 루프 전체 정지, 특정 타이머만 실패, 장치 콜백만 실패, suspend·resume를 구분해 검사한다. 실패 뒤 정상 정리와 재시작도 확인한다.

<a id="m06"></a>
### M06. SYN_DROPPED 이후 입력 상태를 재동기화하지 않음

**분류:** 입력 상태 일관성, 이벤트 유실 복구  
**확인 수준:** 재현 완료. 실제 큐 넘침의 발생 빈도는 미측정.  
**위치:** [daemon.py:534][daemon-534].

**원인과 영향**

이벤트 큐 넘침을 알리는 SYN_DROPPED를 무시한다. 유실된 버튼 해제나 축 변화가 복구되지 않아 클릭·드래그·컨트롤러 입력이 고착될 수 있다.

같은 이벤트 루프에서 수행하는 동기 subprocess와 재보정 대기는 이벤트 처리를 지연시키는 요인이다. 해당 지연이 실기기에서 실제 큐 넘침을 얼마나 유발하는지는 측정하지 않았다.

**재현 조건과 결과**

A가 눌린 상태에서 해제 이벤트 대신 SYN_DROPPED와 다음 SYN_REPORT를 전달했다. 장치 상태를 조회하지 않았고 A는 내부적으로 계속 눌려 있었다.

**수정 방안**

다음 SYN_REPORT까지 프레임을 버리고 ioctl로 키·축 상태를 다시 읽어 가상 장치와 동기화한다. [Linux 입력 프로토콜 문서](https://www.kernel.org/doc/html/latest/input/event-codes.html)가 요구하는 처리다.

**회귀 검증**

버튼 해제·스틱 중앙 복귀 유실, 재보정, 장치 재연결, 처리 지연 중 큐 넘침을 검사한다.

<a id="m07"></a>
### M07. 장치 grab 실패 후에도 게임패드·모터 소유자로 사용함

**분류:** 초기화 실패 처리, 장치 소유권  
**확인 수준:** 재현 완료. 실제 장치 점유 충돌은 실행하지 않음.  
**위치:** [daemon.py:230][daemon-230].

**원인과 영향**

grab() 실패 시 장치를 입력 감시 목록에서 제외하지만 found에는 남긴다. 이후 self.gamepad로 지정하고 모터 초기화까지 호출한다. 입력을 읽지 않는 장치를 정상 소유한 것처럼 취급하고 fd도 닫지 않는다.

**재현 조건과 결과**

게임패드의 grab()만 EBUSY로 실패시켰다. 게임패드 참조가 유지되고 모터 초기화가 1회 호출됐지만 입력 감시에는 등록되지 않았다. 장치 fd도 닫히지 않았다.

**수정 방안**

grab에 성공한 장치만 소유 목록에 넣고 실패한 fd는 닫는다. 필수 장치를 확보하지 못하면 제한된 재시도 또는 정상 종료를 통해 복구한다.

**회귀 검증**

다른 프로세스의 장치 점유, 장치 열기 실패, 일부 장치만 늦게 나타남, 초기화 중 종료를 검사한다.

<a id="m08"></a>
### M08. USB gadget 초기화 중 SIGTERM을 받으면 정리 경로를 건너뜀

**분류:** 종료 처리, 하드웨어 상태  
**확인 수준:** 코드 경로 확인. 실제 USB·커널 영향은 실기기 검증 필요.  
**위치:** [rg35xxh-usbpad:420][usb-420], [rg35xxh-usbpad:515][usb-515], [rg35xxh-usbpad.service:8][usb-unit-8].

**원인과 영향**

gadget 설정은 423행에서 시작하지만 SIGTERM 처리는 515행에서 설치한다. 그 사이 systemd가 서비스를 중지하면 기본 종료 동작이 적용돼 Python finally가 실행되지 않는다. USB Xbox·Switch 서비스에는 별도의 종료 후 정리 명령도 없다.

**발생 조건**

gadget 생성·바인딩·endpoint 열기 도중 서비스 중지, 재부팅 또는 모드 전환이 발생하는 경우다. 설정 잔재와 비정상 해제 가능성이 있다. 특정 커널 정지나 장치 고장을 재현한 것은 아니다.

**수정 방안**

자원을 얻기 전에 조기 종료 핸들러를 설치하고 부분 초기화에도 정리가 실행되도록 한다. 비정상 종료 뒤 정리를 보강할 경우에도 중복 실행과 부분 설정을 안전하게 처리해야 한다.

**회귀 검증**

초기화의 각 단계에서 중지 신호를 주입한다. configfs·FunctionFS·바인딩 정리와 다음 시작을 검사한다. 최종 검증은 실제 RG35XX H에서 수행해야 한다.

<a id="m09"></a>
### M09. HDMI 배율을 적용한 확장 모드에서 화면 사이에 빈 공간이 생김

**분류:** 디스플레이 배치, 논리 좌표 계산  
**확인 수준:** 재현 완료.  
**위치:** [rg35xxh-display:225][display-225].

**원인과 영향**

출력 위치는 논리 좌표인데 모니터의 물리 해상도를 그대로 사용한다. 배율이 1이 아니면 휴대기 화면이 잘못 배치돼 포인터가 두 화면 사이를 자연스럽게 이동하지 못한다.

**재현 조건과 결과**

3840×2160 모니터, 배율 2, 확장 모드를 전달했다.

| 항목 | 위치 |
|---|---|
| 필요한 휴대기 위치 | 640,1080 |
| 생성된 명령의 휴대기 위치 | 1600,2160 |

**수정 방안**

배율과 회전을 반영한 출력의 논리 크기로 위치를 계산한다. 포인터 속도 계산과 화면 배치가 같은 출력 좌표 모델을 사용하도록 정리한다.

**회귀 검증**

배율 1·1.5·2, 회전, HDMI 재연결, 해상도 변경 후 화면 접점과 포인터 이동을 검사한다.

<a id="m10"></a>
### M10. HDMI 테스트 모드의 15초 자동 복귀가 UI 루프 정지에 취약함

**분류:** 복구 보장, 예외 처리, 성능  
**확인 수준:** 코드 경로 확인. 실제 compositor 정지는 유발하지 않음.  
**위치:** [rg35xxh-display:165][display-165], [rg35xxh-display:682][display-682], [rg35xxh-display:788][display-788].

**원인과 영향**

UI 콜백에서 wlr-randr와 알림 명령을 timeout 없이 동기 실행한다. 자동 복귀도 같은 루프에 있고, 남은 시간을 실제 경과 시간 대신 콜백마다 0.1씩 줄인다. 명령이 지연되거나 멈추면 자동 복귀가 늦어지거나 멈춘다. 주기적인 출력 조회도 최대 5초 동안 같은 루프를 막을 수 있다.

**발생 조건**

출력 관리 요청이나 알림 서비스가 응답하지 않거나 매우 느린 경우다. UI 루프에서 복귀를 수행하므로 해당 루프의 진행을 전제로 한다.

**수정 방안**

외부 명령에 제한 시간을 두고 UI를 막지 않도록 실행한다. 복귀 기한은 monotonic 시계로 판단한다. UI 종료에도 복귀를 보장하려면 감시를 별도 프로세스로 분리한다.

**회귀 검증**

멈춘 명령, 명령 실패, 느린 출력 조회, 창 종료, HDMI 분리 중 테스트 모드 복귀를 검사한다.

<a id="m11"></a>
### M11. 새 Wi-Fi 설정 검증 전에 작동하던 연결 프로필을 삭제함

**분류:** 데이터 손실, 네트워크 복구  
**확인 수준:** 가짜 nmcli로 재현 완료. 실제 네트워크는 변경하지 않음.  
**위치:** [rg35xxh-wifi-import:24][wifi-24].

**원인과 영향**

기존 wifi-SSID 연결을 먼저 삭제한 뒤 새 프로필을 생성한다. 새 비밀번호가 유효하지 않거나 생성이 실패하면 기존 연결이 사라져 자동 연결과 원격 접근을 잃는다.

**재현 조건과 결과**

작동하던 기존 프로필을 가정하고 새 connection add를 실패시켰다. 스크립트는 종료 코드 1을 반환했지만 기존 프로필은 이미 삭제된 상태였다.

**수정 방안**

기존 프로필을 보존하면서 새 설정을 검증하고 성공 후 교체한다. 교체 실패·중지 시 이전 프로필이 유지되도록 해야 한다.

**회귀 검증**

잘못된 PSK, NetworkManager 실패, 새 프로필 생성 직후 중지, 교체 중 재부팅에서 기존 연결 보존을 검사한다.

<a id="m12"></a>
### M12. Screen off의 시스템 저전력 상태를 세션 종료 시 복원하지 않음

**분류:** 상태 소유권, 장애 복구, 아키텍처  
**확인 수준:** 코드 경로 확인. 세션·전원 조합의 최종 영향은 실기기 검증 필요.  
**위치:** [rg35xxh-lowpower:8][lowpower-8], [labwc/autostart:24][autostart-24], [daemon.py:1184][daemon-1184].

**원인과 영향**

CPU 코어·백라이트·오디오의 저전력 상태는 시스템 /run에 남지만 화면 끄기 플래그와 감시는 사용자 세션에 속한다. 데몬 정리와 다음 세션 시작 어느 쪽에도 시스템 저전력 상태 복원 처리가 없다.

**발생 조건**

Screen off 중 로그아웃이나 compositor 종료가 발생하는 경우다. 사용자 runtime 디렉터리가 재생성되면 새 세션은 화면 끄기 상태를 모르면서 백라이트 꺼짐·코어 오프라인·오디오 음소거 상태를 물려받을 수 있다. runtime 디렉터리의 유지 여부에 따라 사용자에게 보이는 복구 경로는 달라진다.

**수정 방안**

저전력 상태의 소유권과 수명을 시스템 서비스 또는 명확한 세션 수명에 연결한다. 종료와 다음 시작에서 필요한 상태를 복원하고 중복 복원도 안전하게 처리한다.

**회귀 검증**

Screen off 중 정상 로그아웃, 세션 충돌, 사용자 runtime 재생성, 정상 깨우기, 다른 컨트롤러 모드와의 조합을 실기기에서 확인한다.

<a id="m13"></a>
### M13. arm64 빌드 호스트에서 실행할 수 없는 커널 도구 체인을 선택함

**분류:** 빌드 호환성  
**확인 수준:** 코드 경로 확인. arm64 Linux 빌드는 미실행.  
**위치:** [build/config.sh:24][config-24], [build/06b-cedrus.sh:27][cedrus-27].

**원인과 영향**

Go는 호스트 아키텍처에 따라 선택하지만 커널 도구 체인은 항상 x86_64 호스트용을 내려받는다. 추가 커널 모듈 빌드는 모두 이 실행 파일을 사용한다. 문서에서 지원한다고 명시한 네이티브 arm64 빌드 호스트와 맞지 않는다.

**발생 조건**

문서대로 arm64 Debian·Ubuntu 호스트에서 전체 빌드를 수행하는 경우다. 별도의 x86_64 실행 호환 환경이 없는 일반적인 네이티브 환경에서는 컴파일러가 실행되지 않는다.

**수정 방안**

호스트 아키텍처별 도구 체인 URL과 체크섬을 선택한다. 컴파일러 버전과 ROCKNIX 모듈 호환성 검사는 유지한다.

**회귀 검증**

x86_64와 arm64 호스트에서 추가 모듈을 빌드하고 symbol version과 vermagic을 확인한다.

## 5. Low 발견 사항

<a id="l01"></a>
### L01. 이미지 빌드에서 입력 테스트 2개가 누락됨

**분류:** 테스트 신뢰성  
**확인 수준:** 재현 완료.  
**위치:** [build/08-input.sh:6][input-build-6], [test_core.py:398][tests-398], [test_core.py:412][tests-412], [test_core.py:426][tests-426].

**원인과 영향**

테스트 파일의 직접 실행부가 마지막 두 테스트 정의보다 앞에 있다. 이미지 빌드는 이 직접 실행 경로를 사용하므로 키보드 A 반복과 L2 Shift 관련 테스트가 빠진다.

**재현 조건과 결과**

pytest는 31개를 수집해 모두 통과했다. 빌드와 같은 직접 실행은 29개만 실행해 29/29로 표시했다.

**수정 방안**

직접 실행부를 파일 끝으로 옮기거나 실행기를 통일한다.

**회귀 검증**

두 실행 경로의 수집 개수와 테스트 이름이 같아야 한다.

<a id="l02"></a>
### L02. 로컬 커널 패치 변경이 기존 빌드 트리에 반영되지 않음

**분류:** 증분 빌드 정확성  
**확인 수준:** 코드 경로 확인. 실제 커널 재빌드는 미실행.  
**위치:** [build/06b-cedrus.sh:36][cedrus-36].

**원인과 영향**

.rg35xxh-patched의 존재 여부만 확인하고 패치 내용의 변경을 확인하지 않는다. 한 번 빌드한 뒤 로컬 패치를 수정하고 재실행하면 이전 소스를 사용할 수 있다. 현재의 특정 문자열 검사만으로 모든 패치 변경을 검출하지 못한다.

**발생 조건**

Linux·ROCKNIX 버전이 같은 기존 작업 디렉터리에서 로컬 커널 패치를 변경하는 경우다. 수정했다고 생각한 드라이버 변경이 결과물에 포함되지 않을 수 있다.

**수정 방안**

소스 버전, ROCKNIX 패치, 로컬 패치의 해시로 캐시를 무효화한다.

**회귀 검증**

로컬 패치 변경 뒤 재실행 시 트리가 갱신되고 결과물이 바뀌는지 확인한다. 변경 없는 재실행에서는 캐시를 재사용해야 한다.

<a id="l03"></a>
### L03. Wi-Fi 명령 경로에 공백이 있으면 실행이 깨짐

**분류:** 경로 처리, 테스트 이식성  
**확인 수준:** 재현 완료.  
**위치:** [rg35xxh-wifi-import:24][wifi-24], [test-wifi-import.sh:19][wifi-tests-19].

**원인과 영향**

NMCLI 실행 파일 변수를 따옴표 없이 실행한다. 현재처럼 저장소 경로에 공백이 있으면 가짜 nmcli 경로가 분리돼 테스트가 실패한다. 기기의 기본 nmcli 경로에서는 이 조건이 발생하지 않는다.

**재현 조건과 결과**

원래 저장소 경로에서 가짜 nmcli 실행이 경로 중간에서 끊겼다. 공백 없는 임시 경로에 동일 파일을 복사하면 기존 11개 검사 모두 통과했다.

**수정 방안**

실행 파일 경로를 인용한다. 같은 방식으로 실행하는 다른 테스트용 명령 변수도 점검한다.

**회귀 검증**

공백이 있는 저장소 경로와 도구 경로에서 테스트를 실행한다.

## 6. 의존성 및 추가 조사 후보

### 6.1 확인한 버전과 상태

| 대상 | 확인 결과 |
|---|---|
| Debian 패키지 | 809개 설치 패키지, 501개 소스 패키지로 정리 |
| Debian 보안 추적기 | 항목이 있는 소스 257개를 대조. 버전 기반 후보 매칭 929개 생성 |
| FFmpeg | 실제 바이너리와 dpkg 메타데이터 불일치 확인. H01로 보고 |
| BlueZ 5.82-1.1 | 실제 bluetoothd가 해당 Debian 패키지 바이너리와 일치 |
| Chromium 156.0.8078.73 | 감사 당시 확인한 최신 관련 Debian 보안 업데이트 버전과 일치 |
| Tailscale 1.104.4 | TS-2026-014~017의 수정 버전에 해당 |
| nwg-drawer v0.7.5 | 배포 바이너리의 Go 빌드 메타데이터 확인 |
| Go 의존성 | Tailscale·tailscaled·nwg-drawer에서 중복 제거한 105개 모듈 조회 |
| ROCKNIX 커널 | 두 이미지의 내장 설정 일치. 추가 모듈·패치·빌드 경로 검토 |
| Moonlight 6.2.0 | 패키지 버전과 바이너리 확인. 내장 FFmpeg의 전체 패치 상태는 추가 검증 필요 |

**929개 Debian 권고 매칭은 확정 취약점 수가 아니다.** 미해결·보류·정보성 항목과 기능별 전제 조건을 포함하며, 이 숫자를 본문의 확정 18건에 더하지 않는다. 설치 버전이 최신 고정 버전보다 낮은지 비교한 검사에서는 별도의 고정 버전 미달 항목이 나오지 않았으나, 미해결 권고와 직접 교체한 바이너리의 위험이 사라지는 것은 아니다.

[전체 패키지 목록](audit-evidence-20261030/packages-ddr4.json)과 [Debian 권고 대조 결과](audit-evidence-20261030/debian-security-matches.json)를 함께 보관했다.

### 6.2 확정 건수에서 제외한 보안 후보

#### D01. BlueZ CVE-2026-19774의 Handtop 실행 경로

공식 추적기는 설치 버전 5.82-1.1을 영향 대상으로 표시한다. 악의적인 장치와 A2DP 기능을 협상할 때 root 프로세스의 스택 오버플로가 발생할 수 있다. 기준 BlueZ 소스의 codec capability 저장 처리와 업스트림 수정도 대조했다.

다만 기본 이미지에는 libspa-0.2-bluetooth가 없다. Handtop 기본 상태에서 해당 경로에 도달하는지 추가 확인이 필요하다. A2DP를 활성화하거나 관련 패키지를 추가하는 구성은 우선 검증 대상이다. 실제 악성 장치 페어링과 메모리 손상은 재현하지 않았다.

- [CVE-2026-19774 — Debian 보안 추적기](https://security-tracker.debian.org/tracker/CVE-2026-19774)
- [업스트림 수정](https://github.com/bluez/bluez/commit/912f5efb0dd9bb08e408d33371a57182c5678aef)

#### D02. 그 밖의 BlueZ 권고

발견, AVRCP, 진단 도구 등 권고별 전제 조건이 다르다. 버전 매칭만으로 모두 무선 원격 공격 가능 문제로 합산하지 않았다. Bluetooth 하드웨어의 지원 기능, 활성 프로파일, 실제 패킷 경로를 포함해 추가 확인해야 한다.

- [BlueZ 패키지 보안 상태](https://security-tracker.debian.org/tracker/source-package/bluez)

#### D03. Go 모듈 권고의 실행 경로

모듈 조회에서 3개 모듈에 대해 권고 4개가 매칭됐다.

| 모듈 | 권고 | 판정 |
|---|---|---|
| golang.org/x/crypto v0.58.0 | GO-2026-5932 | openpgp 관련 권고. 해당 코드의 실행 근거를 확인하지 못해 확정 제외 |
| golang.org/x/net v0.60.0 | GO-2026-6860, GO-2026-6866 | HTML 파싱·렌더링 관련 권고. 해당 코드의 실행 근거를 확인하지 못해 확정 제외 |
| golang.org/x/sys v0.42.0 | GO-2026-5024 | Windows 전용 코드 관련 권고. 대상 Linux 이미지 문제로 확정하지 않음 |

바이너리에서 관련 패키지 식별자를 찾는 보완 검사를 수행했으나 전체 govulncheck 호출 경로 분석을 수행한 것은 아니다.

- [Go 모듈 목록](audit-evidence-20261030/go-module-inventory.json)
- [Go 권고 매칭 결과](audit-evidence-20261030/go-advisory-matches.json)

#### D04. ROCKNIX 커널·펌웨어 및 Moonlight의 내장 라이브러리

ROCKNIX 하드웨어 계층은 Debian 패키지 업데이트와 별개다. 커널·모듈·펌웨어의 보안 수정 추적과 배포 정책을 별도로 확인해야 한다. 이번 검토는 전체 업스트림 커널·펌웨어의 독립적인 보안 감사를 대체하지 않는다.

Moonlight의 정적으로 포함된 라이브러리는 Debian 공유 라이브러리 목록만으로 패치 상태를 확정할 수 없다. 해당 릴리스의 내장 FFmpeg 소스와 패치 목록을 별도로 확인해야 한다.

### 6.3 미수정 문제로 보고하지 않은 항목

- Chromium 156.0.8078.73은 확인한 관련 Debian 보안 업데이트 버전과 일치했다. [공식 추적기](https://security-tracker.debian.org/tracker/source-package/chromium).
- Tailscale 1.104.4는 TS-2026-014~017의 수정 버전이다. 해당 권고를 미수정 문제로 보고하지 않았다. [공식 보안 공지](https://tailscale.com/security-bulletins).
- chromium-sandbox 패키지 미설치만으로 sandbox 해제라고 판정하지 않았다. 추출한 커널 설정에서 USER_NS, SECCOMP, SECCOMP_FILTER가 활성화되어 있었다. 실제 브라우저 sandbox 런타임 검사는 별도다.
- 검사한 SSH 호스트 키, Bluetooth 페어링, Tailscale 상태, NetworkManager 연결 프로필에서 명시적인 배포 자격 증명 잔재는 발견되지 않았다.

## 7. 검사 범위와 테스트 결과

### 7.1 모듈별 범위

| 범위 | 수행 내용 | 미검증 영역 |
|---|---|---|
| 입력 core·daemon·UI·OSK | 로직, 장치 수명, IPC, 순수 테스트, 가짜 장치 재현 | 실제 입력 장치, 진동, Wayland UI |
| BLE·Classic·USB·상태 화면 | 연결, 보고서, 승인, 진동 요청, 종료 경로 | 무선·USB 실통신, 실제 상대 장치 호환성 |
| HDMI·테마·세션 | 배치, 복귀, 프로세스 관리, 배율 계산 재현 | 실제 compositor와 모니터 |
| 전원·저전압 | 상태 진입·복구, 세션 수명과의 결합 | 전원·CPU·백라이트·무선 상태 전환 |
| 부팅·패널·저장장치 | 파일 쓰기, 서비스 순서, 재실행·복구 경로 | GPIO, 실제 FAT 전원 차단 복구 |
| C OSD·부팅 화면 | 버퍼, 문자열, 그리기 범위, fd, 종료 경로 정적 검토 | C 빌드, sanitizer, framebuffer |
| 빌드·커널 변경 | 다운로드, chroot, 삭제 경계, 패치, ABI 검사, 이미지 구성 | 전체 Linux 빌드와 모듈 로드 |
| sudoers·polkit·udev·SSH | 권한 경계, 실행 인자, 기본 구성 | 실제 systemd·polkit 통합 실행 |
| 아이콘 생성기·showcase | 생성·저장 경로와 코드 검토, JS 문법 검사 | 자산 재생성, 게임 플레이·UI 검증 |
| 의존성 | 배포 패키지·바이너리·Go 메타데이터, 공식 권고 대조 | 모든 권고의 도달 가능성, 전체 업스트림 소스 감사 |

확인한 권한 경계와 실행 인자 경로에서 별도의 명령 주입 근거는 찾지 못했다. 이는 미검토 경로나 전체 의존성에 취약점이 없다는 보장은 아니다.

### 7.2 실행 결과

| 검사 | 결과 |
|---|---|
| DDR3·DDR4 이미지 SHA-256 | 각각 동봉 체크섬과 일치 |
| 설치 패키지 목록 | 각 809개, 두 이미지 동일 |
| 주요 스크립트·입력 모듈 소스 대조 | 이미지별 39개, 차이 없음 |
| 내장 커널 설정 비교 | 동일 |
| pytest 입력 테스트 | 31/31 통과 |
| 빌드와 같은 직접 테스트 실행 | 29/29 통과 — L01의 수집 누락 확인 |
| Python AST 검사 | 30개 통과 |
| 셸 Bash 문법 검사 | 56개 통과 |
| 기존 Wi-Fi 검사 | 공백 없는 동일 파일 복사본에서 11개 통과 |
| 공백 포함 경로의 Wi-Fi 검사 | 가짜 명령 경로 분리로 실패 — L03 |
| showcase JavaScript 문법 | 통과 |
| 선택 함수의 실패 주입 재현 | 입력 검증, 전송 실패, motor 큐, grab 실패, 이벤트 유실, HDMI 배율 등 확인 |

### 7.3 검증 한계

- Windows 환경에서 수행했다. Bash 문법 검사 결과를 dash 실행 검증으로 간주하지 않는다.
- QEMU·headless Wayland·systemd 통합 검사와 전체 Linux 이미지 빌드를 실행하지 않았다.
- 실제 장치를 잡거나 모터·라디오·전원 상태를 변경하는 테스트를 실행하지 않았다.
- 실기기 테스트가 필요한 항목의 발생 빈도와 기기별 영향은 측정하지 않았다.
- 성능 문제는 코드상 대기·재시도·이벤트 처리 원인을 검토했다. 실제 기기의 CPU·전력·프레임 수치를 새로 측정하지 않았다.
- 코드 위치는 기준 커밋의 줄 번호다. 수정 이후에는 해당 위치를 다시 확인해야 한다.

## 8. 수정 우선순위 및 완료 조건

| 순서 | 대상 | 완료 조건 |
|---|---|---|
| 1 | H01 | 필요한 하드웨어 디코딩을 유지하면서 보안 수정 포함, 패키지·바이너리·패치 상태 일치 |
| 2 | H02 | 컨트롤러 연결에 필요한 기기·서비스로 승인 범위 제한, 무관한 기기 영구 신뢰 방지 |
| 3 | M01·M02·M05 | 마지막 입력 상태 재전송 보장, 모드 종료 뒤 진동 작업 차단, 입력 경로 실패 시 복구 |
| 4 | M06·M07·M08 | 이벤트 유실·장치 점유 실패·USB 초기화 중 종료에서 안전하게 정리 및 재시작 |
| 5 | M11·M12 | Wi-Fi 갱신 실패 시 기존 연결 보존, 세션 종료 후 저전력 상태 복원 |
| 6 | M09·M10 | 배율별 화면 접점 정상, 명령 지연과 UI 종료에도 테스트 모드 복귀 |
| 7 | M03·M13·L01·L02·L03 | 연결 수명 정리, 지원 호스트 빌드, 테스트 수집 통일, 캐시·경로 처리 보완 |

이 보고서는 수정 제안이며 구현을 포함하지 않는다. 동작 제한, 기본값 변경, 새 확인 단계, 성능·메모리·전력 비용이 생기는 수정은 AGENTS.md의 절충점 결정 규칙을 적용해야 한다.

하드웨어를 제어하는 수정은 부분 초기화·종료·재시작 양방향을 먼저 검사한 뒤 실제 RG35XX H에서 검증해야 한다. DDR3·DDR4, regular·rev6 패널, 연결 방식 등 재현 조건을 수정 검증 기록에 명시한다.

## 부록 A. 보관한 근거 자료

보고서 옆의 작은 근거 자료 폴더에 감사 데이터를 복사했다. 해제한 전체 이미지, 설치한 분석 도구, 대용량 원본 보안 DB는 이 근거 자료 폴더에 포함하지 않았다.

| 파일 | 내용 |
|---|---|
| [packages-ddr4.json](audit-evidence-20261030/packages-ddr4.json) | 두 이미지에서 동일하게 확인된 809개 설치 패키지 |
| [metadata-ddr3.json](audit-evidence-20261030/metadata-ddr3.json) | DDR3 이미지 파일·파티션 메타데이터 |
| [metadata-ddr4.json](audit-evidence-20261030/metadata-ddr4.json) | DDR4 이미지 파일·파티션 메타데이터 |
| [probe-results.json](audit-evidence-20261030/probe-results.json) | 기본 실패 주입·순수 함수 재현 결과 |
| [additional-probe-results.json](audit-evidence-20261030/additional-probe-results.json) | HDMI 배율, grab 실패, SYN_DROPPED, heartbeat 재현 결과 |
| [l2cap-watch-probe.json](audit-evidence-20261030/l2cap-watch-probe.json) | 실제 소켓 객체로 확인한 M03 보완 결과 |
| [debian-security-matches.json](audit-evidence-20261030/debian-security-matches.json) | 추가 분류가 필요한 Debian 권고 매칭 929개 |
| [go-module-inventory.json](audit-evidence-20261030/go-module-inventory.json) | Go 바이너리의 모듈 메타데이터 |
| [go-advisory-matches.json](audit-evidence-20261030/go-advisory-matches.json) | Go 모듈 권고 매칭 |
| [static-inventory.json](audit-evidence-20261030/static-inventory.json) | Python·셸 검사 대상과 동기 subprocess 조사 목록 |

원시 재현 결과에는 결함이 나타나지 않은 대조 사례와 초기 가짜 소켓 검사도 포함된다. 원시 결과의 테스트 이름을 곧바로 취약점 판정으로 해석하지 않는다. 특히 M03은 보완 검사에 따라 소켓 fd 누수 주장을 제외했다.

<a id="review"></a>
## 9. 검토 의견 (Reviewed, 2026-11-02)

**검토 기준:** main [98a5ae2](https://github.com/junsulee119/handtop/commit/98a5ae2) (PR #5 VA-API와 enhanced-h264ify 포함). 18건 모두를 소스와 대조했다. 본문의 줄 번호는 98a5ae2에서도 해당 코드를 가리킨다. 검토자는 재현 스크립트를 다시 실행하지 않았고 실기기 테스트도 하지 않았다.

**총평:** 보고서는 정확하다. 확인 수준을 구분했고, 재현하지 않은 영향을 과장하지 않았다. 18건 모두 코드에 실제로 존재한다. 다만 심각도 두 건은 조정이 필요하다(H02 하향, M09 하향). 하드웨어 안전 관점에서는 M02와 M08을 우선해야 한다.

| ID | 판정 | 조정 심각도 | 검토 의견 |
|---|---|---|---|
| H01 | 확인 | High 유지 | CVE-2026-8461(MagicYUV, "PixelSmash")과 CVE-2026-38347(swscale 힙 오버플로)이 실존함을 Ubuntu와 Red Hat 추적기에서 확인했다. 단기 수정으로 04c에서 고정 커밋 위에 두 수정 커밋을 적용하고, 적용 여부를 빌드에서 검사한다. 패키지 버전 표기와 업데이트 경로는 별도 작업으로 다룬다. PR #5 이후에는 VA-API 경로도 같은 libavcodec을 쓴다. "libavformat 등은 Debian 파일 유지"라는 서술은 make install이 모든 라이브러리를 설치하는 구조와 맞지 않아 보이는데, 검토자는 이미지로 확인하지 않았다. |
| H02 | 확인 | Medium-High | 모드 중 에이전트가 모든 페어링과 서비스를 승인한다. 실제 위험은 근처 기기가 HID 키보드로 페어링해 자동 로그인 데스크톱에 입력하는 경우다. 승인 범위를 제한하면 호스트별 페어링(Switch, Windows, Xbox BLE)이 깨질 수 있다. 따라서 범위를 먼저 결정하고 실기기 회귀 테스트를 한 뒤 별도 PR로 진행한다. |
| M01 | 확인 | Medium | `notify()`의 BlockingIOError 처리는 "다음 보고서가 최신 상태를 전달한다"고 가정한다. 이 가정은 마지막 버튼 해제에서 성립하지 않는다. |
| M02 | 확인 | Medium, **우선 수정** | 모드 종료 뒤 업로드된 효과는 `pad_ff`에 남고, `_destroy_pad`가 다시 정리하지 않는다. 무한 길이 효과라면 모터가 계속 돌 수 있다. hardware-safety.md의 진동 규칙에 해당하며 수정은 작다. |
| M03 | 확인 | Medium | 보고서보다 영향이 클 수 있다. 교체된 소켓이 GC로 닫히면 남은 watch는 닫힌 fd를 감시한다. 이때 poll이 POLLNVAL을 즉시 반환해 메인 루프가 바쁜 대기(CPU 점유)에 빠질 가능성이 있다(미측정). `drop()`은 `self.watches`를 모두 제거하므로 연결 해제 시에는 정리된다. |
| M04 | 확인 | Medium | `getboolean(..., fallback=False)`의 fallback은 항목이 없을 때만 적용된다. FAT 설정 오타 하나로 데몬이 재시작 루프에 빠지면 버튼 입력 전체를 잃는다. |
| M05 | 확인 | Medium | `_tick`에 최상위 예외 처리가 없다. M04와 함께 수정하면 좋다. |
| M06 | 확인 | Low | 커널 입력 프로토콜상 맞는 지적이다. 다만 이벤트 큐 넘침이 전제 조건이라 실제 빈도는 낮다고 본다. |
| M07 | 확인 | Medium | grab에 실패한 장치가 `self.gamepad`가 되어 모터까지 초기화된다. |
| M08 | 확인 | Medium, **우선 수정** | hardware-safety.md 규칙 2.3(부분 초기화도 정리)에 어긋난다. 자원을 얻기 전에 SIGTERM을 예외로 바꾸는 핸들러를 설치하면 되는 작은 수정이다. |
| M09 | 확인(잠재) | **Low** | Handtop의 kanshi 설정은 항상 `scale 1`이다. 사용자가 직접 배율을 바꿀 때만 발생한다. |
| M10 | 확인 | Low-Medium | `randr()`와 `notify()`에 timeout이 없다(`outputs()`만 5초). 카운트다운이 콜백마다 0.1씩 줄어 콜백이 늦으면 복귀도 늦어진다. compositor 자체가 멈춘 경우에는 별도 감시 프로세스도 wlr-randr를 실행하지 못한다. 따라서 monotonic 기한과 명령 timeout으로 충분하다고 본다. |
| M11 | 확인 | Low | `nmcli connection add`가 실패하는 조건은 제한적이다(8자 미만 PSK 등). 실패 시 wifi.txt의 비밀번호가 남아 다음 부팅에 재시도된다. |
| M12 | 확인 | Medium | 세션 시작(labwc autostart)에서 `rg35xxh-lowpower off`를 한 번 실행하면 해결된다. 이 명령은 상태가 없으면 아무것도 하지 않으므로 중복 실행해도 안전하다. |
| M13 | 확인 | Low | building.md가 arm64 호스트를 지원한다고 명시하므로 문서와 코드가 어긋난다. |
| L01 | 확인 | Low | 빌드의 단위 테스트가 31개 중 29개만 실행한다. 수정은 한 줄이다. |
| L02 | 확인 | Low | 빌드 서버는 매번 새로 클론하므로 영향이 작다. 같은 작업 디렉터리에서 커널 패치를 반복 수정할 때만 문제가 된다. |
| L03 | 확인 | Low | 테스트에만 영향이 있다. 기기의 기본 nmcli 경로에서는 발생하지 않는다. |

**수정 묶음 제안** (AGENTS.md: 한 PR에 한 주제)

1. H01: FFmpeg 보안 수정 2건 적용과 빌드 검사.
2. 입력 데몬 견고성: M02, M04, M05, M07, L01(M06은 선택). 실기기 테스트 필요.
3. 컨트롤러 모드: M08, M01, M03. 실기기 테스트 필요. H02는 승인 범위를 결정한 뒤 별도 PR로 진행한다.
4. 기타: M12, M10, M11, L03, M13, L02, M09.

[config-38]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/config.sh#L38
[config-24]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/config.sh#L24
[ffbuild-93]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/04c-v4l2-ffmpeg.sh#L93
[ffbuild-155]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/04c-v4l2-ffmpeg.sh#L155
[bt-319]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-btpad#L319
[bt-846]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-btpad#L846
[bt-877]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-btpad#L877
[bt-390]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-btpad#L390
[bt-235]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-btpad#L235
[classic-230]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-switchbt#L230
[classic-607]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-switchbt#L607
[classic-521]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-switchbt#L521
[classic-535]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-switchbt#L535
[classic-670]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-switchbt#L670
[daemon-408]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L408
[daemon-1056]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L1056
[daemon-568]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L568
[daemon-1143]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L1143
[daemon-1161]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L1161
[daemon-534]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L534
[daemon-230]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L230
[daemon-1184]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/daemon.py#L1184
[input-config-38]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/config.py#L38
[input-config-55]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/config.py#L55
[core-324]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/rg35xxh_inputd/core.py#L324
[usb-420]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-usbpad#L420
[usb-515]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-usbpad#L515
[usb-unit-8]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/etc/systemd/system/rg35xxh-usbpad.service#L8
[display-225]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/bin/rg35xxh-display#L225
[display-165]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/bin/rg35xxh-display#L165
[display-682]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/bin/rg35xxh-display#L682
[display-788]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/bin/rg35xxh-display#L788
[wifi-24]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-wifi-import#L24
[lowpower-8]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/usr/local/sbin/rg35xxh-lowpower#L8
[autostart-24]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/overlay/etc/xdg/labwc/autostart#L24
[cedrus-27]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/06b-cedrus.sh#L27
[cedrus-36]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/06b-cedrus.sh#L36
[input-build-6]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/build/08-input.sh#L6
[tests-398]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/tests/test_core.py#L398
[tests-412]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/tests/test_core.py#L412
[tests-426]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/src/inputd/tests/test_core.py#L426
[wifi-tests-19]: https://github.com/junsulee119/handtop/blob/6ef72a9535f4ff0b5767068a4045ad4155ed964e/tools/test-wifi-import.sh#L19

