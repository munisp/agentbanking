#!/bin/bash
# Generate self-signed SSL certificates for development
# For production, use Let's Encrypt or a proper CA

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem \
  -out fullchain.pem \
  -subj "/C=NG/ST=Lagos/L=Lagos/O=54Link/CN=localhost"

echo "✅ Self-signed certificates generated"
echo "   - fullchain.pem"
echo "   - privkey.pem"
