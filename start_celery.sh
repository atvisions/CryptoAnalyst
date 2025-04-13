#!/bin/bash

# 启动 Celery Worker
celery -A config worker -l info &

# 启动 Celery Beat
celery -A config beat -l info &

echo "Celery Worker 和 Beat 已启动"
