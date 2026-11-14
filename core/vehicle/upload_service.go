package vehicle

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/config"
	"github.com/cmusatyalab/steeleagle/v4/core/util/download"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// eaglecName is the name of the mission compiler CompileMission runs, which
// must be on the PATH.
const eaglecName = "eaglec"

// CompileMission compiles a mission on the vehicle with eaglec, saves the
// binary in the vehicle's mission directory under the request's name, and
// loads it as the active mission. The mission is compiled against the driver
// config of the vehicle and a manifest naming the vehicle's engines. This
// overwrites the active mission, but does not delete the old mission file on
// disk.
func (v *Vehicle) CompileMission(
	ctx context.Context,
	req *vehiclepb.CompileMissionRequest,
) (*vehiclepb.CompileMissionResponse, error) {
	name := req.GetName()
	if err := download.CheckFilename(name); err != nil {
		return nil, err
	}
	if len(req.GetMission()) == 0 {
		return nil, status.Error(codes.InvalidArgument, "no mission source given")
	}
	eaglec, err := exec.LookPath(eaglecName)
	if err != nil {
		return nil, status.Errorf(codes.FailedPrecondition,
			"%s is not installed on the vehicle: %v", eaglecName, err)
	}
	// Fail before the compile, which is slow, if the load after it would
	v.missionMu.Lock()
	running := v.mission != nil && v.mission.Running()
	v.missionMu.Unlock()
	if running {
		return nil, status.Error(codes.FailedPrecondition, "cannot load a mission while one is running")
	}

	// The inputs are written to a scratch directory for eaglec to read
	work, err := os.MkdirTemp("", "steeleagle-compile-")
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	defer os.RemoveAll(work)
	pluginToml, err := v.config.ToBytes()
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	manifestToml, err := v.missionManifest(name).ToBytes()
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	source := "mission.dsl"
	if req.GetJson() {
		source = "mission.json"
	}
	args := []string{"dsl", "-errors=text"}
	for _, in := range []struct {
		flag, file string
		data       []byte
	}{
		{"-plugin", "plugin.toml", pluginToml},
		{"-manifest", "manifest.toml", manifestToml},
		{"-flow", "flow.toml", req.GetFlow()},
		{"-geojson", "mission.geojson", req.GetGeojson()},
		{"", source, req.GetMission()},
	} {
		if len(in.data) == 0 {
			continue
		}
		path := filepath.Join(work, in.file)
		if err := os.WriteFile(path, in.data, 0o600); err != nil {
			return nil, status.Error(codes.Internal, err.Error())
		}
		if in.flag != "" {
			args = append(args, in.flag, path)
		}
	}
	if req.GetJson() {
		args = append(args, "-json")
	}
	// The binary is built under a hidden name, which GetMissions skips, and
	// renamed into place only once it is complete
	partial := filepath.Join(v.MissionDir, "."+name+".compiling")
	defer os.Remove(partial)
	args = append(args, "-o", partial, filepath.Join(work, source))

	cmd := exec.CommandContext(ctx, eaglec, args...)
	cmd.Dir = work
	var output bytes.Buffer
	cmd.Stdout, cmd.Stderr = &output, &output
	v.log.Info().Str("mission", name).Msg("compiling mission")
	if err := cmd.Run(); err != nil {
		msg := strings.TrimSpace(output.String())
		v.log.Error().Err(err).Str("mission", name).Str("output", msg).Msg("could not compile mission")
		if ctx.Err() != nil {
			return nil, status.FromContextError(ctx.Err()).Err()
		}
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) && exitErr.ExitCode() == 1 {
			// eaglec exits with 1 on compile errors, which it printed
			return nil, status.Errorf(codes.InvalidArgument, "mission did not compile:\n%s", msg)
		}
		return nil, status.Errorf(codes.Internal, "%s failed: %v\n%s", eaglecName, err, msg)
	}
	if err := os.Rename(partial, filepath.Join(v.MissionDir, name)); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.log.Info().Str("mission", name).Msg("mission compiled")

	if _, err := v.LoadMission(ctx, vehiclepb.LoadMissionRequest_builder{Name: name}.Build()); err != nil {
		return nil, err
	}
	return &vehiclepb.CompileMissionResponse{}, nil
}

// missionManifest returns the manifest a mission called name is compiled
// with on the vehicle, which declares every engine available to the vehicle
// that has a result type.
func (v *Vehicle) missionManifest(name string) *config.MissionManifest {
	manifest := &config.MissionManifest{Info: config.InfoField{Name: name}}
	for engine, info := range v.engines {
		if info == nil || info.Config == nil || info.Config.Engine == nil || info.Config.Engine.Result == "" {
			continue
		}
		manifest.Engines = append(manifest.Engines, config.MissionEngineField{
			Name:   engine,
			Result: info.Config.Engine.Result,
		})
	}
	sort.Slice(manifest.Engines, func(i, j int) bool {
		return manifest.Engines[i].Name < manifest.Engines[j].Name
	})
	return manifest
}

// UploadMission uploads a mission over the network and saves it in the
// vehicle's mission directory. This overwrites the active mission, but does
// not delete the old mission file on disk.
func (v *Vehicle) UploadMission(
	stream grpc.BidiStreamingServer[vehiclepb.UploadMissionRequest, vehiclepb.UploadMissionResponse],
) error {
	return download.DownloadFile(v.log, stream, v.MissionDir, func(number int32) *vehiclepb.UploadMissionResponse {
		return vehiclepb.UploadMissionResponse_builder{Received: number}.Build()
	})
}

// LoadMission loads a mission from the vehicle's mission directory, which
// must exactly match the name of its file.
func (v *Vehicle) LoadMission(
	ctx context.Context,
	req *vehiclepb.LoadMissionRequest,
) (*vehiclepb.LoadMissionResponse, error) {
	name := req.GetName()
	if err := download.CheckFilename(name); err != nil {
		return nil, err
	}
	path := filepath.Join(v.MissionDir, name)
	info, err := os.Stat(path)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, status.Errorf(codes.NotFound, "no mission named %q", name)
	} else if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}
	// Uploads are saved without execute permission, which the plugin needs
	if err := os.Chmod(path, info.Mode().Perm()|0o100); err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	mission, err := plugin.NewBasePlugin(
		plugin.WithName(MissionPluginName),
		plugin.WithPath(path),
		plugin.WithAuthCode(listener.UserCode),
		plugin.WithParentDir(v.runDir),
		plugin.WithLogger(v.log),
		plugin.WithProcessOutputStream(v.out),
	)
	if err != nil {
		v.log.Error().Err(err).Str("mission", name).Msg("could not create mission plugin")
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}

	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.mission != nil && v.mission.Running() {
		return nil, status.Error(codes.FailedPrecondition, "cannot load a mission while one is running")
	}
	v.stopMission() // clean up after a mission that exited on its own
	v.mission, v.missionName = mission, name
	v.log.Info().Str("mission", name).Msg("mission loaded")
	return &vehiclepb.LoadMissionResponse{}, nil
}

// GetMissions lists all the missions in the vehicle's mission directory, and
// the active mission, if there is one.
func (v *Vehicle) GetMissions(
	ctx context.Context,
	req *vehiclepb.GetMissionsRequest,
) (*vehiclepb.GetMissionsResponse, error) {
	entries, err := os.ReadDir(v.MissionDir)
	if err != nil {
		v.log.Error().Err(err).Str("directory", v.MissionDir).Msg("could not list missions")
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.missionMu.Lock()
	active := v.missionName
	if v.mission == nil {
		active = ""
	}
	v.missionMu.Unlock()
	resp := &vehiclepb.GetMissionsResponse{}
	var missions []*vehiclepb.MissionInfo
	for _, entry := range entries {
		// Uploads in progress are hidden
		if !entry.Type().IsRegular() || strings.HasPrefix(entry.Name(), ".") {
			continue
		}
		info, err := v.describeMission(entry.Name())
		if err != nil {
			v.log.Warn().Err(err).Str("mission", entry.Name()).Msg("could not read mission")
			continue
		}
		missions = append(missions, info)
		if entry.Name() == active {
			resp.SetActiveMission(info)
		}
	}
	resp.SetMissions(missions)
	return resp, nil
}

// describeMission describes the mission name in the mission directory, using its
// last modification time, when its upload finished, as its creation time.
func (v *Vehicle) describeMission(name string) (*vehiclepb.MissionInfo, error) {
	f, err := os.Open(filepath.Join(v.MissionDir, name))
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return nil, err
	}
	hash := sha256.New()
	if _, err := io.Copy(hash, f); err != nil {
		return nil, err
	}
	return vehiclepb.MissionInfo_builder{
		Name:         name,
		Hash:         hex.EncodeToString(hash.Sum(nil)),
		CreationTime: timestamppb.New(info.ModTime()),
	}.Build(), nil
}
