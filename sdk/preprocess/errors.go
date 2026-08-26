package preprocess

// PreprocessError is an error generated while pre-processing SDK source
// (scrubbing or generating params), optionally attributed to the line it
// originated from.
type PreprocessError struct {
	error
	LineNo uint32 // the line number the error originates from (optional)
}

// Unwrap returns the underlying error, so errors.Is and errors.As can see
// past a PreprocessError to whatever it wraps.
func (e *PreprocessError) Unwrap() error {
	return e.error
}
