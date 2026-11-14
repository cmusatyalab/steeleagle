package vehicle

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"

	vehiclepb "github.com/cmusatyalab/steeleagle/api/go/steeleagle_protocol/v1/services/vehicle"
	"google.golang.org/grpc/codes"
)

// upload uploads chunks as the mission name to v.
func upload(t *testing.T, v *Vehicle, name string, chunks ...string) error {
	t.Helper()
	stream, err := vehiclepb.NewLoaderServiceClient(v.conn).UploadMission(callCtx(t))
	if err != nil {
		return err
	}
	for i, chunk := range chunks {
		req := vehiclepb.UploadMissionRequest_builder{
			Filename: name,
			Chunk:    []byte(chunk),
			Number:   int32(i + 1),
			Total:    int32(len(chunks)),
		}.Build()
		if err := stream.Send(req); err != nil {
			return err
		}
		if _, err := stream.Recv(); err != nil {
			return err
		}
	}
	return stream.CloseSend()
}

// installMission copies the test mission into the mission directory of v as
// name, without execute permission, like an upload.
func installMission(t *testing.T, v *Vehicle, name string) {
	t.Helper()
	b, err := os.ReadFile(missionBinary)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(v.MissionDir, name), b, 0600); err != nil {
		t.Fatal(err)
	}
}

// loadMission loads the mission name on v.
func loadMission(t *testing.T, v *Vehicle, name string) error {
	t.Helper()
	_, err := vehiclepb.NewLoaderServiceClient(v.conn).LoadMission(callCtx(t),
		vehiclepb.LoadMissionRequest_builder{Name: name}.Build())
	return err
}

// getMissions lists the missions of v by name, and returns the active one.
func getMissions(t *testing.T, v *Vehicle) (map[string]*vehiclepb.MissionInfo, *vehiclepb.MissionInfo) {
	t.Helper()
	resp, err := vehiclepb.NewLoaderServiceClient(v.conn).GetMissions(callCtx(t), &vehiclepb.GetMissionsRequest{})
	if err != nil {
		t.Fatal(err)
	}
	missions := map[string]*vehiclepb.MissionInfo{}
	for _, m := range resp.GetMissions() {
		missions[m.GetName()] = m
	}
	return missions, resp.GetActiveMission()
}

// TestUploadMission checks that an uploaded mission is saved, and listed with
// its hash, and that an upload replaces a mission of the same name.
func TestUploadMission(t *testing.T) {
	v, _ := newTestVehicle(t)
	for _, chunks := range [][]string{{"first ", "mission"}, {"second"}} {
		if err := upload(t, v, "a", chunks...); err != nil {
			t.Fatal(err)
		}
		var content string
		for _, c := range chunks {
			content += c
		}
		b, err := os.ReadFile(filepath.Join(v.MissionDir, "a"))
		if err != nil || string(b) != content {
			t.Errorf("saved %q (%v), want %q", b, err, content)
		}
		missions, active := getMissions(t, v)
		hash := sha256.Sum256([]byte(content))
		if len(missions) != 1 || missions["a"].GetHash() != hex.EncodeToString(hash[:]) {
			t.Errorf("missions are %v, want a with the hash of %q", missions, content)
		}
		if missions["a"].GetCreationTime() == nil {
			t.Error("mission has no creation time")
		}
		if active != nil {
			t.Errorf("active mission is %v, want none", active)
		}
	}
}

// TestUploadMissionInvalid checks that a mission can't be saved outside the
// mission directory.
func TestUploadMissionInvalid(t *testing.T) {
	v, _ := newTestVehicle(t)
	expectCode(t, upload(t, v, "../a", "mission"), codes.InvalidArgument)
	if _, err := os.Stat(filepath.Join(filepath.Dir(v.MissionDir), "a")); !os.IsNotExist(err) {
		t.Errorf("mission was saved outside the mission directory (%v)", err)
	}
}

// TestGetMissionsHidesUploads checks that uploads in progress and
// directories are not listed as missions.
func TestGetMissionsHidesUploads(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "idle")
	if err := os.WriteFile(filepath.Join(v.MissionDir, ".b.123.part"), nil, 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(v.MissionDir, "dir"), 0700); err != nil {
		t.Fatal(err)
	}
	if missions, _ := getMissions(t, v); len(missions) != 1 || missions["idle"] == nil {
		t.Errorf("missions are %v, want only idle", missions)
	}
}

// TestLoadMission checks that a loaded mission is made executable and
// becomes the active one, and that missions that aren't in the mission
// directory can't be loaded.
func TestLoadMission(t *testing.T) {
	v, _ := newTestVehicle(t)
	installMission(t, v, "idle")
	installMission(t, v, "other")
	for _, name := range []string{"idle", "other"} {
		if err := loadMission(t, v, name); err != nil {
			t.Fatal(err)
		}
		info, err := os.Stat(filepath.Join(v.MissionDir, name))
		if err != nil {
			t.Fatal(err)
		}
		if info.Mode()&0100 == 0 {
			t.Errorf("mission %s has mode %v, want it executable", name, info.Mode())
		}
		if _, active := getMissions(t, v); active.GetName() != name {
			t.Errorf("active mission is %v, want %s", active, name)
		}
	}
	expectCode(t, loadMission(t, v, "missing"), codes.NotFound)
	expectCode(t, loadMission(t, v, "../idle"), codes.InvalidArgument)
	if _, active := getMissions(t, v); active.GetName() != "other" {
		t.Errorf("active mission is %v after failed loads, want other", active)
	}
}
