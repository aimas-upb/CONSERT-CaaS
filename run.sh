#!/bin/bash

trap 'kill $(jobs -p)' EXIT
trap 'pkill -9 -f corese-server-4.1.1-jar-with-dependencies; pkill -9 -f managernode.py; pkill -9 -f sensornode.py; pkill -9 -f rosbridge_websocket' EXIT

ros=`pgrep roslaunch`
if [ -z "$ros"]
then
	source /opt/ros/kinetic/setup.bash
	roslaunch rosbridge_server rosbridge_websocket.launch &
	sleep 3
fi

source /home/costin/.local/share/virtualenvs/manager_node-hzDHuAHv/bin/activate
cd /home/costin/Desktop/AI-MAS/CONSERT-CaaS/manager_node
python3 managernode.py &
sleep 3
python3 sensornode.py &
sleep 8
echo [LAB308 ENVIRONMENT]  $(date +"%T") ALL SET

wait