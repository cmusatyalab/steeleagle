package events

import (
	"time"

	"github.com/cmusatyalab/steeleagle/sdk"
	"github.com/cmusatyalab/steeleagle/sdk/dsl"
	"github.com/cmusatyalab/steeleagle/sdk/opt"
	"github.com/cmusatyalab/steeleagle/sdk/params"
)

// DetectionFound fires once a result from Engine has at least one detection
// of Class. Only results received after the hosting state was entered count,
// so a detection that triggered an earlier transition can't fire this event
// again.
type DetectionFound struct {
	Engine params.DetectionEngine // engine used for results
	Class  string                 // class to look for
}

func (e *DetectionFound) Monitor(v sdk.Vehicle, m dsl.MissionData) (bool, error) {
	ticker := time.NewTicker(200 * time.Millisecond)
	defer ticker.Stop()
	lastQuery := time.Now() // so we only get new query results
	for {
		select {
		case <-v.Ctx().Done():
			return false, nil
		case <-ticker.C:
			queried := time.Now()
			results, err := v.GetDetectionResult(e.Engine, opt.WithQueryStart[opt.QueryOption](lastQuery)).Wait()
			if err != nil {
				return false, err
			}
			lastQuery = queried
			// Every new result is checked, since several may have arrived
			// between polls
			for _, result := range results {
				for _, d := range result.GetDetections() {
					if d.GetClassName() == e.Class {
						return true, nil
					}
				}
			}
		}
	}
}

var _ dsl.Event = &DetectionFound{}
