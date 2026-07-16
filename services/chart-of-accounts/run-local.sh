#!/bin/bash
# Load environment variables from .env and run the service

set -a  # automatically export all variables
source .env
set +a

exec go run .
