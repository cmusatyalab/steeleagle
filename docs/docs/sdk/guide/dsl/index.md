---
sidebar_position: 1
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Writing DSL Files

The SteelEagle DSL (Domain-Specific Language) is a custom language specification designed to simplify code for mobile robots.
It achieves this by using a finite state machine execution model, with composable actions and transition events.
By default, SteelEagle is configured to run compiled SteelEagle DSL files, though [this can be changed](mission/).

## Structure

As mentioned, SteelEagle DSL files are a text representation of a [finite state machine](https://www.mathworks.com/discovery/state-machine.html).
A finite state machine (FSM) is a computing model that contains three types, states, trigger events, and transition functions. States can represent anything, but in 
SteelEagle, they represent the current task that the vehicle is executing. Trigger events are events that happen during execution, e.g. the current task is done or
a person was detected. Transition functions are functions which determine which state the FSM should move to given a trigger event. 

In this way, the FSM can compactly model complex logic. Take for instance the following mission: patrol a provided area; if you see a person,
track and follow them; if you lose the person, go back to patrolling. Here is a representation of the accompanying FSM and an example SteelEagle DSL implementation:

<Tabs>
  <TabItem value="fsm" label="Finite State Machine" default>
    ```mermaid
    ---
    config:
      layout: elk
      look: handDrawn
      theme: default
    ---
    stateDiagram-v2
        direction LR
        Start --> Patrol
        Patrol --> Patrol: OnFinished
        Patrol --> Track: OnDetect(person)
        Track --> Patrol: OnFinished
    ```
  </TabItem>
  <TabItem value="dsl" label="SteelEagle DSL">
    <pre>
    <code>
    Hello world!
    </code>
    </pre>
  </TabItem>
</Tabs>
