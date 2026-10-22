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

// UploadMission uploads a mission over the network and saves it to MissionDir.
func (v *Vehicle) UploadMission(
	stream grpc.BidiStreamingServer[vehiclepb.UploadMissionRequest, vehiclepb.UploadMissionResponse],
) error {
	return download.DownloadFile(v.log, stream, v.MissionDir,
		func(number int32) *vehiclepb.UploadMissionResponse {
			return vehiclepb.UploadMissionResponse_builder{Received: number}.Build()
		})
}

// LoadMission loads a mission from MissionDir by exact name. The mission
// binary runs as a plugin with AuthCode UserCode, in place of the mission
// that was loaded, if any, and becomes the mission the vehicle's mission
// service relays to.
func (v *Vehicle) LoadMission(
	ctx context.Context,
	req *vehiclepb.LoadMissionRequest,
) (*vehiclepb.LoadMissionResponse, error) {
	name := req.GetName()
	path, err := v.missionPath(name)
	if err != nil {
		return nil, err
	}
	// Uploads are saved without execute permission, which the plugin needs
	info, err := os.Stat(path)
	if err == nil {
		err = os.Chmod(path, info.Mode().Perm()|0o100)
	}
	if err != nil {
		v.log.Error().Err(err).Str("mission", name).Msg("could not make mission executable")
		return nil, status.Error(codes.Internal, err.Error())
	}

	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.runCtx.Err() != nil {
		return nil, status.Error(codes.Unavailable, "vehicle is shutting down")
	}
	v.stopMission()

	mission, err := plugin.NewBasePlugin(
		plugin.WithName(MissionPluginName),
		plugin.WithPath(path),
		plugin.WithAuthCode(listener.UserCode),
		plugin.WithParentDir(v.RunDir),
		plugin.WithLogger(v.log),
	)
	if err != nil {
		v.log.Error().Err(err).Str("mission", name).Msg("could not create mission plugin")
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	// The mission lives until it is replaced or the run stops, not as long as
	// this call
	missionCtx, cancel := context.WithCancel(v.runCtx)
	ln, conn, err := mission.Start(missionCtx)
	if err != nil {
		cancel()
		v.log.Error().Err(err).Str("mission", name).Msg("could not start mission plugin")
		return nil, status.Error(codes.Internal, err.Error())
	}
	v.mission = &pluginInfo{obj: mission, ln: ln, conn: conn, name: name, cancel: cancel}

	// The mission calls the vehicle's services through its listener
	server := v.server
	go func() {
		if err := server.Serve(ln); err != nil {
			v.log.Debug().Err(err).Str("listener", "mission").Msg("listener closed")
		}
	}()
	v.log.Info().Str("mission", name).Msg("mission loaded")
	return &vehiclepb.LoadMissionResponse{}, nil
}

// GetMissions lists the missions in MissionDir and the active mission.
func (v *Vehicle) GetMissions(
	ctx context.Context,
	req *vehiclepb.GetMissionsRequest,
) (*vehiclepb.GetMissionsResponse, error) {
	entries, err := os.ReadDir(v.MissionDir)
	if err != nil {
		v.log.Error().Err(err).Str("directory", v.MissionDir).Msg("could not list missions")
		return nil, status.Error(codes.Internal, err.Error())
	}
	var missions []*vehiclepb.MissionInfo
	for _, entry := range entries {
		// Uploads in progress are hidden
		if !entry.Type().IsRegular() || strings.HasPrefix(entry.Name(), ".") {
			continue
		}
		info, err := v.missionInfo(entry.Name())
		if err != nil {
			// The mission may have been replaced since it was listed
			v.log.Warn().Err(err).Str("mission", entry.Name()).Msg("could not read mission")
			continue
		}
		missions = append(missions, info)
	}
	resp := vehiclepb.GetMissionsResponse_builder{Missions: missions}.Build()

	v.missionMu.Lock()
	defer v.missionMu.Unlock()
	if v.mission != nil && v.mission.obj.Running() {
		if info, err := v.missionInfo(v.mission.name); err == nil {
			resp.SetActiveMission(info)
		}
	}
	return resp, nil
}

// missionPath returns the path of the mission name in MissionDir, which must
// be a file directly within it.
func (v *Vehicle) missionPath(name string) (string, error) {
	if name == "" || name != filepath.Base(name) || strings.HasPrefix(name, ".") {
		return "", status.Errorf(codes.InvalidArgument, "invalid mission name %q", name)
	}
	path := filepath.Join(v.MissionDir, name)
	info, err := os.Stat(path)
	if errors.Is(err, fs.ErrNotExist) {
		return "", status.Errorf(codes.NotFound, "no mission named %q", name)
	} else if err != nil {
		return "", status.Error(codes.Internal, err.Error())
	}
	if !info.Mode().IsRegular() {
		return "", status.Errorf(codes.InvalidArgument, "mission %q is not a file", name)
	}
	return path, nil
}

// missionInfo describes the mission name in MissionDir. Linux keeps no
// creation time that Go can read, so the last modification time, when the
// upload finished, is used.
func (v *Vehicle) missionInfo(name string) (*vehiclepb.MissionInfo, error) {
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

// stopMission stops the loaded mission, if any. The caller must hold
// missionMu.
func (v *Vehicle) stopMission() {
	if v.mission == nil {
		return
	}
	v.mission.cancel()
	v.mission.obj.Wait()
	if v.mission.conn != nil {
		v.mission.conn.Close()
	}
	if v.mission.ln != nil {
		v.mission.ln.Close()
	}
	v.log.Info().Str("mission", v.mission.name).Msg("mission stopped")
	v.mission = nil
}
