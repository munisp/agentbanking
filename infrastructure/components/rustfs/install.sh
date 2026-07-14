helm upgrade --install rustfs rustfs/rustfs -n rustfs --create-namespace \
    --set ingress.enabled="false" \
    --set storageclass.name="rook-ceph-block"
    