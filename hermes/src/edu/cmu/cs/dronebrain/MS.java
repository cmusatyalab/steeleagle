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
import edu.cmu.cs.dronebrain.interfaces.CloudletItf;
import edu.cmu.cs.dronebrain.interfaces.DroneItf;
import edu.cmu.cs.dronebrain.interfaces.FlightScript;
import edu.cmu.cs.dronebrain.interfaces.Task;

import edu.cmu.cs.dronebrain.T1;
import edu.cmu.cs.dronebrain.T2;


public class MS extends FlightScript {
    
    @Override
    public void run() {
	taskQueue.add(new T1(drone, cloudlet));
	taskQueue.add(new T2(drone, cloudlet));	
	try {
	    customExecLoop();
	} catch (Exception e) {
        
	}
    }
    
    @Override
    public void pause() {}

    private void customExecLoop() throws Exception {
	exec(taskQueue.remove());
	Thread.sleep(5000);
	currentTask.pause();
	taskThread.interrupt();
	taskThread.join();
	exec(taskQueue.remove());
    }

    private void customExec(Task newTask) throws Exception {
	taskThread = new Thread(newTask);
        taskThread.start();
    }
}
