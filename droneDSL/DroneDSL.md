# DroneDSL Documentation

## Definition

DroneDSL is a domain-specific language used to describe the drone mission lifecycle. It helps users express the drone's self-adaptive behavior by abstracting from the underlying imlpementation details and creating executable code for various drone platforms.

Every DroneDSL file is considered a flight mission. The mission lifecycle is modeled by a task-based automata (finite state machine) to describe the drones' adaptation behavior. The task, considered as a state in this state machine, is configured based on the task type and their corresponding attributes. The transition from one task to another is triggered by the another notion called _event_.


​		

## Computational Mode - Task-based Automata

Every mission includes the following components: start state, terminate state, task states, and transition functions.

In each mission, the drone agent:

1. begins at the start state,
2. transitions through various task states via transition functions, and
3. eventually terminates at the terminate state.

Start State: This is where all missions start. It is a blank state that does not do anything but transitions.

Task State: This state defines an individual task commanded to the drone agent. When reached, it will execute all the specified task attributes.

Terminate State: This is where all missions end. The drone agent will return to home in this state.

Transition Function: They are used to move the drone agent from one state to another. There are three types of transition functions in the model:

- Start Transition: This transition function moves the drone agent from the start state to a task state unconditionally.
- Task Transition: This transition function moves the drone agent from one task state to another, given a specified trigger event has occurred. (A trigger event is a predefined event used to activate the task transition function.)
- End Transition: This transition function moves the drone agent from a task state to the terminate state when the drone agent has executed all commands in its current state and has not triggered any task transitions. (Note, the end transition, unlike the other transitions, is implicitly defined. It is assumed that if the drone agent executes all the commands specified in its current task without triggering any events, then it satisfies the mission requirements and thereby is meant to end the mission.)

Example of a mission described by the task-based automata:

![img](https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=5360&x=-571&y=-2692&w=3763&h=1573&store=1&accept=image%2F*&auth=LCA%20635535078509a726ba38f2f055df2710bb8db84e0dff298925b24efa18fcb50e-ts%3D1706801140)

In this example, the drone agent starts from the start state and transitions to the `Task1` state to perform a detection task over a triangular area, with its task attributes specified. If a person is detected during this task, the drone agent transitions to the `Task2` state for a tracking task. If the duration of `Task2` exceeds 70 seconds, then the drone agent will transition back to the `Task1` state for another detection task. If the drone agent reaches all the waypoints specified in the triangular area without detecting any person, it will then transition to the terminate state and return home.



## Language Component (Pilot Aspect)

### Section

A mission script comprises two sections:

+ Task section: used to define all the task states.
+ Mission section: used to define all the transition functions.

Sections are created using section keywords followed by `{}`. The section keywords are `Task` and `Mission`, corresponding to the task and mission sections, respectively.

Example:

```
Task {
	// define task states
}

Mission {
	// define transition functions
}
```



### Task section

**Task state**

The task state is used to define a task along with its attributes for the drone agent to execute within this state.

The task state includes the task type and task attributes. It is created using the following format:

```
task_type task_id {
    task_attribute_type: task_attribute_value,
    task_attribute_type: task_attribute_value,
    ...
}
```

- **Task type** is a keyword specifying the type of task for the drone agent to execute. The keywords are as follows:

  ```
  Detect, Track, Avoidance
  ```

- **Task ID** is the name of the task state, which only allows numbers and letters.

- **Task attribute type** is a keyword specifying the type of the task attribute, with keywords as follows:

  ```
  waypoint, gimbal_pitch, drone_rotation, sample_rate, hover_delay, model, class, speed, altitude
  ```

- **Task attribute** specifies the value of the given task attribute type. Examples include:

  - **waypoint**: Can be specified in KML or as a list of coordinates (longitude, latitude, altitude). For example, `<Triangle>` or `[(-79.9503492, 40.4155806, 25.0), (-79.9491717, 40.4155826, 25.0)]`.
  - **drone rotation**, **gimbal_pitch**: Specified as a double.
  - **sample rate**, **hover delay**: Specified as an integer.
  - **model**: Specified as a string.

**Task types and required attributes:**

- **Detect task**: Instructs the drone to detect objects along a specified path using the specified pitch, rotation, sampling rate, and detection model.
  - **Keyword**: `Detect`
  - **Required task attributes**:
    - `waypoints`
    - `gimbal_pitch`
    - `drone_rotation`
    - `sample_rate`
    - `hover_delay`
    - `model`
- **Track task**: Tracks a specified class using a particular model for inference.
  - **Keyword**: `Track`
  - **Required task attributes**:
    - `gimbal_pitch`
    - `model`
    - `class`
- **Avoidance task**: Flies from coordinate A to coordinate B while avoiding obstacles.
  - **Keyword**: `Avoidance`
  - **Required task attributes**:
    - `waypoints`
    - `model`
    - `speed`
    - `altitude`

Examples of task states include:

```
Detect task1 {
    way_points: <Triangle>,
    gimbal_pitch: -45.0,
    drone_rotation: 0.0,
    sample_rate: 2,
    hover_delay: 0,
    model: coco
}
```

Example of a task section:

```
Task {
    Detect task1 {
        way_points: <Triangle>,
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco
    }

    Detect task1 {
        way_points: [(-79.9503492, 40.4155806, 25.0),(-79.9491717, 40.4155826, 25.0)],
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 5,
        model: none
    }
}
```



### Mission section

**Start Transition**

The start transition function specifies which task the drone agent should start with. It is created using the keyword `Start` followed by the name of the task, according to the following rule:

```
Start task_id
```

Here is an example of a start transition function:

```
Start task1
```

**Task Transition**

The task transition function specifies that, given the current task state and a trigger event, which task state the drone agent should transition to. This function is created using the keyword `Transition`, the trigger event, the current task state, and the next task state, according to the following rule:

```
Transition (trigger_event) current_task_id -> next_task_id
```

**Trigger Event**

A trigger event specifies under what circumstances the task transition will be triggered. The trigger event is defined by the name of the event and its argument, following this rule:

```
trigger_event_name(trigger_event_argument)
```

Here is an example of a task transition function:

```
Transition (timeout(40)) task1 -> task2
```

The trigger event is supported in the following forms:

1. Timeout: This event triggers after a specified duration of time has passed. It takes an integer as an argument.

   ```
   timeout( integer ) 
   ```

2. Object Detection: This event triggers when a specified class of object is detected. It requires the name of the class as an argument.

   ```
   object_detection  ( name of the class )
   ```

3. End Task: This event triggers when the task has reached its conclusion. It does not require an argument.

   ```
   end_task()
   ```

**Mission Section Example**

```
Mission {
    Start  task1 
    Transition ( timeout( 70 ) ) task2 -> task1
    Transition ( object_detection( person ) ) task1 -> task2
}
```



### A Mission Script Example

```
Task {
    Detect task1 {
        way_points: <Triangle>,
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco
    }

    Detect task2 {
        way_points: <Rectangle>,
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco
    }
}


Mission {
    Start  task1 
    Transition ( timeout( 70 ) ) task2 -> task1
    Transition ( object_detection( person ) ) task1 -> task2
}

```

In this example, the drone agent starts from the start state and transitions to the Task 1 state to perform a detection task over a triangular area, with its task attributes specified. If a person is detected during this task, the drone agent transitions to the Task 2 state for another detect task. If the duration of Task 2 exceeds 70 seconds, then the drone agent will transition back to the Task 1 state. If the drone agent reaches all the waypoints specified in the triangular area without detecting any person, it will then transition to the terminate state and return home.
