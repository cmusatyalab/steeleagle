Role Patrol:
Import:
    "github.com/cmusatyalab/steeleagle/sdk/dsl" v4.0-beta
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions" v4.0-beta
    "github.com/cmusatyalab/steeleagle/sdk/dsl/events" v4.0-beta
    "github.com/cmusatyalab/steeleagle/sdk/dsl/types" v4.0-beta
    "github.com/cmusatyalab/steeleagle/sdk/params" v4.0-beta
Actions:
    actions.TakeOff takeoff()
    actions.Patrol patrol(Altitude=15.0, Area=params.Poly)
Mission:
Start takeoff
During takeoff:
    done -> patrol
