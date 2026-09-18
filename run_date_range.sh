#!/usr/bin/env bash

# ==============================================================================
# Telegram Scraping Date Range Runner Script
# 특정 일자 구간(시작일 ~ 종료일) 동안 telegram_scrap_test.py를 순차 실행하는 스크립트
# ==============================================================================

# 스크립트 파일이 위치한 디렉토리로 이동
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 실행 파일 감지 (가상환경 우선)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_EXEC="python3"
elif command -v python &>/dev/null; then
    PYTHON_EXEC="python"
else
    echo "❌ Python 실행 파일을 찾을 수 없습니다." >&2
    exit 1
fi

# 사용법 안내 함수
usage() {
    echo "사용법: $0 <시작일자> <종료일자> [추가옵션...]"
    echo ""
    echo "설명:"
    echo "  지정한 시작일자부터 종료일자까지 1일씩 증가시키며 telegram_scrap_test.py를 실행합니다."
    echo ""
    echo "인자:"
    echo "  시작일자        수집 시작 일자 (형식: YYYYMMDD 또는 YYYY-MM-DD, 예: 20260901)"
    echo "  종료일자        수집 종료 일자 (형식: YYYYMMDD 또는 YYYY-MM-DD, 예: 20260918)"
    echo "  추가옵션        telegram_scrap_test.py에 전달할 추가 옵션 (예: --no-upload-gcs)"
    echo ""
    echo "예시:"
    echo "  $0 20260901 20260905"
    echo "  $0 2026-09-01 2026-09-05 --no-upload-gcs"
}

# 도움말 출력
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    usage
    exit 0
fi

# 인자 개수 확인
if [ "$#" -lt 2 ]; then
    echo "❌ 오류: 시작일자와 종료일자를 입력해야 합니다." >&2
    echo ""
    usage
    exit 1
fi

START_INPUT="$1"
END_INPUT="$2"
shift 2 # 앞의 2개 인자 제거, 나머지는 python 스크립트에 전달할 옵션

# 날짜 포맷 정리 (하이픈 제거: 2026-09-01 -> 20260901)
START_DATE=$(echo "$START_INPUT" | tr -d '-')
END_DATE=$(echo "$END_INPUT" | tr -d '-')

# 날짜 유효성 검사 (8자리 숫자 확인 및 date 명령어로 유효성 검증)
if ! [[ "$START_DATE" =~ ^[0-9]{8}$ ]] || ! date -d "$START_DATE" +%Y%m%d &>/dev/null; then
    echo "❌ 유효하지 않은 시작일자입니다: $START_INPUT (YYYYMMDD 형식 필요)" >&2
    exit 1
fi

if ! [[ "$END_DATE" =~ ^[0-9]{8}$ ]] || ! date -d "$END_DATE" +%Y%m%d &>/dev/null; then
    echo "❌ 유효하지 않은 종료일자입니다: $END_INPUT (YYYYMMDD 형식 필요)" >&2
    exit 1
fi

if [ "$START_DATE" -gt "$END_DATE" ]; then
    echo "❌ 시작일자($START_DATE)가 종료일자($END_DATE)보다 미래일 수 없습니다." >&2
    exit 1
fi

echo "=========================================================="
echo "🚀 텔레그램 스크랩 일자 구간 실행 시작"
echo "  - 시작일자 : $START_DATE"
echo "  - 종료일자 : $END_DATE"
echo "  - Python   : $PYTHON_EXEC"
if [ -n "$*" ]; then
    echo "  - 추가옵션 : $*"
fi
echo "=========================================================="

CURRENT_DATE="$START_DATE"
SUCCESS_COUNT=0
FAIL_COUNT=0

# 일자별 반복 실행
while [ "$CURRENT_DATE" -le "$END_DATE" ]; do
    echo ""
    echo "----------------------------------------------------------"
    echo "📅 [일자: $CURRENT_DATE] 스크랩 작업 시작..."
    echo "----------------------------------------------------------"

    # Python 스크립트 실행
    if "$PYTHON_EXEC" "$SCRIPT_DIR/telegram_scrap_test.py" --date "$CURRENT_DATE" "$@"; then
        echo "✅ [일자: $CURRENT_DATE] 작업 완료"
        ((SUCCESS_COUNT++))
    else
        echo "⚠️ [일자: $CURRENT_DATE] 작업 실패" >&2
        ((FAIL_COUNT++))
    fi

    # 다음 날짜로 이동 (GNU date)
    CURRENT_DATE=$(date -d "$CURRENT_DATE + 1 day" +%Y%m%d)

    # 연속 실행 간 1초 대기 (종료일 이후에는 대기 생략)
    if [ "$CURRENT_DATE" -le "$END_DATE" ]; then
        sleep 1
    fi
done

echo ""
echo "=========================================================="
echo "🎉 전체 일자 구간 작업이 완료되었습니다."
echo "  - 성공 일수: $SUCCESS_COUNT"
echo "  - 실패 일수: $FAIL_COUNT"
echo "=========================================================="
