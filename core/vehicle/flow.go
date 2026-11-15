package vehicle

import (
	"slices"
	"strings"

	driverpb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/driver"
	"github.com/cmusatyalab/steeleagle/config"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// Prefixes of the node names of a dataflow. A flow names nodes relative to the
// vehicle, so the same flow runs on any vehicle:
//   - vehicle.<stream>: the vehicle's telemetry, or one of its cameras;
//   - local.<engine>.<producer>: a producer of an engine on the vehicle's
//     daemon;
//   - local.<engine> and remote.<engine>: an engine on the vehicle's daemon or
//     on the orchestrator.
//
// Producers of remote engines can't be used: Uriel's producers are on the
// device, with the client.
const (
	VehiclePrefix = "vehicle."
	LocalPrefix   = config.LocationLocal + "."
	RemotePrefix  = config.LocationRemote + "."
)

// resolvedFlow is a dataflow as the vehicle runs it.
type resolvedFlow struct {
	// spec is the flow's Uriel spec, which knows every node by its fully
	// qualified name.
	spec string
	// cameras is the request to stream the flow's cameras.
	cameras *driverpb.StreamCamerasRequest
	// names maps each engine's Uriel name to its name in the flow, which its
	// results are stored under.
	names map[string]string
}

// resolveFlow checks flow against the vehicle and qualifies its names:
// vehicle.<stream> with the vehicle's name, local.<...> with the local
// qualifier, and remote.<engine> with the remote one. Every producer must be
// telemetry, a camera, or a producer a local engine advertises; every engine
// must be one the vehicle can reach, at the location its prefix names; and at
// most one camera may be primary. It fails with InvalidArgument.
func (v *Vehicle) resolveFlow(flow *config.FlowConfig) (*resolvedFlow, error) {
	r := &resolvedFlow{
		cameras: &driverpb.StreamCamerasRequest{},
		names:   make(map[string]string, len(flow.Engines)),
	}
	spec := config.FlowConfig{
		Producers: slices.Clone(flow.Producers),
		Engines:   slices.Clone(flow.Engines),
		Edges:     slices.Clone(flow.Edges),
	}
	rename := make(map[string]string, len(flow.Producers)+len(flow.Engines))
	var secondaries []*driverpb.CameraRequest
	for i, p := range flow.Producers {
		name, camera, err := v.resolveProducer(p.Name)
		if err != nil {
			return nil, err
		}
		if camera != nil {
			cr := driverpb.CameraRequest_builder{Id: camera.Name, Uri: name}.Build()
			if !camera.Primary {
				secondaries = append(secondaries, cr)
			} else if r.cameras.HasPrimary() {
				return nil, status.Errorf(codes.InvalidArgument, "cameras %q and %q are both primary",
					r.cameras.GetPrimary().GetId(), camera.Name)
			} else {
				r.cameras.SetPrimary(cr)
			}
		}
		spec.Producers[i].Name, rename[p.Name] = name, name
	}
	r.cameras.SetSecondaries(secondaries)
	for i, e := range flow.Engines {
		name, err := v.resolveEngine(e)
		if err != nil {
			return nil, err
		}
		spec.Engines[i].Name, rename[e.Name] = name, name
		r.names[name] = e.Name
	}
	// An edge naming no node is left for Uriel to reject
	for i, e := range spec.Edges {
		if n, ok := rename[e.From]; ok {
			spec.Edges[i].From = n
		}
		if n, ok := rename[e.To]; ok {
			spec.Edges[i].To = n
		}
	}
	b, err := spec.ToBytes()
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	r.spec = string(b)
	return r, nil
}

// resolveProducer returns the fully qualified name of the flow producer name,
// and its camera if it is one.
func (v *Vehicle) resolveProducer(name string) (string, *config.DriverCamera, error) {
	if stream, ok := strings.CutPrefix(name, VehiclePrefix); ok {
		if stream == TelemetryProducerName {
			return v.producerUri(stream), nil, nil
		}
		camera, err := v.config.Driver.GetCamera(stream)
		if err != nil {
			return "", nil, status.Errorf(codes.InvalidArgument, "producer %q: the vehicle has no camera %q", name, stream)
		}
		return v.producerUri(camera.Name), &camera, nil
	}
	if rest, ok := strings.CutPrefix(name, LocalPrefix); ok {
		i := strings.LastIndex(rest, ".")
		if i <= 0 || i == len(rest)-1 {
			return "", nil, status.Errorf(codes.InvalidArgument, "producer %q must be %s<engine>.<producer>", name, LocalPrefix)
		}
		engine, producer := rest[:i], rest[i+1:]
		full := v.qualifyLocal(engine)
		info, ok := v.engines[full]
		if !ok || info == nil || !info.Local {
			return "", nil, status.Errorf(codes.InvalidArgument, "producer %q: no local engine %q", name, engine)
		}
		if info.Config == nil || info.Config.Engine == nil {
			return "", nil, status.Errorf(codes.InvalidArgument, "producer %q: engine %q has no engine config", name, engine)
		}
		if _, err := info.Config.Engine.GetProducer(producer); err != nil {
			return "", nil, status.Errorf(codes.InvalidArgument, "producer %q: engine %q has no producer %q", name, engine, producer)
		}
		return engineProducerUri(full, producer), nil, nil
	}
	if strings.HasPrefix(name, RemotePrefix) {
		return "", nil, status.Errorf(codes.InvalidArgument,
			"producer %q is of a remote engine; only the vehicle's streams and local engines' producers can be used", name)
	}
	return "", nil, status.Errorf(codes.InvalidArgument,
		"unknown producer %q: producers must start with %q or %q", name, VehiclePrefix, LocalPrefix)
}

// resolveEngine returns the fully qualified name of the flow engine e, which
// must be at the location its prefix names.
func (v *Vehicle) resolveEngine(e config.Engine) (string, error) {
	var bare, full string
	var local bool
	if b, ok := strings.CutPrefix(e.Name, LocalPrefix); ok {
		bare, full, local = b, v.qualifyLocal(b), true
	} else if b, ok := strings.CutPrefix(e.Name, RemotePrefix); ok {
		if v.compute.rcs == "" {
			return "", status.Errorf(codes.InvalidArgument, "engine %q is remote, but the vehicle has no orchestrator", e.Name)
		}
		bare, full = b, v.qualifyRemote(b)
	} else {
		return "", status.Errorf(codes.InvalidArgument,
			"unknown engine %q: engines must start with %q or %q", e.Name, LocalPrefix, RemotePrefix)
	}
	if bare == "" {
		return "", status.Errorf(codes.InvalidArgument, "engine %q has no name", e.Name)
	}
	if want := strings.TrimSuffix(e.Name[:len(e.Name)-len(bare)], "."); e.Location != want {
		return "", status.Errorf(codes.InvalidArgument, "engine %q has location %q, want %q", e.Name, e.Location, want)
	}
	if info, ok := v.engines[full]; !ok || info == nil || info.Local != local {
		where := "the vehicle's daemon"
		if !local {
			where = "the orchestrator"
		}
		return "", status.Errorf(codes.InvalidArgument, "engine %q: no engine %q on %s", e.Name, bare, where)
	}
	return full, nil
}

// qualifyLocal is the fully qualified name of an engine on the vehicle's daemon.
func (v *Vehicle) qualifyLocal(engine string) string {
	return v.compute.localQual + "." + engine
}

// qualifyRemote is the fully qualified name of an engine on the orchestrator.
func (v *Vehicle) qualifyRemote(engine string) string {
	return v.compute.remoteQual + "." + engine
}

// flowEngineName is the name a flow knows the engine full (a key of the
// engine map) by: local.<engine> or remote.<engine>.
func (v *Vehicle) flowEngineName(full string, info *EngineInfo) string {
	if info != nil && info.Local {
		return LocalPrefix + strings.TrimPrefix(full, v.compute.localQual+".")
	}
	return RemotePrefix + strings.TrimPrefix(full, v.compute.remoteQual+".")
}

// engineProducerUri is the fully qualified name of the producer the engine
// (by its fully qualified name) advertises, which the engine publishes on.
func engineProducerUri(engine, producer string) string {
	return engine + "." + producer
}

// localEngineProducers returns the fully qualified names of the producers
// local engines advertise, sorted: the only engine producers a flow can use.
func (v *Vehicle) localEngineProducers() []string {
	var names []string
	for full, info := range v.engines {
		if info == nil || !info.Local || info.Config == nil || info.Config.Engine == nil {
			continue
		}
		for _, p := range info.Config.Engine.Producers {
			names = append(names, engineProducerUri(full, p.Name))
		}
	}
	slices.Sort(names)
	return names
}
