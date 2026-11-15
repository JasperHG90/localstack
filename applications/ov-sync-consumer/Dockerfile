FROM --platform=$BUILDPLATFORM golang:1.27-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -trimpath -ldflags="-s -w" -o /out/ov-sync-consumer .

# No shell and no CA bundle: every call it makes is plain HTTP on the LAN.
# Runs as root because Nomad makes the workload identity JWT unreadable to any
# other user.
FROM scratch
COPY --from=build /out/ov-sync-consumer /ov-sync-consumer
ENTRYPOINT ["/ov-sync-consumer"]
