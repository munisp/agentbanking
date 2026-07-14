#!/bin/bash

NS="54agent"

kubectl apply -f "./manifests/service-account.yaml" -n "$NS"
