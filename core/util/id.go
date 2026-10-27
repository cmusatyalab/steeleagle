package util

import (
	"encoding/hex"

	"github.com/google/uuid"
)

// shortId returns a short random ID, which saves space when socket path lengths
// are a concern.
func ShortId() string {
	id := uuid.New()
	return hex.EncodeToString(id[:4])
}
