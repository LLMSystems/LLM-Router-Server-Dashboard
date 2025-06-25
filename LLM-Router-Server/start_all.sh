#!/bin/bash

CONFIG_PATH=$1

if [ -z "$CONFIG_PATH" ]; then
  echo "請提供 config.yaml 路徑，例如: ./start_all.sh ./configs/config.yaml"
  exit 1
fi

echo "使用配置檔: $CONFIG_PATH"

# export TORCH_CUDA_ARCH_LIST="8.0"

echo "啟動所有模型..."
python start_all_models.py --config "$CONFIG_PATH" &
sleep 5

echo "啟動 Router Server（gunicorn + uvloop + 多 worker）..."
gunicorn main:app -c gunicorn.conf.py --env CONFIG_PATH="$CONFIG_PATH"

# echo "啟動 router server..."
# python main.py --config "$CONFIG_PATH"