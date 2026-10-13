package sdk

import (
	"errors"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Sentinel errors for the SDK.
var (
	ErrFieldNotPresent    = errors.New("field not present, returning default value")
	ErrCannotVerify       = errors.New("couldn't verify expectation but command completed")
	ErrFailedExpectation  = errors.New("command stalled but setpoint was not reached")
	ErrPermissionDenied   = errors.New("command permission denied by the vehicle")
	ErrTimeout            = errors.New("timeout occurred before command could complete")
	ErrFailedPrecondition = errors.New("command failed because a pre-condition was not met")
	ErrUnimplemented      = errors.New("command is not implemented by this service")
	ErrInternal           = errors.New("service experienced an internal error")
	ErrCancelled          = errors.New("setpoint changed by new command")
	ErrContextExpired     = errors.New("context has expired")
)

// grpcToSentinel gets the sentinel error from a gRPC error.
func grpcToSentinel(err error) error {
	switch status.Code(err) {
	case codes.OK:
		return nil
	case codes.PermissionDenied:
		return ErrPermissionDenied
	case codes.FailedPrecondition:
		return ErrFailedPrecondition
	case codes.Unimplemented:
		return ErrUnimplemented
	case codes.DeadlineExceeded:
		return ErrContextExpired
	default:
		return ErrInternal
	}
}
