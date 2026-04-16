package util

import (
    "os"
    "fmt"
    "time"
    "strings"
    
    "github.com/rs/zerolog"
)

// Log message object that is sent over the log channel
type LogMessage struct {
    data        []byte
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
    }

    return len(p), nil
}

// Builds and returns a zerolog logger that writes to console and to the
// log channel
func NewChannelLogger(logCfg LogConfig) zerolog.Logger {
    consoleWriter := zerolog.ConsoleWriter{
        Out:        os.Stdout,
        TimeFormat: time.RFC3339,
    }

    level, err := zerolog.ParseLevel(strings.ToLower(logCfg.Level))
    if err != nil {
        fmt.Println("failed to parse log string, switching to INFO level")
        level = zerolog.InfoLevel
    }
    
    if logCfg.Channel != nil {
        chanWriter := &ZerologChannelLogger{
            logChan:    logCfg.Channel,
        }

        multi := zerolog.MultiLevelWriter(consoleWriter, chanWriter)
        
        return zerolog.New(multi).With().Str("name", logCfg.Name).Timestamp().Logger().Level(level)
    } else {
        return zerolog.New(consoleWriter).With().Str("name", logCfg.Name).Timestamp().Logger().Level(level)
    }
}

