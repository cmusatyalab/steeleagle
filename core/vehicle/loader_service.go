package vehicle

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"github.com/cmusatyalab/steeleagle/v4/core/util/download"
	"github.com/cmusatyalab/steeleagle/v4/core/util/listener"
	"github.com/cmusatyalab/steeleagle/v4/core/util/plugin"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/timestamppb"
)

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
