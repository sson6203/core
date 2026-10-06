# ./build.sh 로 build/ 와 dist/ 를 먼저 만든 뒤 사용합니다.
#   docker buildx build --platform linux/amd64,linux/arm64 -t sound-tools .
FROM scratch
ARG TARGETARCH
COPY build/server-linux-${TARGETARCH} /server
COPY dist/음향도구-통합.html /srv/index.html
USER 65534:65534
ENV PORT=8080 ROOT=/srv
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["/server", "healthcheck"]
ENTRYPOINT ["/server"]
