package opt

import "time"

// WaitOptions are the options for a waiter, the poll interval and the
// timeout. Timeout set to zero means that the Wait will never time out.
type WaitOptions struct {
	Interval   time.Duration
	Timeout    time.Duration
	Tolerances Tolerances
}

// Tolerances are the tolerances waiters use to decide when a command has
// satisfied its expectation.
type Tolerances struct {
	PosTol      float32
	AngleTol    float32
	SpeedTol    float32
	AngSpeedTol float32
}

// WaitOption is a functional option for waitOptions.
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
