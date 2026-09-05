"""log.py：初始化幂等、活动流队列、success 级别。"""

from __future__ import annotations

import logging

from deli_eplus import log as applog


def test_setup_idempotent_single_feed():
    applog.setup()
    applog.setup()
    feed = applog.feed()
    assert feed is not None
    log1 = applog.get("test")
    log2 = applog.get("test")
    assert log1 is log2
    handlers = [h for h in applog.get("test").parent.handlers
                if isinstance(h, applog.ActivityFeedHandler)]
    assert len(handlers) == 1


def test_feed_receives_and_drains():
    applog.setup()
    feed = applog.feed()
    log = applog.get("feedtest")
    feed.drain()  # 清空此前积累
    log.info("普通消息")
    log.success("成功消息")
    log.warning("警告消息")
    items = feed.drain()
    assert [level for _, level in items] == [
        logging.INFO, applog.SUCCESS, logging.WARNING,
    ]


def test_success_level_registered():
    assert logging.getLevelName(applog.SUCCESS) == "SUCCESS"
    logger = applog.get("success_test")
    logger.success("ok")  # 不抛异常即可


def test_feed_capacity_drops_oldest():
    handler = applog.ActivityFeedHandler(capacity=3)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    for i in range(5):
        record = logging.LogRecord("t", logging.INFO, "f", 1, f"m{i}", None, None)
        handler.emit(record)
    items = handler.drain()
    assert [msg for msg, _ in items] == ["m2", "m3", "m4"]
