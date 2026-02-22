package core

import (
    "os"
    "fmt"
    "time"
    "strings"
    
    "github.com/rs/zerolog"
)

// Log channel object that sends logs to a log writer
var LogChannel = make(chan LogMessage, 1000)

// Log message object that is sent over the log channel
type LogMessage struct {
    data        []byte
    timestamp   time.Time
}

// Writer interface for zerolog that writes logs to a channel as JSON
type ZerologChannelLogger struct {
    logChan   chan<- LogMessage
}

// Write function called on each log write, sends log over the channel
func (i *ZerologChannelLogger) Write(p []byte) (int, error) {
    data := make([]byte, len(p))
    copy(data, p)

    i.logChan <- LogMessage{
        data: data,
        timestamp: time.Now(),
    }

    return len(p), nil
}

// Builds and returns a zerolog logger that writes to console and to the
// log channel
func NewChannelLogger(levelStr string) zerolog.Logger {
    consoleWriter := zerolog.ConsoleWriter{
        Out:        os.Stdout,
        TimeFormat: time.RFC3339,
    }

    chanWriter := &ZerologChannelLogger{
        logChan:    LogChannel,
    }

    multi := zerolog.MultiLevelWriter(consoleWriter, chanWriter)

    level, err := zerolog.ParseLevel(strings.ToLower(levelStr))
    if err != nil {
        fmt.Println("failed to parse log string, switching to INFO level")
        level = zerolog.InfoLevel
    }

    return zerolog.New(multi).With().Timestamp().Logger().Level(level)
}

