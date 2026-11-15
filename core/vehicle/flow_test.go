package vehicle

import (
	"strings"
	"testing"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc/codes"
	"google.golang.org/protobuf/proto"
)

// flowOf is a flow fed by producers (flow names, like vehicle.front), each
// to testEngine.
func flowOf(producers ...string) *config.FlowConfig {
	flow := &config.FlowConfig{Engines: []config.Engine{{Name: testFlowEngine, Location: config.LocationLocal}}}
	for _, p := range producers {
		flow.Producers = append(flow.Producers, config.Producer{Name: p})
		flow.Edges = append(flow.Edges, config.Edge{From: p, To: testFlowEngine, Timeout: "1s"})
	}
	return flow
}

// cameraOf is the request for the vehicle's camera name.
func cameraOf(v *Vehicle, name string) *driverpb.CameraRequest {
	return driverpb.CameraRequest_builder{Id: name, Uri: v.Name + "." + name}.Build()
}

// testProducer is the producer testEngine advertises in withEngineProducer.
const testProducer = "frames"

// withEngineProducer has testEngine advertise testProducer, and returns its
// name in a flow. It must be called before the vehicle starts.
func withEngineProducer(v *Vehicle) string {
	v.engines[testEngineUri].Config.Engine.Producers = []config.EngineProducer{{
		Name: testProducer, Output: "steeleagle_protocol/v1/messages/frame/EncodedFrame",
	}}
	return LocalPrefix + testEngine + "." + testProducer
}

// withOrchestrator gives the vehicle an orchestrator serving the engine
// remote, and returns its name in a flow. It must be called before the
// vehicle starts.
func withOrchestrator(v *Vehicle, remote string) string {
	v.compute.rcs, v.compute.remoteQual = "orchestrator:5000", "10.0.0.9"
	v.engines["10.0.0.9."+remote] = &EngineInfo{
		Config: &config.PluginConfig{Engine: &config.EngineCap{
			Result:    DetectionResultType,
			Producers: []config.EngineProducer{{Name: testProducer, Output: "o"}},
		}},
	}
	return RemotePrefix + remote
}

// specOf parses the Uriel spec of r.
func specOf(t *testing.T, r *resolvedFlow) *config.FlowConfig {
	t.Helper()
	f, err := config.ParseFlowConfigFromBytes([]byte(r.spec))
	if err != nil {
		t.Fatalf("spec %q: %v", r.spec, err)
	}
	return f
}

// TestResolveVehicleStreams checks that vehicle.<stream> producers are the
// vehicle's telemetry and cameras, qualified with its name, with its primary
// camera as the primary.
func TestResolveVehicleStreams(t *testing.T) {
	v, _ := testVehicle(t)
	telemetry := VehiclePrefix + TelemetryProducerName
	for _, tc := range []struct {
		name      string
		producers []string
		want      *driverpb.StreamCamerasRequest
	}{
		{"none", nil, driverpb.StreamCamerasRequest_builder{}.Build()},
		{"telemetry", []string{telemetry}, driverpb.StreamCamerasRequest_builder{}.Build()},
		{"primary", []string{"vehicle.front"}, driverpb.StreamCamerasRequest_builder{
			Primary: cameraOf(v, "front"),
		}.Build()},
		{"secondary", []string{"vehicle.down", telemetry}, driverpb.StreamCamerasRequest_builder{
			Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
		}.Build()},
		{"both", []string{"vehicle.down", "vehicle.rear"}, driverpb.StreamCamerasRequest_builder{
			Primary:     cameraOf(v, "rear"),
			Secondaries: []*driverpb.CameraRequest{cameraOf(v, "down")},
		}.Build()},
	} {
		r, err := v.resolveFlow(flowOf(tc.producers...))
		if err != nil {
			t.Errorf("%s: %v", tc.name, err)
			continue
		}
		if !proto.Equal(r.cameras, tc.want) {
			t.Errorf("%s: cameras %v, want %v", tc.name, r.cameras, tc.want)
		}
		spec := specOf(t, r)
		for i, p := range tc.producers {
			want := v.Name + "." + strings.TrimPrefix(p, VehiclePrefix)
			if spec.Producers[i].Name != want || spec.Edges[i].From != want {
				t.Errorf("%s: producer %s is %q (edge from %q), want %q",
					tc.name, p, spec.Producers[i].Name, spec.Edges[i].From, want)
			}
		}
	}
}

// TestResolveLocalEngineProducer checks that local.<engine>.<producer> is
// qualified with the local qualifier and streams no camera.
func TestResolveLocalEngineProducer(t *testing.T) {
	v, _ := testVehicle(t)
	frames := withEngineProducer(v)
	r, err := v.resolveFlow(flowOf(frames, "vehicle.front"))
	if err != nil {
		t.Fatal(err)
	}
	want := testEngineUri + "." + testProducer
	spec := specOf(t, r)
	if spec.Producers[0].Name != want || spec.Edges[0].From != want {
		t.Errorf("producer %q (edge from %q), want %q", spec.Producers[0].Name, spec.Edges[0].From, want)
	}
	if cameras := (driverpb.StreamCamerasRequest_builder{Primary: cameraOf(v, "front")}.Build()); !proto.Equal(r.cameras, cameras) {
		t.Errorf("cameras %v, want only the front camera", r.cameras)
	}
}

// TestResolveEngines checks that local.<engine> and remote.<engine> are
// qualified with the local and remote qualifiers, and remembered by their
// flow names for their results.
func TestResolveEngines(t *testing.T) {
	v, _ := testVehicle(t)
	remote := withOrchestrator(v, "gcs")
	flow := flowOf("vehicle.front")
	flow.Engines = append(flow.Engines, config.Engine{Name: remote, Location: config.LocationRemote})
	flow.Edges = append(flow.Edges, config.Edge{From: testFlowEngine, To: remote, Timeout: "1s"})
	r, err := v.resolveFlow(flow)
	if err != nil {
		t.Fatal(err)
	}
	spec := specOf(t, r)
	if spec.Engines[0].Name != testEngineUri || spec.Engines[1].Name != "10.0.0.9.gcs" {
		t.Errorf("engines %+v, want %s and 10.0.0.9.gcs", spec.Engines, testEngineUri)
	}
	if e := spec.Edges[1]; e.From != testEngineUri || e.To != "10.0.0.9.gcs" {
		t.Errorf("edge %+v, want it between the qualified engines", e)
	}
	want := map[string]string{testEngineUri: testFlowEngine, "10.0.0.9.gcs": remote}
	if len(r.names) != 2 || r.names[testEngineUri] != want[testEngineUri] || r.names["10.0.0.9.gcs"] != remote {
		t.Errorf("names %v, want %v", r.names, want)
	}
}

// TestResolveInvalid checks every way a flow's names can fail to resolve,
// and that each is refused as an invalid argument naming the culprit.
func TestResolveInvalid(t *testing.T) {
	v, _ := testVehicle(t)
	frames := withEngineProducer(v)
	engine := func(name, location string) *config.FlowConfig {
		f := flowOf("vehicle.front")
		f.Engines[0] = config.Engine{Name: name, Location: location}
		f.Edges[0].To = name
		return f
	}
	for name, tc := range map[string]struct {
		flow *config.FlowConfig
		want []string
	}{
		"bare stream":          {flowOf("front"), []string{"front", "must start with"}},
		"unknown camera":       {flowOf("vehicle.side"), []string{"vehicle.side", "no camera"}},
		"two primaries":        {flowOf("vehicle.front", "vehicle.rear"), []string{"front", "rear", "primary"}},
		"remote producer":      {flowOf("remote." + testEngine + ".frames"), []string{"remote engine"}},
		"no engine of":         {flowOf("local.other.frames"), []string{"no local engine", "other"}},
		"no such producer":     {flowOf(LocalPrefix + testEngine + ".nope"), []string{"no producer", "nope"}},
		"producer, no name":    {flowOf(LocalPrefix + testEngine), []string{"local.<engine>.<producer>"}},
		"bare engine":          {engine(testEngine, config.LocationLocal), []string{"must start with"}},
		"wrong location":       {engine(testFlowEngine, config.LocationRemote), []string{"location", "remote"}},
		"unknown local engine": {engine("local.missing", config.LocationLocal), []string{"missing", "vehicle's daemon"}},
		"no orchestrator":      {engine("remote.gcs", config.LocationRemote), []string{"no orchestrator"}},
	} {
		_, err := v.resolveFlow(tc.flow)
		if err == nil {
			t.Errorf("%s: resolved, want an error", name)
			continue
		}
		expectCode(t, err, codes.InvalidArgument, tc.want...)
	}
	if _, err := v.resolveFlow(flowOf(frames)); err != nil {
		t.Errorf("the producer itself: %v", err)
	}

	// With an orchestrator: its engines resolve as remote, but never as local,
	// and their producers can't be used.
	remote := withOrchestrator(v, "gcs")
	for name, tc := range map[string]struct {
		flow *config.FlowConfig
		want []string
	}{
		"remote engine's producer": {flowOf(remote + "." + testProducer), []string{"remote engine"}},
		"remote engine as local":   {engine("local.gcs", config.LocationLocal), []string{"gcs", "vehicle's daemon"}},
		"local engine as remote":   {engine(RemotePrefix+testEngine, config.LocationRemote), []string{testEngine, "orchestrator"}},
	} {
		_, err := v.resolveFlow(tc.flow)
		expectCode(t, err, codes.InvalidArgument, tc.want...)
		if err == nil {
			t.Errorf("%s: resolved, want an error", name)
		}
	}
}

// TestFlowEngineName checks the names the vehicle's onboard mission manifest
// declares its engines by.
func TestFlowEngineName(t *testing.T) {
	v, _ := testVehicle(t)
	withOrchestrator(v, "gcs")
	if got := v.flowEngineName(testEngineUri, v.engines[testEngineUri]); got != testFlowEngine {
		t.Errorf("local engine is %q, want %q", got, testFlowEngine)
	}
	if got := v.flowEngineName("10.0.0.9.gcs", v.engines["10.0.0.9.gcs"]); got != "remote.gcs" {
		t.Errorf("remote engine is %q, want remote.gcs", got)
	}
}

// TestSetDataflowEngineProducer checks that a dataflow fed by a local
// engine's producer is set without streaming a camera, and that the results
// of its inputs are stored under the engine's flow name.
func TestSetDataflowEngineProducer(t *testing.T) {
	v, driver := testVehicle(t)
	frames := withEngineProducer(v)
	if _, _, err := v.Start(t.Context()); err != nil {
		t.Fatal(err)
	}
	toml := flowToml(t, frames)
	if err := setDataflow(t, v, toml); err != nil {
		t.Fatal(err)
	}
	expectFlow(t, v, toml)
	expectCameras(t, driver, []*driverpb.StreamCamerasRequest{driverpb.StreamCamerasRequest_builder{}.Build()})
	expectResultStored(t, v, testEngineUri+"."+testProducer)
}

// TestSetDataflowRemoteProducer checks that a dataflow naming a remote
// producer is refused before anything is streamed.
func TestSetDataflowRemoteProducer(t *testing.T) {
	v, driver := newTestVehicle(t)
	expectCode(t, setDataflow(t, v, flowToml(t, "remote.gcs.frames")), codes.InvalidArgument, "remote engine")
	expectFlow(t, v, nil)
	expectCameras(t, driver, nil)
}
