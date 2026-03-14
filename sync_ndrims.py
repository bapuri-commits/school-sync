"""nDRIMS 로컬 크롤 → VPS 동기화 스크립트.

사용법:
    python sync_ndrims.py

동작:
    1. 로컬에서 nDRIMS 크롤링 (headed 브라우저, SSO 수동 로그인)
    2. 결과 JSON을 VPS로 scp 전송
    3. VPS에서 normalize 트리거
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

VPS_HOST = os.getenv("VPS_HOST", "")
VPS_USER = os.getenv("VPS_USER", "")
VPS_DATA_DIR = "/opt/data/study/output/raw/ndrims"

LOCAL_OUTPUT = Path(__file__).parent / "output" / "raw" / "ndrims" / "ndrims.json"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, **kwargs)


def main():
    print("=" * 50)
    print("  nDRIMS 로컬 크롤 → VPS 동기화")
    print("=" * 50)

    if not VPS_HOST or not VPS_USER:
        print("[실패] .env에 VPS_HOST, VPS_USER를 설정해주세요.")
        print("  예: VPS_HOST=46.250.251.82")
        print("      VPS_USER=dev")
        sys.exit(1)

    # 1. 로컬 크롤링
    print("\n[1/3] nDRIMS 크롤링 (SSO 수동 로그인)")
    result = run(
        [sys.executable, "main.py", "--site", "ndrims", "--no-normalize"],
        cwd=str(Path(__file__).parent),
    )
    if result.returncode != 0:
        print("[실패] 크롤링 실패")
        sys.exit(1)

    if not LOCAL_OUTPUT.exists():
        print(f"[실패] 결과 파일 없음: {LOCAL_OUTPUT}")
        sys.exit(1)

    size = LOCAL_OUTPUT.stat().st_size
    print(f"  결과: {LOCAL_OUTPUT} ({size:,} bytes)")

    # 2. SCP 전송
    print(f"\n[2/3] VPS로 전송 ({VPS_USER}@{VPS_HOST})")
    dest = f"{VPS_USER}@{VPS_HOST}:{VPS_DATA_DIR}/ndrims.json"

    result = run([
        "ssh", f"{VPS_USER}@{VPS_HOST}",
        f"mkdir -p {VPS_DATA_DIR}",
    ])
    if result.returncode != 0:
        print("[실패] VPS 연결 또는 디렉토리 생성 실패")
        sys.exit(1)

    result = run(["scp", str(LOCAL_OUTPUT), dest])
    if result.returncode != 0:
        print("[실패] SCP 전송 실패")
        sys.exit(1)
    print("  전송 완료")

    # 3. VPS에서 normalize
    print("\n[3/3] VPS에서 정규화 실행")
    result = run([
        "ssh", f"{VPS_USER}@{VPS_HOST}",
        "docker exec study python main.py --normalize-only",
    ])
    if result.returncode != 0:
        print("[실패] 정규화 실패")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  nDRIMS 동기화 완료!")
    print("=" * 50)


if __name__ == "__main__":
    main()
