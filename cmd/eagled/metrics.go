package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/zerolog/log"
)

const (
	// metricsPath is where eagled serves its Prometheus metrics.
	metricsPath = "/metrics"
	// metricsReadHeaderTimeout bounds how long a scrape may take to send its
	// request headers.
	metricsReadHeaderTimeout = 5 * time.Second
	// metricsShutdownTimeout bounds how long a shutdown waits for a scrape
	// in progress.
	metricsShutdownTimeout = 5 * time.Second
)

// serveMetrics serves the Prometheus metrics, among them the vehicles'
// Gabriel metrics and the host's, on port until ctx ends.
func serveMetrics(ctx context.Context, port int) {
	if host, err := newHostCollector(); err != nil {
		log.Warn().Err(err).Msg("cannot read the host's metrics; serving the rest")
	} else if err := prometheus.Register(host); err != nil {
		log.Warn().Err(err).Msg("registering the host's metrics")
	}

	mux := http.NewServeMux()
	mux.Handle(metricsPath, promhttp.Handler())
	server := &http.Server{
		Addr:              fmt.Sprintf(":%d", port),
		Handler:           mux,
		ReadHeaderTimeout: metricsReadHeaderTimeout,
	}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), metricsShutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			log.Err(err).Msg("shutting down the metrics server")
		}
	}()

	go func() {
		log.Info().Int("port", port).Msgf("serving Prometheus metrics on port %d", port)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Err(err).Msg("metrics server failed")
		}
	}()
}
