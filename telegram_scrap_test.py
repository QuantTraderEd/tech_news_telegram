import os
import sys
import site
import logging
import json
import datetime as dt
import argparse

from telethon.sync import TelegramClient

src_path = os.path.dirname(__file__)
# pjt_home_path = os.path.join(src_path, os.pardir)
pjt_home_path = os.path.join(src_path)
pjt_home_path = os.path.abspath(pjt_home_path)
site.addsitedir(pjt_home_path)

# 로깅 설정
logger = logging.getLogger(__file__)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s %(lineno)d: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger.setLevel(logging.INFO)
stream_log = logging.StreamHandler(sys.stdout)
stream_log.setFormatter(formatter)
logger.addHandler(stream_log)

# -----------------------------------------------------------
# 설정 파일 (config.json) 에서 API 정보 로드
# -----------------------------------------------------------
try:
    with open(f'{pjt_home_path}/config.json', 'r') as f:
        config = json.load(f)
    API_ID = config['tele_api_id']
    API_HASH = config['tele_api_hash']
    PHONE_NUMBER = config['tele_pn']
except FileNotFoundError:
    logger.error("❌ 'config.json' 파일을 찾을 수 없습니다. API 정보를 담은 설정 파일을 생성해주세요.")
    exit()
except KeyError as e:
    logger.error(f"❌ 'config.json' 파일에 필요한 키({e})가 없습니다.")
    exit()


# 수집할 채널 주소 및 출력 디렉토리 설정
CHANNEL_URLS = [
    "Samsung_Global_AI_SW",
    "samsungpe",
    "ss_global_aerospace",
    "growth_semi",
    "aetherjapanresearch",
    "bornlupin",
]

OUTPUT_DIR = 'data'


def fetch_messages_by_date(api_id, api_hash, phone, channel_url, target_date_str):
    """
    특정 텔레그램 채널에서 특정 일자의 메시지를 가져와 리스트로 반환합니다.
    """
    # 타겟 일자를 datetime.date 객체로 변환
    try:
        target_date = dt.datetime.strptime(target_date_str, "%Y%m%d").date()
    except ValueError:
        logger.error("❌ 날짜 형식이 잘못되었습니다. YYYYMMDD 형식으로 입력해주세요. (예: 20240315)")
        return []

    # 세션 파일 생성 및 클라이언트 초기화
    client = TelegramClient('my_session', api_id, api_hash)

    # 클라이언트 시작 (처음 실행 시 터미널에서 인증 코드 입력 필요)
    logger.info("⏳ 텔레그램 클라이언트 시작 중...")
    client.start(phone=phone)

    messages_data = []

    try:
        # 채널 엔티티(정보) 가져오기
        channel = client.get_entity(channel_url)
        logger.info(f"✅ 채널 '{channel.title}'에 성공적으로 연결되었습니다.")
        logger.info(f"🔍 {target_date_str} 일자의 메시지를 검색합니다...")

        # 채널의 메시지를 최신순으로 가져옵니다.
        for message in client.iter_messages(channel):
            # Message 타입 체크(isinstance)를 제거하고 속성 존재 여부로 확인
            if hasattr(message, 'date') and message.date and not getattr(message, 'action', None):
                # 메시지 날짜를 UTC 기준으로 사용
                msg_utc = message.date
                msg_date = msg_utc.date()

                # 타겟 날짜와 일치하는 경우 데이터 저장
                if msg_date == target_date:
                    has_media = False
                    media_type = None

                    # 메시지에 미디어 객체가 존재하는지 확인
                    if getattr(message, 'media', None):
                        has_media = True
                        # 미디어의 구체적인 타입 분류
                        # 1. 가장 먼저 웹페이지 링크(미리보기)인지 확인
                        if getattr(message, 'web_preview', None):
                            media_type = 'web link'
                        # 2. 실제 업로드된 사진인 경우
                        elif getattr(message, 'photo', None):
                            media_type = 'photo'
                        # 3. 동영상인 경우
                        elif getattr(message, 'video', None):
                            media_type = 'video'
                        # 4. 일반 파일/문서인 경우
                        elif getattr(message, 'document', None):
                            media_type = 'document'
                        # 5. 기타 미디어
                        else:
                            media_type = 'other media'

                    msg_dict = {
                        'id': message.id,
                        'date': msg_utc.isoformat(),
                        'text': message.message or "",
                        'views': message.views,
                        'forwards': message.forwards,
                        'url': f"https://t.me/{channel_url}/{message.id}",
                        'has_media': has_media,
                        'media_type': media_type,
                    }

                    messages_data.append(msg_dict)
                    logger.info(f"  -> 메시지 발견: [ID: {message.id}] {msg_utc.strftime('%H:%M:%S')}")

                # 순회 중인 메시지의 날짜가 타겟 날짜보다 과거로 넘어가면 탐색 종료 (최적화)
                elif msg_date < target_date:
                    logger.info("🏁 타겟 날짜 이전의 메시지에 도달하여 탐색을 종료합니다.")
                    break

    except Exception as e:
        logger.error(f"❌ 오류가 발생했습니다: {e}")
    finally:
        # 클라이언트 연결 종료
        client.disconnect()

    return messages_data


def save_to_json(data, filename):
    """
    수집된 데이터를 JSON 파일로 저장합니다.
    """
    if not data:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return

    try:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            # ensure_ascii=False 를 통해 한글 깨짐 방지
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"💾 총 {len(data)}개의 메시지가 '{filename}'에 성공적으로 저장되었습니다.")
    except Exception as e:
        logger.error(f"❌ 파일 저장 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="특정 일자의 텔레그램 채널 메시지를 수집합니다.")
    parser.add_argument(
        "--date", "-d",
        type=str,
        default=None,
        help="추출하고자 하는 타겟 일자 (YYYYMMDD 형식, 기본값: 오늘 날짜)"
    )
    parser.add_argument(
        "positional_date",
        nargs="?",
        type=str,
        default=None,
        help="추출하고자 하는 타겟 일자 (위치 인자, YYYYMMDD 형식)"
    )
    args = parser.parse_args()

    # 인자 우선순위: --date/-d -> positional_date -> 오늘 날짜
    target_date_str = args.date or args.positional_date or dt.datetime.now().strftime("%Y%m%d")

    # 날짜 유효성 검사
    try:
        dt.datetime.strptime(target_date_str, "%Y%m%d")
    except ValueError:
        logger.error(f"❌ 날짜 형식이 잘못되었습니다: '{target_date_str}'. YYYYMMDD 형식으로 입력해주세요. (예: 20260724)")
        sys.exit(1)

    logger.info(f"📅 대상 수집 일자: {target_date_str}")

    for channel_url in CHANNEL_URLS:
        logger.info(f"\n===== {channel_url} 채널 수집 시작 =====")
        # 메시지 수집
        scraped_messages = fetch_messages_by_date(
            api_id=API_ID,
            api_hash=API_HASH,
            phone=PHONE_NUMBER,
            channel_url=channel_url,
            target_date_str=target_date_str
        )

        # JSON 저장
        if scraped_messages:
            output_filename = f"telegram_{channel_url}_{target_date_str}.json"
            output_path = os.path.join(OUTPUT_DIR, target_date_str, output_filename)
            save_to_json(scraped_messages, output_path)
        logger.info(f"===== {channel_url} 채널 수집 종료 =====")
