---
sidebar_position: 1
toc_max_heading_level: 5
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Structure

SteelEagle DSL files are a text representation of a [finite state machine](https://www.mathworks.com/discovery/state-machine.html).
A finite state machine (FSM) is a computing model that contains three types, states, trigger events, and transition functions. States can represent anything, but in 
SteelEagle, they represent the current task that the vehicle is executing. Trigger events are events that happen during execution, e.g. the current task is done or
a person was detected. Transition functions are functions which determine which state the FSM should move to given a trigger event. 

In this way, the FSM can compactly model complex logic. Take for instance the following UAV mission: take off and patrol a provided area; if you see a person,
track and follow them; if you lose the person, go back to patrolling. If battery levels drop below 50%, return to home.
Here is a representation of the accompanying FSM and an example SteelEagle DSL implementation:

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events: # Definitions of trigger events
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission: # Definitions of transitions
        Start: take_off
        During take_off:
            done -> patrol
        During patrol:
            done -> patrol
            person_seen -> track
            battery_low -> return_to_home
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
    ```
  </TabItem>
</Tabs>

## Syntax

The SteelEagle DSL is based on a [Pydantic](https://docs.pydantic.dev/latest/) model architecture. 
Pydantic is a Python library that introduces strong typing to Python, and allows for "compile-time"
validation/type-checking. This is especially important for SteelEagle, since its core protocol is
based on strongly-typed Protobuf which could cause runtime errors during vehicle motion if users
make easy-to-miss type errors. There are three core types in the SteelEagle DSL Pydantic model:

### Datatypes

Datatypes represent any kind of data which is used during the mission. For example, the [`Location`](/sdk/python/steeleagle_sdk/api/datatypes/common#class-location)
object used as the target of a [`SetGlobalPosition`](/sdk/python/steeleagle_sdk/api/actions/primitives/control#class-setglobalposition)
action is a datatype. All datatypes are derived from the [`Datatype`](/sdk/python/steeleagle_sdk/api/base#class-datatype) base class.

### Actions

Actions represent actions or tasks which can be executed by the vehicle. For example, to order a
vehicle to take off, use the [`TakeOff`](/sdk/python/steeleagle_sdk/api/actions/primitives/control#class-takeoff) action.
The fields of the action class represent its parameters. For the `TakeOff` example, it has one parameter, `take_off_altitude`
which denotes the altitude the vehicle will ascend to. To modify this parameter, construct the object and set
the field to the desired value: 

```python
take_off = TakeOff(take_off_altitude = 10.0)
```

Some actions have optional fields, like
[`SetGlobalPosition`](/sdk/python/steeleagle_sdk/api/actions/primitives/control#class-setglobalposition) which has 
the optional fields `frame` and `max_velocity`. These parameters can be safely excluded: 

```python
go_to_global_pos = SetGlobalPosition(location = Location(latitude = 48.0, longitude = -79.0, altitude = 5.0))
```

All actions are derived from the [`Action`](/sdk/python/steeleagle_sdk/api/base#class-action) base class. Every action
inherits the `execute()` method. This method is responsible for asynchronously converting the object's parameters into the
associated gRPC request and sending it to the correct service. Once the call is finished, it returns a [`Response`](/sdk/python/steeleagle_sdk/api/datatypes/common#class-response).
This contains the `status` field which indicates the success or failure of the call (more about the different response statuses can be found [here](/sdk/python/steeleagle_sdk/api/datatypes/common#class-responsestatus)). The common rule is that if `status` is `COMPLETED` (which is value 2), the call succeeded.

Putting it all together, to order the vehicle to take off to an altitude of 10 meters:
```python
take_off = TakeOff(take_off_altitude = 10.0)
response = await take_off.execute()
assert(response.status == 2)
```

Actions can be composed into more complicated tasks. For example, a task called `Patrol` may, under the hood, use
several `SetGlobalPosition` actions. In this way, simple primitives can be layered into complex, reusable logic.
For more information, read [here](custom).

### Events

Events represent events which may occur during a mission, triggering state transitions. Events are typically
tied to vehicle telemetry (e.g. [`BatteryReached`](/sdk/python/steeleagle_sdk/api/events/singulars#class-batteryreached)) or
datasink output (e.g. [`DetectionFound`](/sdk/python/steeleagle_sdk/api/events/singulars#class-detectionfound). This gives
missions the ability to react in real-time to what the vehicle is seeing.

All events are derived from the [`Event`](/sdk/python/steeleagle_sdk/api/base#class-event) base class. Every event
inherits the `check()` method. This method is called on a time interval by the mission. On each call, it will
check whether the event condition is met, returning `True` or `False`. If an event returns `True`, it will trigger
associated state transitions as defined in the DSL file.

Events, like actions, can be composed into more complicated checks. For more information, read [here](custom).

## File Structure

SteelEagle DSL files are made up of four fields, called _stanzas_.

### Data Stanza

Inside the Data Stanza, users can define datatypes to be referenced later by Event or Action constructors. These must be:
- Valid Python datatypes.
- Datatypes defined within the [SteelEagle API](../../python/steeleagle_sdk/api/datatypes).
- [Custom datatypes](custom#datatypes) derived from the [datatype base class](../../python/steeleagle_sdk/api/base#class-datatype) registered at compile time.

For example, the code below defines two [`Velocity`](/sdk/python/steeleagle_sdk/api/datatypes/common#class-velocity) datatypes which can be used later by actions or events:

```dsl
Data: # Definitions of datatypes
    Velocity velocity_1(x_vel = 1.0, y_vel = 2.0)
    Velocity velocity_2(x_vel = 2.0, y_vel = 2.0, z_vel = 3.0, angular_vel = 1.0)
```

Inline definitions are also supported. For fictional types _Foo_ and _Bar_:

```dsl
Data: # Definitions of datatypes
    Bar bar(foo = Foo())
```

The Data Stanza can contain special [`Waypoints`](/sdk/python/steeleagle_sdk/api/datatypes/waypoint#class-waypoint) objects. These types refer to a set of global coordinates (latitude, longitude) which represent a shape or line. This set of coordinates is contained in a KML file which is referenced by the waypoint object. More details on waypoint configuration can be found [in the next section](kml). 

```dsl
Data: # Definitions of datatypes
    # Refers to the shape called "'Rectangle'" in the associated KML file
    Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
```

### Actions Stanza

The Actions Stanza contains all of the named actions (or states) that the vehicle can transit into during this mission. These must be:
- Actions defined in the SteelEagle API [primitives](../../python/steeleagle_sdk/api/actions/primitives).
- Actions defined in the SteelEagle API [composites](../../python/steeleagle_sdk/api/actions/procedures).
- [Custom actions](custom#actions) derived from the [action base class](../../python/steeleagle_sdk/api/base#class-action) registered at compile time.

```dsl
Actions: # Definitions of states
    TakeOff take_off(take_off_altitude = 10.0)
    Track track(class_name = 'person')
    # Composite action (moves to each point in a set of waypoints)
    Patrol patrol(waypoints = patrol_path) # Uses earlier defined patrol_path
    ReturnToHome return_to_home()
```

### Events Stanza

The Events Stanza contains all of the events for the mission. There must be:
- Events defined in the SteelEagle API [singular events](/sdk/python/steeleagle_sdk/api/events/singulars).
- Events defined in the SteelEagle API [composite events](/sdk/python/steeleagle_sdk/api/events/compositions).

```dsl
Events: # Definitions of trigger events
    DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
    BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    # Composite event (triggered when any of the parameter events is triggered)
    AnyOf any_of(events = [person_seen, battery_low]
```

### Mission Stanza

The Mission Stanza contains all of the transition functions for the mission. This defines how the vehicle changes state based on events. Referenced actions must be defined in the Actions Stanza and referenced events must be defined in the Events Stanza.

```dsl
Mission: # Definitions of transitions
    Start take_off
    During take_off:
        done -> patrol
    During patrol:
        done -> patrol
        person_seen -> track
        battery_low -> return_to_home
    During track:
        done -> patrol
        battery_low -> return_to_home
```

There are two subsections within the Mission Stanza:

#### Start

The `Start` keyword denotes the following action as the first action that will be executed.

```dsl
Start ACTION_NAME
# Example
Start take_off
```

#### During

The `During` keyword defines a single transition function. The `done` keyword is a special reserved event that is triggered once an Action's
`execute()` function returns. The during statements for a given action _A_ are said to be "bound to _A_".

```dsl
During ACTION_NAME:
    done or TRIGGER_NAME -> ACTION_NAME
    ...
    # Example with done
    done -> patrol
    # Example with earlier event definition
    person_seen -> track
```

## Semantics

The semantics of SteelEagle DSL are similar to those of equivalent FSM markup languages. On mission start, the runtime will call the `execute()`
function of the `Start` action defined in the Mission Stanza. 

When an action _A_ is running, if a `During` statement exists that is bound to _A_, a
listener is started to check for listed transition conditions. For example, if `DetectionFound</span>(class_name = 'person')` is part of a transition bound to _A_, the listener will call its check method repeatedly on a fixed time interval. If an event triggers, 
it will immediately cancel the running action and transit to the target action.
This repeats until the mission is stopped _or_ a `done` transition is not defined for an action that terminates.

### Example Mission Flow

This section will work through an example mission flow using the earlier provided mission.

#### Start

On start, the mission enters the `take_off` state. This calls `execute()` for the `take_off`
action, and the vehicle starts to fly.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        // highlight-next-line
        TakeOff take_off(take_off_altitude = 10.0)
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events:
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission:
        // highlight-next-line
        Start: take_off
        During take_off:
            done -> patrol
        During patrol:
            done -> patrol
            person_seen -> track
            battery_low -> return_to_home
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class TakeOff current
    ```
  </TabItem>
</Tabs>

#### First Transition

Once the vehicle reaches its target altitude, the `execute()` method for `take_off` returns. This
triggers the `done` transition into the `patrol` action. The `execute()` method for `patrol` is called
and the vehicle starts moving to each of the waypoints in sequence.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        // highlight-next-line
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events:
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission:
        Start: take_off
        // highlight-start
        During take_off:
            done -> patrol
        // highlight-end
        During patrol:
            done -> patrol
            person_seen -> track
            battery_low -> return_to_home
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class Patrol current
    ```
  </TabItem>
</Tabs>

#### New Listeners Started

As the transition to `patrol` happens, two listeners are started, one for `battery_low` and one for `person_seen`.
These are checked at a fixed interval as the vehicle moves.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        // highlight-next-line
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events:
        // highlight-start
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
        // highlight-end
    Mission:
        Start: take_off
        During take_off:
            done -> patrol
        // highlight-start
        During patrol:
            done -> patrol
            person_seen -> track
            battery_low -> return_to_home
        // highlight-end
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class Patrol current
    ```
  </TabItem>
</Tabs>

#### Person Detection

A person has been seen by the vehicle and detected by a datasink! This detection is forwarded to the mission which transitions into the `track` action.
Since the `person_seen` event is only active for the `patrol` action, it is no longer polled. However, `battery_low` is active for `track`
and thus persists.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        Patrol patrol(waypoints = patrol_path)
        // highlight-next-line
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events:
        // highlight-next-line
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission:
        Start: take_off
        During take_off:
            done -> patrol
        During patrol:
            done -> patrol
            // highlight-next-line
            person_seen -> track
            battery_low -> return_to_home
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class Track current
    ```
  </TabItem>
</Tabs>

#### Tracking Lost

Due to some occlusion, the vehicle has lost track of the person it was tracking and the `execute()` method returns.
This triggers a `done` transition back into `patrol`. The event listener for `person_seen` starts again.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        // highlight-next-line
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        ReturnToHome return_to_home()
    Events:
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission:
        Start: take_off
        During take_off:
            done -> patrol
        During patrol:
            done -> patrol
            person_seen -> track
            battery_low -> return_to_home
        During track:
            // highlight-next-line
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class Patrol current
    ```
  </TabItem>
</Tabs>

#### Low Battery

All this flying has drained the vehicle's battery below 50%. This triggers the `battery_low` event which transitions into the `return_to_home`
action. The vehicle goes back to its home position and hovers before it is manually landed safely. Since no `done` transition is specified
from the `return_to_home` action, the mission ends.

<Tabs groupId="flightscripts">
  <TabItem value="dsl" label="SteelEagle DSL">
    ```dsl
    Data: # Definitions of datatypes
        Waypoints patrol_path(alt = 15.0, area = 'Rectangle', algo = 'edge')
    Actions: # Definitions of states
        TakeOff take_off(take_off_altitude = 10.0)
        Patrol patrol(waypoints = patrol_path)
        Track track(class_name = 'person')
        // highlight-next-line
        ReturnToHome return_to_home()
    Events:
        DetectionFound person_seen(compute_type = 'object-engine', class_name = 'person')
        // highlight-next-line
        BatteryReached battery_low(threshold = 50, relation = 'at_most', consecutive = 5)
    Mission:
        Start: take_off
        During take_off:
            done -> patrol
        During patrol:
            done -> patrol
            person_seen -> track
            // highlight-next-line
            battery_low -> return_to_home
        During track:
            done -> patrol
            battery_low -> return_to_home
    ```
  </TabItem>
  <TabItem value="fsm" label="Finite State Machine">
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        classDef current fill:#db4462,color:white,font-weight:bold
        TakeOff --> Patrol: done
        Patrol --> Patrol: done
        Patrol --> Track: DetectionFound(person)
        Track --> Patrol: done
        Track --> ReturnToHome: BatteryReached(50)
        Patrol --> ReturnToHome: BatteryReached(50)
        
        class ReturnToHome current
    ```
  </TabItem>
</Tabs>
