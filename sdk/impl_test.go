package sdk

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"reflect"
	"strings"
	"testing"
	"time"

	commonpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/common"
	resultpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/result"
	telemetrypb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/messages/telemetry"
	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/sdk/enums"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
)

// Query bounds the tests set with opt.WithQueryStart and opt.WithQueryEnd.
var (
	queryStart = time.Date(2026, 10, 23, 12, 0, 0, 0, time.UTC)
	queryEnd   = queryStart.Add(time.Minute)
)

// testResultContext provides a mock vehicle context whose GetResult
// returns results, recording each request in reqs.
func testResultContext(reqs *[]*vehiclepb.GetResultRequest, results []*resultpb.ComputeResult, err error) *vehicleContext {
	return &vehicleContext{ctx: context.Background(), data: &fakeDataClient{
		result: func(req *vehiclepb.GetResultRequest) (*vehiclepb.GetResultResponse, error) {
			*reqs = append(*reqs, req)
			if err != nil {
				return nil, err
			}
			return vehiclepb.GetResultResponse_builder{Result: results}.Build(), nil
		},
	}}
}

// requireDone checks that a Get* waiter is already done after Wait, with
// the error it returned.
func requireDone[Resp any](t *testing.T, w *Waiter[Resp], wantErr error) Resp {
	t.Helper()
	resp, err := w.Wait()
	if !errors.Is(err, wantErr) {
		t.Fatalf("Wait() error = %v, want %v", err, wantErr)
	}
	if done, checkErr := w.Check(); !done || !errors.Is(checkErr, wantErr) {
		t.Fatalf("Check() = %v, %v; want true, %v", done, checkErr, wantErr)
	}
	return resp
}

// requireQueryRange checks that q has the start and end time given, where a
// zero time means none.
func requireQueryRange(t *testing.T, q timeRange, start, end time.Time) {
	t.Helper()
	if q.HasTimeStart() != !start.IsZero() || (!start.IsZero() && !q.GetTimeStart().AsTime().Equal(start)) {
		t.Errorf("query start = %v (set %v), want %v", q.GetTimeStart(), q.HasTimeStart(), start)
	}
	if q.HasTimeEnd() != !end.IsZero() || (!end.IsZero() && !q.GetTimeEnd().AsTime().Equal(end)) {
		t.Errorf("query end = %v (set %v), want %v", q.GetTimeEnd(), q.HasTimeEnd(), end)
	}
}

// TestGetTelemetryReturnsAll checks that GetTelemetry returns every
// telemetry the vehicle returns, in order.
func TestGetTelemetryReturnsAll(t *testing.T) {
	older := telemetrypb.Telemetry_builder{Mode: modeP(telemetrypb.Mode_MODE_LOITER)}.Build()
	latest := telemetrypb.Telemetry_builder{Mode: modeP(telemetrypb.Mode_MODE_GUIDED)}.Build()
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		return vehiclepb.GetTelemetryResponse_builder{Telemetry: []*telemetrypb.Telemetry{older, latest}}.Build(), nil
	})

	tel := requireDone(t, v.GetTelemetry(), nil)
	if len(tel) != 2 {
		t.Fatalf("len(telemetry) = %d, want 2", len(tel))
	}
	for i, want := range []telemetrypb.Mode{telemetrypb.Mode_MODE_LOITER, telemetrypb.Mode_MODE_GUIDED} {
		if mode, err := tel[i].GetMode(); err != nil || mode != enums.Mode(want) {
			t.Errorf("telemetry[%d].GetMode() = %v, %v; want %v", i, mode, err, enums.Mode(want))
		}
	}
}

// TestGetTelemetryQueryRange checks that GetTelemetry queries the time range
// its options give, and only the most recent telemetry without them.
func TestGetTelemetryQueryRange(t *testing.T) {
	tests := map[string]struct {
		options    []opt.Option[opt.QueryOption]
		start, end time.Time
	}{
		"most recent": {},
		"start":       {options: []opt.Option[opt.QueryOption]{opt.WithQueryStart[opt.QueryOption](queryStart)}, start: queryStart},
		"end":         {options: []opt.Option[opt.QueryOption]{opt.WithQueryEnd[opt.QueryOption](queryEnd)}, end: queryEnd},
		"start and end": {
			options: []opt.Option[opt.QueryOption]{
				opt.WithQueryStart[opt.QueryOption](queryStart), opt.WithQueryEnd[opt.QueryOption](queryEnd),
			},
			start: queryStart, end: queryEnd,
		},
	}
	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			fake := &fakeDataClient{respond: func() (*vehiclepb.GetTelemetryResponse, error) {
				return vehiclepb.GetTelemetryResponse_builder{}.Build(), nil
			}}
			v := &vehicleContext{ctx: context.Background(), data: fake}

			requireDone(t, v.GetTelemetry(tt.options...), nil)
			requireQueryRange(t, fake.lastTelemetry, tt.start, tt.end)
		})
	}
}

// TestGetTelemetryEmpty checks that GetTelemetry with no telemetry succeeds
// with none.
func TestGetTelemetryEmpty(t *testing.T) {
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		return vehiclepb.GetTelemetryResponse_builder{}.Build(), nil
	})

	if tel := requireDone(t, v.GetTelemetry(), nil); len(tel) != 0 {
		t.Errorf("telemetry = %v, want none", tel)
	}
}

// TestGetTelemetryRPCError checks that a failed GetTelemetry RPC is
// reported as its sentinel error.
func TestGetTelemetryRPCError(t *testing.T) {
	v := testVehicleContext(context.Background(), func() (*vehiclepb.GetTelemetryResponse, error) {
		return nil, status.Error(codes.PermissionDenied, "denied")
	})

	requireDone(t, v.GetTelemetry(), ErrPermissionDenied)
}

// TestGetResults checks that each Get*Result queries its engine and returns
// every result's contents, in order.
func TestGetResults(t *testing.T) {
	class := "person"
	tests := map[string]struct {
		results []*resultpb.ComputeResult // older first
		check   func(*testing.T, *vehicleContext)
	}{
		"detection": {
			results: []*resultpb.ComputeResult{
				resultpb.ComputeResult_builder{DetectionResult: resultpb.DetectionResult_builder{
					Detections: []*resultpb.Detection{resultpb.Detection_builder{ClassName: "dog"}.Build()},
				}.Build()}.Build(),
				resultpb.ComputeResult_builder{DetectionResult: resultpb.DetectionResult_builder{
					Detections: []*resultpb.Detection{resultpb.Detection_builder{ClassName: "car", Score: 0.8}.Build()},
				}.Build()}.Build(),
			},
			check: func(t *testing.T, v *vehicleContext) {
				r := requireDone(t, v.GetDetectionResult("engine"), nil)
				if len(r) != 2 {
					t.Fatalf("len(results) = %d, want 2", len(r))
				}
				if d := r[0].GetDetections(); len(d) != 1 || d[0].GetClassName() != "dog" {
					t.Errorf("results[0].GetDetections() = %v, want one dog", d)
				}
				if d := r[1].GetDetections(); len(d) != 1 || d[0].GetClassName() != "car" || d[0].GetScore() != 0.8 {
					t.Errorf("results[1].GetDetections() = %v, want one car with score 0.8", d)
				}
			},
		},
		"classification": {
			results: []*resultpb.ComputeResult{
				resultpb.ComputeResult_builder{ClassificationResult: resultpb.ClassificationResult_builder{
					Score: 0.9, Class: &class,
				}.Build()}.Build(),
			},
			check: func(t *testing.T, v *vehicleContext) {
				r := requireDone(t, v.GetClassificationResult("engine"), nil)
				if len(r) != 1 {
					t.Fatalf("len(results) = %d, want 1", len(r))
				}
				if got, err := r[0].GetClass(); err != nil || got != class || r[0].GetScore() != 0.9 {
					t.Errorf("result = %q (%v), score %v; want %q, score 0.9", got, err, r[0].GetScore(), class)
				}
			},
		},
		"guidance": {
			results: []*resultpb.ComputeResult{
				resultpb.ComputeResult_builder{GuidanceResult: resultpb.GuidanceResult_builder{
					Trajectory: commonpb.Velocity_builder{XVel: f32(1.5)}.Build(),
				}.Build()}.Build(),
			},
			check: func(t *testing.T, v *vehicleContext) {
				r := requireDone(t, v.GetGuidanceResult("engine"), nil)
				if len(r) != 1 {
					t.Fatalf("len(results) = %d, want 1", len(r))
				}
				traj, err := r[0].GetTrajectory()
				if err != nil {
					t.Fatalf("GetTrajectory() error = %v", err)
				}
				if x, err := traj.GetXVel(); err != nil || x != 1.5 {
					t.Errorf("GetXVel() = %v, %v; want 1.5", x, err)
				}
			},
		},
		"position": {
			results: []*resultpb.ComputeResult{
				resultpb.ComputeResult_builder{PositionResult: resultpb.PositionResult_builder{
					GlobalPosition: commonpb.GlobalPosition_builder{Latitude: f64(40.4), Longitude: f64(-79.9)}.Build(),
				}.Build()}.Build(),
			},
			check: func(t *testing.T, v *vehicleContext) {
				r := requireDone(t, v.GetPositionResult("engine"), nil)
				if len(r) != 1 {
					t.Fatalf("len(results) = %d, want 1", len(r))
				}
				if _, err := r[0].GetRelativePosition(); !errors.Is(err, ErrFieldNotPresent) {
					t.Errorf("GetRelativePosition() error = %v, want ErrFieldNotPresent", err)
				}
				gp, err := r[0].GetGlobalPosition()
				if err != nil {
					t.Fatalf("GetGlobalPosition() error = %v", err)
				}
				if lat, err := gp.GetLatitude(); err != nil || lat != 40.4 {
					t.Errorf("GetLatitude() = %v, %v; want 40.4", lat, err)
				}
			},
		},
		"generic": {
			results: []*resultpb.ComputeResult{
				resultpb.ComputeResult_builder{GenericResult: resultpb.GenericResult_builder{Payload: []byte("first")}.Build()}.Build(),
				resultpb.ComputeResult_builder{GenericResult: resultpb.GenericResult_builder{Payload: []byte("second")}.Build()}.Build(),
			},
			check: func(t *testing.T, v *vehicleContext) {
				r := requireDone(t, v.GetGenericResult("engine"), nil)
				if len(r) != 2 || string(r[0].GetPayload()) != "first" || string(r[1].GetPayload()) != "second" {
					t.Errorf("results = %v, want payloads first and second", r)
				}
			},
		},
	}
	for name, tt := range tests {
		t.Run(name, func(t *testing.T) {
			var reqs []*vehiclepb.GetResultRequest
			v := testResultContext(&reqs, tt.results, nil)
			tt.check(t, v)
			if len(reqs) != 1 || reqs[0].GetEngine() != "engine" {
				t.Errorf("queried %v, want engine once", reqs)
			}
		})
	}
}

// TestGetResultQueryRange checks that Get*Result queries the time range its
// options give, and only the most recent result without them.
func TestGetResultQueryRange(t *testing.T) {
	var reqs []*vehiclepb.GetResultRequest
	v := testResultContext(&reqs, nil, nil)

	requireDone(t, v.GetDetectionResult("engine"), nil)
	requireDone(t, v.GetDetectionResult("engine",
		opt.WithQueryStart[opt.QueryOption](queryStart), opt.WithQueryEnd[opt.QueryOption](queryEnd)), nil)
	if len(reqs) != 2 {
		t.Fatalf("queried %d times, want 2", len(reqs))
	}
	requireQueryRange(t, reqs[0], time.Time{}, time.Time{})
	requireQueryRange(t, reqs[1], queryStart, queryEnd)
	if reqs[1].GetEngine() != "engine" {
		t.Errorf("queried engine %q, want engine", reqs[1].GetEngine())
	}
}

// TestGetResultSkipsOtherTypes checks that Get*Result returns only the
// results of its type, so results of another type are skipped.
func TestGetResultSkipsOtherTypes(t *testing.T) {
	var reqs []*vehiclepb.GetResultRequest
	results := []*resultpb.ComputeResult{
		resultpb.ComputeResult_builder{ClassificationResult: resultpb.ClassificationResult_builder{Score: 0.1}.Build()}.Build(),
		resultpb.ComputeResult_builder{GenericResult: resultpb.GenericResult_builder{Payload: []byte("payload")}.Build()}.Build(),
		resultpb.ComputeResult_builder{ClassificationResult: resultpb.ClassificationResult_builder{Score: 0.9}.Build()}.Build(),
	}
	v := testResultContext(&reqs, results, nil)

	r := requireDone(t, v.GetClassificationResult("engine"), nil)
	if len(r) != 2 || r[0].GetScore() != 0.1 || r[1].GetScore() != 0.9 {
		t.Errorf("results = %v, want the two classifications only", r)
	}
	if r := requireDone(t, v.GetDetectionResult("engine"), nil); len(r) != 0 {
		t.Errorf("detection results = %v, want none", r)
	}
}

// TestGetResultNoResultsYet checks that Get*Result for an engine the
// vehicle has no results for (NotFound) succeeds with none.
func TestGetResultNoResultsYet(t *testing.T) {
	var reqs []*vehiclepb.GetResultRequest
	v := testResultContext(&reqs, nil, status.Error(codes.NotFound, `nothing stored for "engine"`))

	if r := requireDone(t, v.GetDetectionResult("engine"), nil); len(r) != 0 {
		t.Errorf("results = %v, want none", r)
	}
}

// TestGetResultRPCError checks that a failed GetResult RPC is reported as
// its sentinel error.
func TestGetResultRPCError(t *testing.T) {
	tests := map[codes.Code]error{
		codes.PermissionDenied: ErrPermissionDenied,
		codes.Unimplemented:    ErrUnimplemented,
		codes.Unavailable:      ErrInternal,
	}
	for code, want := range tests {
		t.Run(code.String(), func(t *testing.T) {
			var reqs []*vehiclepb.GetResultRequest
			v := testResultContext(&reqs, nil, status.Error(code, "failed"))
			requireDone(t, v.GetPositionResult("engine"), want)
		})
	}
}

// TestGetResultLogs checks that Get*Result logs with its command, the
// queried engine, the query's time range and the number of results.
func TestGetResultLogs(t *testing.T) {
	var buf bytes.Buffer
	var reqs []*vehiclepb.GetResultRequest
	results := []*resultpb.ComputeResult{
		resultpb.ComputeResult_builder{GenericResult: resultpb.GenericResult_builder{}.Build()}.Build(),
	}
	v := testResultContext(&reqs, results, nil)
	WithLogger(zerolog.New(&buf).Level(zerolog.DebugLevel))(v)

	requireDone(t, v.GetGenericResult("yolo", opt.WithQueryStart[opt.QueryOption](queryStart)), nil)
	for _, want := range []string{
		`"command":"GetGenericResult"`, `"engine":"yolo"`, `"start":"2026-10-23T12:00:00Z"`, `"count":1`,
		"fetched engine results",
	} {
		if !strings.Contains(buf.String(), want) {
			t.Errorf("log missing %s:\n%s", want, buf.String())
		}
	}
}

// TestCommandsLogRPCErrors checks that every Vehicle command whose RPC fails
// logs the RPC's own error and gRPC status, not just the sentinel error it
// returns. Every method is called, so a new command can't skip it.
func TestCommandsLogRPCErrors(t *testing.T) {
	// The vehicle can't connect, so every RPC fails with Unavailable
	conn, err := grpc.NewClient("passthrough:///127.0.0.1:1", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()

	vehicleType := reflect.TypeFor[Vehicle]()
	for i := range vehicleType.NumMethod() {
		method := vehicleType.Method(i)
		if method.Name == "Ctx" {
			continue
		}
		t.Run(method.Name, func(t *testing.T) {
			var buf bytes.Buffer
			v := NewVehicleFromContext(context.Background(), conn, WithLogger(zerolog.New(&buf).Level(zerolog.DebugLevel)))
			// Zero values for every non-variadic parameter
			var args []reflect.Value
			for j := range method.Type.NumIn() {
				if method.Type.IsVariadic() && j == method.Type.NumIn()-1 {
					break
				}
				args = append(args, reflect.Zero(method.Type.In(j)))
			}
			waiter := reflect.ValueOf(v).MethodByName(method.Name).Call(args)[0]
			if err, _ := waiter.MethodByName("Wait").Call(nil)[1].Interface().(error); !errors.Is(err, ErrInternal) {
				t.Fatalf("Wait() error = %v, want ErrInternal", err)
			}

			var entry map[string]any
			for _, line := range strings.Split(strings.TrimSpace(buf.String()), "\n") {
				if strings.Contains(line, `"message":"command failed"`) {
					if err := json.Unmarshal([]byte(line), &entry); err != nil {
						t.Fatal(err)
					}
				}
			}
			if entry == nil {
				t.Fatalf("no command failed log in:\n%s", buf.String())
			}
			if entry["command"] != method.Name || entry["code"] != "Unavailable" || entry["returned"] != ErrInternal.Error() {
				t.Errorf("command failed log = %v, want command %s, code Unavailable, returned ErrInternal", entry, method.Name)
			}
			if logged, _ := entry["error"].(string); logged == "" || logged == ErrInternal.Error() {
				t.Errorf("logged error = %q, want the RPC's own error", logged)
			}
		})
	}
}
