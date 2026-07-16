#!/bin/bash

NS=54agent
CONFIG_FILE_LOCATION="./config/docker.json"

kubectl create secret generic credential \
  --from-file=.dockerconfigjson="$CONFIG_FILE_LOCATION" \
  --type=kubernetes.io/dockerconfigjson \
  --namespace "$NS"

kubectl patch serviceaccount 54agent -p '{"imagePullSecrets": [{"name": "credential"}]}' -n "$NS"
