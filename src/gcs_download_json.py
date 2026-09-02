import os
import sys
import site
import logging
import traceback
import datetime as dt

import pytz
from google.cloud import storage

src_path = os.path.dirname(__file__)
pjt_home_path = os.path.join(src_path, os.pardir, os.pardir)
pjt_home_path = os.path.abspath(pjt_home_path)
site.addsitedir(pjt_home_path)

# 로깅 설정
logger = logging.getLogger(__file__)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s %(lineno)d: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger.setLevel(logging.INFO)
stream_log = logging.StreamHandler(sys.stdout)
stream_log.setFormatter(formatter)
logger.addHandler(stream_log)

kst_timezone = pytz.timezone('Asia/Seoul')

from src.services import tweet_scrapper_post

def download_gcs_to_local(
    file_name: str,
    bucket_name: str ='gcs-private-pjt-data', 
    gcs_base_path: str ='news_data', 
    date_str: str ='20000101',
    local_file_path: str = f'{pjt_home_path}/data'):
    
    """
    Google Cloud Storage에서 파일을 로컬로 다운로드합니다.

    Args:
        file_name (str): 다운로드할 GCS 내의 파일 이름 (예: 'news_data.json').
        bucket_name (str): GCS 버킷 이름.
        gcs_base_path (str): GCS 버킷 내의 기본 경로 (예: 'news_data').
        date_str (str, optional): GCS 경로에 사용할 날짜 문자열 (YYYYMMDD 형식).
                                  지정하지 않으면 과거 날짜 (20000101) 를 사용합니다.
        local_file_path (str): 파일을 저장할 로컬 디렉토리 경로.

    Returns:
        int: 0: 성공, 1: GCS에 파일 없음, 2: GCS 접근 오류
    """
    storage_client = storage.Client()
    try:
        bucket = storage_client.bucket(bucket_name)
    except Exception as e:
        logger.error(f"bucket '{bucket_name}': can not access!! {e}")
        return 2

    gcs_source_path = f"{gcs_base_path}/{date_str}/{file_name}"
    blob = bucket.blob(gcs_source_path)

    if not blob.exists():
        logger.error(f"GCS file 'gs://{bucket_name}/{gcs_source_path}' does not exist!!")
        return 1

    # 로컬 저장 경로 확인 및 생성
    os.makedirs(local_file_path, exist_ok=True)
    destination_file_name = os.path.join(local_file_path, file_name)

    logger.info(f"start download 'gs://{bucket_name}/{gcs_source_path}' to '{destination_file_name}'...")

    try:
        blob.download_to_filename(destination_file_name)
        logger.info(f"finish to download '{file_name}' to '{destination_file_name}'!!!")
    except Exception as e:
        logger.error(f"'{file_name}' download fail!!! => {e}")
        raise

    return 0
    
def local_test():
    file_name = 'rwang07_posts.json'
    ret = download_gcs_to_local(file_name, date_str='20250711')
    logger.info(f"ret => {ret}")
    
def download_gcs_posts_json_to_local(target_user_list:list = [], target_date:str = '20000101'):
    if not target_user_list:
        target_user_list = tweet_scrapper_post.TARGET_USERNAMES

    for target_user in target_user_list:
        file_name = f"{target_user}_posts.json"
        ret = download_gcs_to_local(file_name, date_str=target_date)
        logger.info(f"ret => {ret}")


if __name__ == '__main__':
    # local_test()
    download_gcs_posts_json_to_local(target_date='20250713')