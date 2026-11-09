FROM alpine:3.22

ARG TARGETARCH
ARG MINIO_RELEASE=RELEASE.2025-09-07T16-13-09Z
ARG MINIO_SHA256_AMD64=7c5bd8512c6e966455b1d198209358b2d191c77a83ab377c4073281065fb855f
ARG MINIO_SHA256_ARM64=5c83cd2cf151717ba0243f73e1c7802ff36e272b67144bdd7f1f7d684fd6f03d

ADD https://github.com/minio/minio/releases/download/${MINIO_RELEASE}/minio.linux-${TARGETARCH}.${MINIO_RELEASE} /usr/local/bin/minio

RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) expected="${MINIO_SHA256_AMD64}" ;; \
        arm64) expected="${MINIO_SHA256_ARM64}" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}"; exit 1 ;; \
    esac; \
    echo "${expected}  /usr/local/bin/minio" | sha256sum -c -; \
    chmod +x /usr/local/bin/minio; \
    apk add --no-cache ca-certificates curl; \
    addgroup -S minio; \
    adduser -S -G minio -h /home/minio minio; \
    mkdir -p /data /home/minio/.minio; \
    chown -R minio:minio /data /home/minio

USER minio

EXPOSE 9000 9001

ENTRYPOINT ["/usr/local/bin/minio"]
