import os
import sys
import site
import logging
import traceback
import pytest

src_path = os.path.dirname(__file__)
pjt_home_path = os.path.join(src_path, os.pardir)
pjt_home_path = os.path.abspath(pjt_home_path)

site.addsitedir(pjt_home_path)

from src import gcs_upload_json

# 로깅 설정
logger = logging.getLogger(__file__)

# 1. 단위테스트 시 필요한 패키지 추가 설치
# pip install pytest pytest-mock
# 2. 단위테스트 실행 커멘드
# pytest -vs tests/test_gcs_upload_json.py
# -v 옵션: 상세한 테스트 결과를 보여줍니다.
# -s 옵션: logging 출력을 캡처하지 않고 표준 출력을 표시합니다 (로그 메시지를 직접 볼 수 있습니다).
# -x 옵션: 첫 실패 시 중단
# --log-level=DEBUG 옵션: 로그 출력 레밸 조정하여 로그 출력


@pytest.fixture
def mock_gcs(mocker):
    """
    Google Cloud Storage 클라이언트, 버킷, 블롭 객체를 목(mock) 처리하는 픽스처.
    """
    # Blob 객체의 upload_from_filename 메서드를 목(mock) 처리합니다.
    mock_blob = mocker.MagicMock()
    mock_blob.upload_from_filename.return_value = None # 성공적인 업로드를 가정

    # Bucket 객체의 blob 메서드를 목(mock) 처리하여 mock_blob을 반환하게 합니다.
    mock_bucket = mocker.MagicMock()
    mock_bucket.blob.return_value = mock_blob

    # Client 객체의 bucket 메서드를 목(mock) 처리하여 mock_bucket을 반환하게 합니다.
    mock_client = mocker.MagicMock()
    mock_client.bucket.return_value = mock_bucket

    # google.cloud.storage.Client를 목(mock) 처리된 클라이언트로 대체합니다.
    mocker.patch('google.cloud.storage.Client', return_value=mock_client)

    return mock_client, mock_bucket, mock_blob

@pytest.fixture
def mock_os_path(mocker):
    """
    os.path.exists와 os.path.basename을 목(mock) 처리하는 픽스처.
    """
    mock_exists = mocker.patch('os.path.exists')
    mock_basename = mocker.patch('os.path.basename')
    return mock_exists, mock_basename

@pytest.fixture
def caplog_setup(caplog):
    """
    pytest의 caplog 픽스처를 사용하여 로깅 레벨을 INFO로 설정합니다.
    """
    caplog.set_level(logging.INFO)
    return caplog

# --- 테스트 케이스들 ---

def test_upload_success(mock_gcs, mock_os_path, caplog_setup):
    """
    로컬 파일이 Google Cloud Storage로 성공적으로 업로드되는지 테스트합니다.
    """
    # 픽스처에서 반환된 목(mock) 객체들을 언팩합니다.
    _, mock_bucket, mock_blob = mock_gcs
    mock_exists, mock_basename = mock_os_path

    # 목(mock) 함수의 반환 값을 설정합니다.
    mock_exists.return_value = True # 로컬 파일이 존재한다고 가정
    mock_basename.return_value = 'my_document.json' # 파일 이름 추출 결과 시뮬레이션

    # 테스트에 사용할 인자들을 정의합니다.
    local_file = '/home/user/data/my_document.json'
    bucket_name = 'my-private-data-bucket'
    gcs_base = 'archive_data'
    date_str = '20231026'

    # 테스트 대상 함수를 호출합니다.
    ret = gcs_upload_json.upload_local_file_to_gcs(local_file, bucket_name, gcs_base, date_str)
    assert ret == 0

    # GCS 관련 목(mock) 메서드들이 올바른 인수로 호출되었는지 검증합니다.
    mock_exists.assert_called_once_with(local_file)
    mock_bucket.blob.assert_called_once_with(f"{gcs_base}/{date_str}/my_document.json")
    mock_blob.upload_from_filename.assert_called_once_with(local_file)

    # 로깅 메시지를 검증합니다.
    assert f"start upload '{local_file}' file to 'gs://{bucket_name}/{gcs_base}/{date_str}/'..." in caplog_setup.text
    assert f"finish to upload 'my_document.json' to 'gs://{bucket_name}/{gcs_base}/{date_str}/my_document.json'!!!" in caplog_setup.text

def test_local_file_not_exists(mock_gcs, mock_os_path, caplog_setup):
    """
    로컬 파일이 존재하지 않을 때 함수가 적절히 처리하는지 테스트합니다.
    """
    mock_exists, _ = mock_os_path
    mock_exists.return_value = False # 로컬 파일이 존재하지 않는다고 가정

    local_file = '/non/existent/path/non_existent_file.txt'

    ret = gcs_upload_json.upload_local_file_to_gcs(local_file)
    assert ret == 1

    # 파일 존재 여부만 확인하고, GCS 관련 작업은 수행되지 않아야 합니다.
    mock_exists.assert_called_once_with(local_file)
    mock_gcs[0].bucket.assert_not_called() # Client().bucket()이 호출되지 않아야 함
    mock_gcs[1].blob.assert_not_called() # bucket.blob()이 호출되지 않아야 함
    mock_gcs[2].upload_from_filename.assert_not_called() # upload_from_filename이 호출되지 않아야 함

    # 오류 로그 메시지를 검증합니다.
    assert f"local data file '{local_file}' doesn't exist!!" in caplog_setup.text
    assert "start upload" not in caplog_setup.text # 업로드 시작 로그는 찍히지 않아야 함

def test_bucket_access_failure(mock_gcs, mock_os_path, caplog_setup):
    """
    GCS 버킷 접근에 실패했을 때 함수가 적절히 처리하는지 테스트합니다.
    """
    mock_client, _, _ = mock_gcs
    mock_exists, _ = mock_os_path

    mock_exists.return_value = True # 로컬 파일은 존재한다고 가정
    # bucket() 호출 시 예외를 발생시키도록 설정합니다.
    mock_client.bucket.side_effect = Exception("Google Cloud Storage API - Permission Denied")

    test_bucket_name = "restricted-access-bucket"
    local_file = '/data/valid_file.json'

    ret = gcs_upload_json.upload_local_file_to_gcs(local_file, bucket_name=test_bucket_name)
    assert ret == 2

    # GCS 관련 메서드 호출 및 로그 검증
    mock_exists.assert_called_once_with(local_file)
    mock_client.bucket.assert_called_once_with(test_bucket_name)
    mock_gcs[1].blob.assert_not_called()
    mock_gcs[2].upload_from_filename.assert_not_called()

    assert f"bucket '{test_bucket_name}': can not access!! Google Cloud Storage API - Permission Denied" in caplog_setup.text
    assert "start upload" not in caplog_setup.text # 업로드 시작 로그는 찍히지 않아야 함

def test_file_upload_failure_raises_exception(mock_gcs, mock_os_path, caplog_setup):
    """
    파일 업로드 중 예외가 발생했을 때 예외가 다시 발생하고 적절한 로그가 남는지 테스트합니다.
    """
    _, _, mock_blob = mock_gcs
    mock_exists, mock_basename = mock_os_path

    mock_exists.return_value = True # 로컬 파일은 존재한다고 가정
    mock_basename.return_value = 'failed_upload_file.json'
    # upload_from_filename() 호출 시 예외를 발생시키도록 설정합니다.
    mock_blob.upload_from_filename.side_effect = Exception("Network error during upload")

    local_file = '/data/some_file_to_fail.json'

    # 원본 함수가 예외를 다시 발생시키므로, pytest.raises를 사용하여 이를 잡습니다.
    with pytest.raises(Exception) as excinfo:
        gcs_upload_json.upload_local_file_to_gcs(local_file)

    # Assertions
    mock_blob.upload_from_filename.assert_called_once_with(local_file)
    assert "Network error during upload" in str(excinfo.value) # 발생한 예외의 메시지 확인

    # 로그 검증
    assert f"start upload '{local_file}' file to 'gs://gcs-private-pjt-data/news_data/20000101/'..." in caplog_setup.text
    assert f"'failed_upload_file.json' upload fail!!! => Network error during upload" in caplog_setup.text


def test_default_date_string(mock_gcs, mock_os_path, caplog_setup):
    """
    date_str이 지정되지 않았을 때 기본값 '20000101'이 사용되는지 테스트합니다.
    """
    _, mock_bucket, mock_blob = mock_gcs
    mock_exists, mock_basename = mock_os_path

    mock_exists.return_value = True
    mock_basename.return_value = 'default_date_test.json'

    local_file = '/path/to/default/date_file.json'
    bucket_name = 'default-test-bucket'
    gcs_base = 'default_news'

    # date_str 인자를 생략하고 함수를 호출합니다.
    gcs_upload_json.upload_local_file_to_gcs(local_file, bucket_name, gcs_base)

    # GCS 경로에 기본 날짜 '20000101'이 사용되었는지 검증합니다.
    mock_bucket.blob.assert_called_once_with(f"{gcs_base}/20000101/default_date_test.json")
    mock_blob.upload_from_filename.assert_called_once_with(local_file)

    # 로그 메시지에서도 기본 날짜가 사용되었는지 확인합니다.
    assert f"start upload '{local_file}' file to 'gs://{bucket_name}/{gcs_base}/20000101/'..." in caplog_setup.text

# --- main 함수 테스트 케이스들 ---

@pytest.fixture
def mock_main_dependencies(mocker):
    """
    main 함수에 필요한 의존성(os.listdir, upload_local_file_to_gcs, sys.exit)을 목(mock) 처리합니다.
    """
    mock_listdir = mocker.patch('os.listdir')
    mock_upload = mocker.patch('src.gcs_upload_json.upload_local_file_to_gcs')
    mock_exit = mocker.patch('sys.exit')
    return mock_listdir, mock_upload, mock_exit

def test_main_uploads_matching_files(mock_main_dependencies, caplog_setup, mocker):
    """
    main 함수가 대상 사이트와 확장자에 맞는 파일을 식별하여 업로드 함수를 호출하는지 테스트합니다.
    """
    mock_listdir, mock_upload, _ = mock_main_dependencies

    # os.listdir가 반환할 파일 목록을 설정합니다.
    pjt_home_path = gcs_upload_json.pjt_home_path
    local_data_dir = os.path.join(pjt_home_path, 'data')
    mock_listdir.return_value = [
        'zdnet_news.json',
        'thelec_news.json',
        'zdnet_other.txt',
        'zdnet_archive.json'
    ]

    target_site = 'zdnet'
    target_ymd = '20240520'

    # 테스트 대상 함수를 호출합니다.
    gcs_upload_json.main(target_news_site=target_site, base_ymd=target_ymd)

    # os.listdir가 올바른 경로로 호출되었는지 확인합니다.
    mock_listdir.assert_called_once_with(local_data_dir)

    # upload_local_file_to_gcs 함수가 올바른 파일에 대해 호출되었는지 확인합니다.
    # main 함수는 target_news_site를 기반으로 gcs_base를 동적으로 생성하므로,
    # 테스트에서 이 값을 명시적으로 확인해야 합니다.
    expected_gcs_base = f"news_data"
    expected_calls = [
        mocker.call(os.path.join(local_data_dir, 'zdnet_news.json'), date_str=target_ymd),
        mocker.call(os.path.join(local_data_dir, 'zdnet_archive.json'), date_str=target_ymd)
    ]
    mock_upload.assert_has_calls(expected_calls, any_order=True)
    assert mock_upload.call_count == 2

    # 건너뛴 파일에 대한 로그가 올바르게 남았는지 확인합니다.
    assert "skip target file...: 'thelec_news.json'" in caplog_setup.text
    assert "skip target file...: 'zdnet_other.txt'" in caplog_setup.text

def test_main_handles_exception(mock_main_dependencies, caplog_setup):
    """
    main 함수 내에서 예외가 발생했을 때, sys.exit(1)을 호출하고 오류를 로깅하는지 테스트합니다.
    """
    mock_listdir, _, mock_exit = mock_main_dependencies

    # os.listdir 호출 시 예외를 발생시키도록 설정합니다.
    error_message = "Directory not found"
    mock_listdir.side_effect = FileNotFoundError(error_message)

    gcs_upload_json.main(target_news_site='zdnet', base_ymd='20240520')

    # sys.exit(1)이 호출되었는지 확인합니다.
    mock_exit.assert_called_once_with(1)
    # 오류 메시지가 로그에 기록되었는지 확인합니다.
    assert error_message in caplog_setup.text

if __name__ == "__main__":
    exit_code = pytest.main(["-v", __file__])
    if exit_code == 0:
        print("✅ 모든 테스트 통과")
    else:
        print("❌ 테스트 실패")