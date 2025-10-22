---
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Structure

SteelEagle DSL files are a text representation of a [finite state machine](https://www.mathworks.com/discovery/state-machine.html).
A finite state machine (FSM) is a computing model that contains three types, states, trigger events, and transition functions. States can represent anything, but in 
SteelEagle, they represent the current task that the vehicle is executing. Trigger events are events that happen during execution, e.g. the current task is done or
a person was detected. Transition functions are functions which determine which state the FSM should move to given a trigger event. 

In this way, the FSM can compactly model complex logic. Take for instance the following UAV mission: take off and patrol a provided area; if you see a person,
track and follow them; if you lose the person, go back to patrolling. Here is a representation of the accompanying FSM and an example SteelEagle DSL implementation:

<Tabs>
  <TabItem value="fsm" label="Finite State Machine" default>
    ```mermaid
    ---
    config:
      layout: elk
      theme: default
    ---
    stateDiagram-v2
        direction LR
        TakeOff --> Patrol
        Patrol --> Patrol: OnFinished
        Patrol --> Track: OnDetect(person)
        Track --> Patrol: OnFinished
    ```
  </TabItem>
  <TabItem value="dsl" label="SteelEagle DSL">
    <pre>
    <code>
	<span style={{color: '#e01be3'}}>Data</span>: <span style={{color: '#7d7d7d'}}># Definitions of datatypes</span>
	&emsp;<span style={{color: '#19ade3'}}>Waypoint</span> patrol_path(path: [<span style={{color: '#19ade3'}}>Location</span>(48.0, -78.0, 10.0), <span style={{color: '#19ade3'}}>Location</span>(48.1, -78.1, 10.0)])
	<span style={{color: '#e01be3'}}>Actions</span>: <span style={{color: '#7d7d7d'}}># Definitions of states</span>
	&emsp;<span style={{color: '#19ade3'}}>TakeOff</span> take_off(take_off_altitude: 10.0)
	&emsp;<span style={{color: '#19ade3'}}>Patrol</span> patrol(waypoints: patrol_path) <span style={{color: '#7d7d7d'}}># Uses earlier defined patrol_path</span>
	&emsp;<span style={{color: '#19ade3'}}>Track</span> track(class: 'person')
	<span style={{color: '#e01be3'}}>Mission</span>: <span style={{color: '#7d7d7d'}}># Definitions of trigger events and transitions</span>
	&emsp;<span style={{color: '#19e341'}}>Start</span> take_off
	&emsp;<span style={{color: '#19e341'}}>During</span> take_off:
	&emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
	&emsp;<span style={{color: '#19e341'}}>During</span> patrol:
	&emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
	&emsp;<span style={{color: '#19e341'}}>During</span> patrol:
	&emsp;&emsp;<span style={{color: '#19ade3'}}>DetectionReached</span>(class: 'person') -> track
	&emsp;<span style={{color: '#19e341'}}>During</span> track:
	&emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
    </code>
    </pre>
  </TabItem>
</Tabs>

## Syntax

SteelEagle DSL files are made up of three fields, called _stanzas_.

### Data Stanza

Inside the Data Stanza, users can define datatypes to be referenced later by Event or Action constructors. These must be:
- Valid Python datatypes
- Datatypes defined within the [SteelEagle API](../python/steeleagle_sdk/api/datatypes)
- [Custom datatypes](dsl/custom#datatypes) derived from the [datatype base class](../python/steeleagle_sdk/api/base#class-datatype) defined in the custom definitions folder passed in at compile time.

<pre>
<code>
    <span style={{color: '#e01be3'}}>Data</span>: <span style={{color: '#7d7d7d'}}># Definitions of datatypes</span>
    &emsp;<span style={{color: '#19ade3'}}>Waypoint</span> patrol_path(path: [<span style={{color: '#19ade3'}}>Location</span>(48.0, -78.0, 10.0), <span style={{color: '#19ade3'}}>Location</span>(48.1, -78.1, 10.0)])
</code>
</pre>

### Actions Stanza

The Actions Stanza contains all of the named actions (or states) that the vehicle can transit into during this mission. These must be:
- Actions defined in the SteelEagle API [primitives](../python/steeleagle_sdk/api/primitives)
- Actions defined in the SteelEagle API [composites](../python/steeleagle_sdk/api/composites)
- [Custom actions](dsl/custom#actions) derived from the [action base class](../python/steeleagle_sdk/api/base#class-action) defined in the custom definitions folder passed in at compile time.

<pre>
<code>
    <span style={{color: '#e01be3'}}>Actions</span>: <span style={{color: '#7d7d7d'}}># Definitions of states</span>
    &emsp;<span style={{color: '#19ade3'}}>TakeOff</span> take_off(take_off_altitude: 10.0)
    &emsp;<span style={{color: '#19ade3'}}>Patrol</span> patrol(waypoints: patrol_path) <span style={{color: '#7d7d7d'}}># Uses earlier defined patrol_path</span>
    &emsp;<span style={{color: '#19ade3'}}>Track</span> track(class: 'person')
</code>
</pre>

### Mission Stanza

The Mission Stanza contains all of the transition functions for the mission. This defines how the vehicle changes state based on events. Referenced actions must be defined in the Actions Stanza.

<pre>
<code>
    <span style={{color: '#e01be3'}}>Mission</span>: <span style={{color: '#7d7d7d'}}># Definitions of trigger events and transitions</span>
    &emsp;<span style={{color: '#19e341'}}>Start</span> take_off
    &emsp;<span style={{color: '#19e341'}}>During</span> take_off:
    &emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
    &emsp;<span style={{color: '#19e341'}}>During</span> patrol:
    &emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
    &emsp;<span style={{color: '#19e341'}}>During</span> patrol:
    &emsp;&emsp;<span style={{color: '#19ade3'}}>DetectionReached</span>(class: 'person') -> track
    &emsp;<span style={{color: '#19e341'}}>During</span> track:
    &emsp;&emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
</code>
</pre>

There are three reserved types within the Mission Stanza:

#### Start

The `Start` keyword denotes the following action as the first action that will be executed.

<pre>
<code>
    <span style={{color: '#19e341'}}>Start</span> ACTION_NAME
    <span style={{color: '#7d7d7d'}}># Example:</span>
    <span style={{color: '#19e341'}}>Start</span> take_off
</code>
</pre>

#### During

The `During` keyword defines a single transition function. The `done` keyword is a special reserved event that is triggered once an Action's
`execute()` function returns. The during statements for a given action _A_ are said to be "bound to _A_".

<pre>
<code>
    <span style={{color: '#19e341'}}>During</span> ACTION_NAME:
    &emsp;<span style={{color: '#19ade3'}}>done</span> or TRIGGER_EVENT_DEFINITION -> ACTION_NAME
    <span style={{color: '#7d7d7d'}}># Example with done:</span>
    <span style={{color: '#19e341'}}>During</span> patrol:
    &emsp;<span style={{color: '#19ade3'}}>done</span> -> patrol
    <span style={{color: '#7d7d7d'}}># Example with event definition:</span>
    <span style={{color: '#19e341'}}>During</span> patrol:
    &emsp;<span style={{color: '#19ade3'}}>DetectionReached</span>(class: 'person') -> track
</code>
</pre>

## Semantics

The semantics of SteelEagle DSL are similar to those of equivalent FSM markup languages. On mission start, the runtime will call the `execute()`
function of the `Start` action defined in the Mission Stanza. 

When an action _A_ is running, if a `During` statement exists that is bound to _A_, a
listener is started to check for listed transition conditions. For example, <code><span style={{color: '#19ade3'}}>DetectionReached</span>(class: 'person')</code> would listen for a person detection over the result socket. If an event triggers, it will immediately cancel the running action and transit to the target action. This repeats until the mission is stopped _or_ a `done` transition is not defined for an action that terminates.
