#----------------------------------------------------------------------
# Stage 1: Compile the MinIO Client (mc) binary for RISC-V 64-bit
#----------------------------------------------------------------------
FROM golang:1.24-alpine AS builder

# Set the target architecture and OS for cross-compilation
ENV GOOS=linux
ENV GOARCH=riscv64
ENV CGO_ENABLED=0
ENV GO111MODULE=on

WORKDIR /go/src/github.com/minio/mc

# Copy all source files from the current build context
# NOTE: This assumes you are running the build from the root of the 'mc' repository clone.
COPY . .

# Build the MC client binary
RUN go build -o /usr/bin/mc .

#----------------------------------------------------------------------
# Stage 2: Create the final, minimal image
#----------------------------------------------------------------------
# Use a minimal base image that is available for riscv64
FROM alpine:latest

# Create a non-root user (optional, but good practice for client tools)
RUN adduser -D -g 'MinIO Client' mcuser

# Copy the compiled RISC-V binary from the builder stage
COPY --from=builder /usr/bin/mc /usr/bin/mc

# Set the user
USER mcuser

# Set the entrypoint to the mc binary
# This allows running container as: podman run mc-riscv:latest <mc-command>
ENTRYPOINT ["/usr/bin/mc"]

# Set a default command to provide basic usage info if run without arguments
CMD ["--help"]
