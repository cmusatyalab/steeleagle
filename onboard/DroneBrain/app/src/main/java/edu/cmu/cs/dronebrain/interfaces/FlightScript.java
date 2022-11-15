package edu.cmu.cs.dronebrain.interfaces;

import java.util.Queue;

public abstract class FlightScript implements Runnable {
    protected DroneItf drone;
    protected CloudletItf cloudlet;
    // Members which help with execution of tasks.
    protected Thread taskThread;
    protected Task currentTask;
    protected Queue<Task> taskQueue;

    // Init function to set drone and cloudlet.
    public void init(DroneItf d, CloudletItf c) {
        drone = d;
        cloudlet = c;
    }

    // Run method is derived from Runnable. Defined for each task.

    // Executes all tasks on the command queue.
    protected void execLoop() throws InterruptedException {
        while (!taskQueue.isEmpty()) {
            exec(taskQueue.remove());
        }
    }

    // Executes a task.
    protected void exec(Task task) throws InterruptedException {
        taskThread = new Thread(task);
        taskThread.start();
        taskThread.join();
    }

    // Kills this mission. Halts the drone and flushes the task queue.
    public void kill() throws Exception {
        drone.kill();
    }

    // Pauses the mission. Halts the drone but preserves the task queue.
    public abstract void pause();

    // Pushes a new task to the head of the queue.
    public void push_task(Task newTask) {
        taskQueue.add(newTask);
    }

    // Forces the drone to switch to the new task.
    public void force_task(Task newTask) {
        currentTask.pause();
        push_task(newTask);
        taskThread.interrupt(); // Interrupt the task thread to continue the exec loop.
    }
}
