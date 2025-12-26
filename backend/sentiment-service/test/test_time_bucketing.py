from sentiment_service.utils.time import bucket_epoch_seconds_to_hour


def test_normal_timestamp():
    bucket = bucket_epoch_seconds_to_hour(1766567348)
    assert bucket.hour_start_utc == 1766566800
    assert bucket.hour_end_utc == 1766570400


def test_exact_hour_boundary():
    bucket = bucket_epoch_seconds_to_hour(1766566800)
    assert bucket.hour_start_utc == 1766566800
    assert bucket.hour_end_utc == 1766570400


def test_last_second_of_hour():
    bucket = bucket_epoch_seconds_to_hour(1766570399)
    assert bucket.hour_start_utc == 1766566800
    assert bucket.hour_end_utc == 1766570400


def test_invalid_timestamp():
    try:
        bucket_epoch_seconds_to_hour(-1)
        assert False
    except ValueError:
        assert True
