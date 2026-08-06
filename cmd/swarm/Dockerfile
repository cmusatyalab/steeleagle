# SPDX-FileCopyrightText: 2025 Carnegie Mellon University - LivingEdgeLab
#
# SPDX-License-Identifier: GPL-2.0-only

FROM golang:1.26-bookworm AS build

WORKDIR /src

# Cache module downloads separately from source changes
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/root/go/pkg/mod go mod download

COPY . .
RUN --mount=type=cache,target=/root/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -o /swarm ./cmd/swarm

FROM gcr.io/distroless/static-debian12

LABEL org.opencontainers.image.vendor="CMU Satyalab" \
      org.opencontainers.image.authors=satya-group@lists.andrew.cmu.edu

# tsnet's default state directory is derived from $HOME (via
# os.UserConfigDir); fixing it here makes that state land somewhere a
# volume can be mounted over, so the node's tailnet identity survives a
# container recreate instead of re-registering every time.
ENV HOME=/steeleagle
WORKDIR /steeleagle
COPY --from=build /swarm /steeleagle/swarm

ENTRYPOINT ["/steeleagle/swarm"]
CMD ["-config", "/steeleagle/config.toml"]
