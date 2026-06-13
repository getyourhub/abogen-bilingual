#!/bin/bash

# Script to build and push Docker image to Docker Hub

set -e

# Configuration
DOCKER_USERNAME="getyourhub"
IMAGE_NAME="abogen-bilingual"
TAG="latest"

echo "Building Docker image..."
docker build -f Dockerfile.simple -t $DOCKER_USERNAME/$IMAGE_NAME:$TAG .

echo "Pushing to Docker Hub..."
docker push $DOCKER_USERNAME/$IMAGE_NAME:$TAG

echo "Done! Image pushed to $DOCKER_USERNAME/$IMAGE_NAME:$TAG"