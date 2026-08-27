Role Patrol:
Import:
    "github.com/cmusatyalab/steeleagle/sdk/dsl/actions"
    "github.com/cmusatyalab/steeleagle/sdk/params"
Actions:
    actions.TakeOff takeoff()
    actions.Patrol patrol(Altitude=15.0, Area=params.Poly)
Mission:
Start takeoff
During takeoff:
    done -> patrol
