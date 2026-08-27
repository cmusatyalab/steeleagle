// Command mission is a mock "self-contained mission binary" fixture for
// missionservice's tests. On start it records that it ran and what client
// socket it was given, then either exits immediately or blocks until killed,
// depending on env vars the test sets before launching missionservice.
package main

import (
	"os"
	"time"
)

func main() {
	marker := os.Getenv("MOCK_MISSION_MARKER")
	if marker == "" {
		os.Exit(1)
	}
	if err := os.WriteFile(marker, []byte(os.Getenv("CLIENT_SOCKET")), 0644); err != nil {
		os.Exit(1)
	}

	if os.Getenv("MOCK_MISSION_BLOCK") == "1" {
		// A bare `select{}` would trip Go's runtime deadlock detector (it can
		// prove the process can never wake up) and exit immediately, which
		// defeats the point of a fixture that's supposed to run until killed.
		// A live timer keeps the runtime convinced progress is still possible.
		for {
			time.Sleep(time.Hour)
		}
	}
}
