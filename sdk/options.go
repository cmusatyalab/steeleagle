package sdk

import (
	"time"

	"github.com/rs/zerolog"
)

// ContextOption sets the optional parameters of a vehicle context.
type ContextOption func(*vehicleContext)

// WithLogger sets the logger object for all vehicleContext calls.
func WithLogger(l zerolog.Logger) ContextOption {
	return func(v *vehicleContext) {
		v.log = l
	}
}

// WaitOption is a functional option for WaitOptions.
type WaitOption func(*WaitOptions)

// WithPollInterval sets the poll interval of the Wait call.
func WithPollInterval(t time.Duration) WaitOption {
	return func(w *WaitOptions) {
		w.Interval = t
	}
}

// WithTimeout sets the timeout of the Wait call.
func WithTimeout(t time.Duration) WaitOption {
	return func(w *WaitOptions) {
		w.Timeout = t
	}
}

// WithStall sets the stall timeout of the Wait call.
func WithStall(t time.Duration) WaitOption {
	return func(w *WaitOptions) {
		w.Stall = t
	}
}

// WithPositionTolerance sets the position tolerance of the waiter [meters].
func WithPositionTolerance(t float32) WaitOption {
	return func(w *WaitOptions) {
		w.Tolerances.PosTol = t
	}
}

// WithAngleTolerance sets the angular tolerance of the waiter [degrees].
func WithAngleTolerance(t float32) WaitOption {
	return func(w *WaitOptions) {
		w.Tolerances.AngleTol = t
	}
}

// WithSpeedTolerance sets the speed tolerance of the waiter [meters/second].
func WithSpeedTolerance(t float32) WaitOption {
	return func(w *WaitOptions) {
		w.Tolerances.SpeedTol = t
	}
}

// WithAngularSpeedTolerance sets the angular speed tolerance of the waiter
// [degrees/second].
func WithAngularSpeedTolerance(t float32) WaitOption {
	return func(w *WaitOptions) {
		w.Tolerances.AngSpeedTol = t
	}
}
