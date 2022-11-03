/* Copyright 2022 Carnegie Mellon University

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License. 
*/

package edu.cmu.cs.dronebrain;

import java.lang.Thread;
import java.util.PriorityQueue;
import java.util.Comparator;
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Task;

import edu.cmu.cs.dronebrain.T1;
import edu.cmu.cs.dronebrain.T2;

public class MS extends FlightScript {

	@Override
	public void run() {
		Comparator<Task> comp = new Comparator<Task>() {
			@Override
			public int compare(Task t1, Task t2) {
				return 0;
			}
		};
		try {
			drone.connect();
			drone.takeOff();
			taskQueue = new PriorityQueue<Task>(comp);
			taskQueue.add(new T1(drone, cloudlet));
			taskQueue.add(new T2(drone, cloudlet));
			customExecLoop();
		} catch (Exception e) {

		}
	}

	@Override
	public void pause() {
	}

	private void customExecLoop() throws Exception {
		System.out.println("customExec on T1");
		customExec(taskQueue.remove());
		System.out.println("About to sleep...");
		Thread.sleep(3000);
		System.out.println("Pausing currentTask");
		currentTask.pause();
		System.out.println("interrupt/join");
		taskThread.interrupt();
		taskThread.join();
		System.out.println("customExec on T2");
		customExec(taskQueue.remove());
	}

	private void customExec(Task newTask) throws Exception {
		taskThread = new Thread(newTask);
		taskThread.start();
		currentTask = newTask;
	}
}
