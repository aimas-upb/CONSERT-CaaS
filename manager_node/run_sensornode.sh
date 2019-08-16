#!/bin/bash

#trap 'pkill -9 -f corese-server-4.1.1-jar-with-dependencies; pkill -9 -f managernode.py; pkill -9 -f sensornode.py; pkill -9 -f rosbridge_websocket' EXIT

# ros=`pgrep roslaunch`
# if [ -z "$ros"]
# then
# 	source /opt/ros/kinetic/setup.bash
# 	roslaunch rosbridge_server rosbridge_websocket.launch &
# 	sleep 3
# fi


python sensornode.py