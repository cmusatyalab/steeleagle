package vehicle

import (
	"context"
	"fmt"
	"os"
	"slices"
	"testing"
	"time"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// TestQueryRange ensures that queries return what is stored between their
// start and end times, inclusive, and that an end before the start is
// rejected.
func TestQueryRange(t *testing.T) {
	v := newDataTestVehicle(t, fmt.Sprintf("unused-%d", os.Getpid()))
	for i := range int64(4) {
		data, _ := proto.Marshal(telemetryAt(i))
		if err := v.store(TelemetryBucket, time.Unix(i, 0), data); err != nil {
			t.Fatal(err)
		}
	}
	at := func(seconds int64) *timestamppb.Timestamp { return timestamppb.New(time.Unix(seconds, 0)) }
	for _, tt := range []struct {
		name       string
		start, end *timestamppb.Timestamp
		want       []int64
	}{
		{"most recent", nil, nil, []int64{3}},
		{"since start", at(2), nil, []int64{2, 3}},
		{"up to end", nil, at(1), []int64{0, 1}},
		{"between", at(1), at(2), []int64{1, 2}},
		{"empty", at(10), nil, nil},
	} {
		t.Run(tt.name, func(t *testing.T) {
			req := vehiclepb.GetTelemetryRequest_builder{TimeStart: tt.start, TimeEnd: tt.end}.Build()
			resp, err := v.GetTelemetry(context.Background(), req)
			if err != nil {
				t.Fatal(err)
			}
			var got []int64
			for _, telemetry := range resp.GetTelemetry() {
				got = append(got, telemetry.GetTimestamp().GetSeconds())
			}
			if !slices.Equal(got, tt.want) {
				t.Errorf("got %v, want %v", got, tt.want)
			}
		})
	}

	req := vehiclepb.GetTelemetryRequest_builder{TimeStart: at(2), TimeEnd: at(1)}.Build()
	if _, err := v.GetTelemetry(context.Background(), req); status.Code(err) != codes.InvalidArgument {
		t.Errorf("end before start: got %v, want InvalidArgument", err)
	}
}
