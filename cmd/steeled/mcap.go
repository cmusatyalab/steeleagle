package main

import (
	"bytes"
	"context"
	"os"
	"time"

	pb "github.com/cmusatyalab/steeleagle/runtime/protos"
	"github.com/foxglove/mcap/go/mcap"
	"go.nanomsg.org/mangos/v3"
	"go.nanomsg.org/mangos/v3/protocol/sub"
	_ "go.nanomsg.org/mangos/v3/transport/all"
)

type RecordType int

const (
	ConsoleLog RecordType = 1 << iota // 0x00000001
	Telemetry                         // 0x00000010
	Imagery                           // 0x00000100
	Results                           // 0x00001000
)

type MCAPLogger struct {
	writer     *mcap.Writer
	dataReader mangos.Socket
	// Bitmask that determines which topics are logged
	topicMask RecordType
	// Context related attributes
	ctx    context.Context
	cancel context.CancelFunc
}

func NewMCAPLogger(parentCtx context.Context, dataSockAddr string) (*MCAPLogger, error) {
	// Set up new context
	ctx, cancel := context.WithCancel(parentCtx)

	// Open the log file as an MCAP file
	f, err := os.Create(filename)
	if err != nil {
		logger.Error().Err(err).Str("file", filename).Msg("couldn't open mcap file")
		return nil, err
	}

	writer, err := mcap.NewWriter(f, &mcap.WriterOptions{
		Compression: mcap.CompressionZSTD,
		ChunkSize:   8 * 1024 * 1024, // Chunk size optimized for images
	})

	// Write schema and channels
	// Log schema
	if err = writer.WriteSchema(&mcap.Schema{
		ID:       uint16(ConsoleLog),
		Name:     "log",
		Encoding: "application/json",
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create log schema")
	}
	if err = writer.WriteChannel(&mcap.Channel{
		ID:       uint16(ConsoleLog),
		SchemaID: uint16(ConsoleLog),
		Topic:    "log",
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create log channel")
	}

	// Telemetry schema
	if err = writer.WriteSchema(&mcap.Schema{
		ID:       uint16(Telemetry),
		Name:     "steeleagle.protocol.messages.Telemetry",
		Encoding: "protobuf",
		Data:     pb.DescriptorFile,
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create telemetry schema")
	}
	if err = writer.WriteChannel(&mcap.Channel{
		ID:       uint16(Telemetry),
		SchemaID: uint16(Telemetry),
		Topic:    "telemetry",
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create telemetry channel")
	}

	// Imagery schema TODO: this should be a JPG channel not protobuf
	if err = writer.WriteSchema(&mcap.Schema{
		ID:       uint16(Imagery),
		Name:     "steeleagle.protocol.messages.Frame",
		Encoding: "protobuf",
		Data:     pb.DescriptorFile,
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create imagery schema")
	}
	if err = writer.WriteChannel(&mcap.Channel{
		ID:       uint16(Imagery),
		SchemaID: uint16(Imagery),
		Topic:    "imagery",
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create imagery channel")
	}

	// Results schema
	if err = writer.WriteSchema(&mcap.Schema{
		ID:       uint16(Results),
		Name:     "steeleagle.protocol.results.ComputeResult",
		Encoding: "protobuf",
		Data:     pb.DescriptorFile,
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create result schema")
	}
	if err = writer.WriteChannel(&mcap.Channel{
		ID:       uint16(Results),
		SchemaID: uint16(Results),
		Topic:    "results",
	}); err != nil {
		logger.Error().Err(err).Msg("couldn't create result channel")
	}
	if err != nil {
		return nil, err
	}

	// Open socket to read incoming data from the data proxy
	dataReader, err := sub.NewSocket()
	if err != nil {
		logger.Error().Err(err).Msg("couldn't open data socket to proxy")
	}
	if err = dataReader.SetOption(mangos.OptionSubscribe, []byte("")); err != nil {
		logger.Error().Err(err).Msg("failed to subcribe to all topics")
	}
	if err = dataReader.SetOption(mangos.OptionRecvDeadline, time.Duration(0)); err != nil {
		logger.Error().Err(err).Msg("failed to set non-blocking behavior")
	}
	if err = dataReader.Dial(dataSockAddr); err != nil {
		logger.Error().Err(err).Msg("failed to dial data out socket")
	}
	if err != nil {
		return nil, err
	}

	// Create logger object and run
	mcapLogger := &MCAPLogger{
		writer:      writer,
		dataReader:  dataReader,
		telemetryHz: telemetryHz,
		imageryHz:   imageryHz,
		ctx:         ctx,
		cancel:      cancel,
	}

	go mcapLogger.run()
	return mcapLogger, nil
}

func (i *MCAPLogger) run() {
	defer i.writer.Close()
	for {
		// Attempt read from log channel
		if i.topicMask&ConsoleLog != 0 {
			select {
			case msg := <-LogChannel:
				i.writer.WriteMessage(&mcap.Message{
					ChannelID: uint16(ConsoleLog),
					Sequence:  0,
					LogTime:   uint64(time.Now().UnixNano()),
					Data:      msg.data,
				})
			default:
			}
		}

		// Attempt to read from the socket
		data, err := i.dataReader.Recv()
		if err == nil {
			switch {
			case (i.topicMask&Telemetry != 0) && bytes.HasPrefix(data, []byte("telemetry")):
				if len(data) > 9 {
					i.writer.WriteMessage(&mcap.Message{
						ChannelID: uint16(Telemetry),
						Sequence:  0,
						LogTime:   uint64(time.Now().UnixNano()),
						Data:      data[9:],
					})
				}
			case (i.topicMask&Imagery != 0) && bytes.HasPrefix(data, []byte("imagery")):
				// TODO: Encode to JPG
				if len(data) > 7 {
					i.writer.WriteMessage(&mcap.Message{
						ChannelID: uint16(Imagery),
						Sequence:  0,
						LogTime:   uint64(time.Now().UnixNano()),
						Data:      data[7:],
					})
				}
			case (i.topicMask&Results != 0) && bytes.HasPrefix(data, []byte("results")):
				if len(data) > 7 {
					i.writer.WriteMessage(&mcap.Message{
						ChannelID: uint16(Results),
						Sequence:  0,
						LogTime:   uint64(time.Now().UnixNano()),
						Data:      data[7:],
					})
				}
			}
		}

		// Check if context has been canceled
		select {
		case <-i.ctx.Done():
			return
		default:
		}
	}
}

func (i *MCAPLogger) Close() {
	i.cancel()
}
