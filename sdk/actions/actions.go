//go:build ignore

package actions

import (
	"context"

	"github.com/cmusatyalab/steeleagle/sdk"
)

type TakeOff struct {
	TakeOffAltitude float32
}

func (i *TakeOff) Execute(ctx context.Context, device sdk.Device) error {
	return device.TakeOff(i.TakeOffRequest).Wait()
}

type Land struct{}

func (i *Land) Execute(ctx context.Context, device sdk.Device) error {
	return device.TakeOff(i.Land).Wait()
}
