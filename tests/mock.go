package test

import (
	driverpb "github.com/cmusatyalab/steeleagle/api/gen/go/v1/services/driver"
)

type controlServer struct {
	driverpb.UnimplementedControlServiceServer
}

//func (i *controlServer) TakeOff(in *driverpb.TakeOffRequest, stream driverpb.ControlService_TakeOffServer) error {
//	stream.Send(&pb.Response{})
//	return nil
//}
//
//type missionServer struct {
//	pb.UnimplementedMissionServiceServer
//}
//
//func (i *missionServer) Start(in *missionpb.StartMissionRequest, stream missionpb.MissionService_StartServer) error {
//	stream.Send(&pb.Response{})
//	return nil
//}
//
//func (i *missionServer) Stop(in *missionpb.StopMissionRequest, stream pb.MissionService_StopServer) error {
//	stream.Send(&pb.Response{})
//	return nil
//}
