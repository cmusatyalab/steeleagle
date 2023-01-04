// SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
//
// SPDX-License-Identifier: GPL-2.0-only

package edu.cmu.cs.dronebrain.interfaces;

public abstract class Task implements Runnable {
    protected DroneItf drone;
    protected CloudletItf cloudlet;

    // Include references to task members
    public Task(DroneItf d, CloudletItf c) {
        drone = d;
        cloudlet = c;
    }

    // TODO: Run is already an abstract method derived from Runnable.
    //  It will be implemented separately by each task.

    // Pauses the task. Allows resuming in certain cases.
    public abstract void pause();

    // Resumes the task if it is resumeable, otherwise returns immediately.
    public abstract void resume();
}
