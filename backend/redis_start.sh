#!/bin/bash

CONTAINER_NAME="redisinsight"
PORT="8001"

# Stop and remove any existing container to avoid conflicts
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Removing old container..."
    docker rm -f $CONTAINER_NAME
fi

echo "Running RedisInsight in foreground..."

docker run \
  --name $CONTAINER_NAME \
  -p $PORT:8001 \
  -v redisinsight:/data \
  redis/redisinsight:latest