.TH "AGIBOT TEST RUNBOOK" "1" "2026-11-19" "AgiBot A3 Ultra" "Operator Guide"
.SH NAME
AgiBot A3 Ultra - Test Script Runbook
.PP
This runbook records the scripts created in this repository, the tests that
worked, the network addresses discovered during testing, and the safe next
steps for gesture, audio, and ROS 2 walking control.

.SH "1. Safety first"
.IP \(em 2
Keep people and obstacles outside the robot's movement range before any
physical motion test.
.IP \(em 2
Use the accessible emergency stop and verify the robot is stable.
.IP \(em 2
Motion scripts are dry runs unless an explicit execute flag is supplied.
.IP \(em 2
Stop testing if status services are unavailable or the robot's current state
cannot be confirmed.

.SH "2. Network addresses and ports"
.PP
Two robot network paths were identified.
.TS
center box;
l l l.
Path	Purpose	Observed result

192.168.2.196	External LAN robot address	Previously served ports 59301, 56322, and 56666; later became unreachable.
10.42.10.10	Internal MDU resource address	Resource-list RPC on port 51049 worked.
10.42.10.12	Internal HDU address	Motion service on port 56444 worked.
10.42.10.11	Internal map address	Documented map service on port 50807.
.TE
.PP
The PC has eth3 configured with 10.42.10.100/24. Verify its route:
.nf
ip -brief addr show eth3
ip route get 10.42.10.12
.fi

.SH "3. Read-only status tests"
.PP
Run these before any gesture after the external LAN robot address is restored:
.nf
\&./robot_rpc_status.sh mode
\&./robot_rpc_status.sh action
\&./robot_rpc_status.sh joints
\&./robot_rpc_status.sh voice
\&./robot_rpc_status.sh compliance
.fi
.PP
Important observed state: interaction mode was successfully set to only_voice.
The robot later stopped responding at 192.168.2.196. If this address remains
unreachable, do not rely on these status results.

.SH "4. Interaction-mode control"
.PP
Inspect current mode:
.nf
python3 interactive_mode.py
.fi
.PP
Set only_voice, then reboot the robot:
.nf
\&./set_interactive_mode.sh only_voice 192.168.2.196
.fi
.PP
Restore normal interaction, then reboot the robot:
.nf
\&./set_interactive_mode.sh normal 192.168.2.196
.fi
.PP
The script requires typing APPLY. only_voice provides noise-reduced microphone
output for custom software but changes the built-in interaction chain.

.bp
.SH "5. Motion-resource discovery"
.PP
List the actual motion resources installed on this robot. This is read-only and
avoids using a motion path that is not present on the current firmware:
.nf
\&./list_motion_resources.sh
.fi
.PP
The installed resources included handshake, wave, right-hand thumbs-up,
finger-heart, double thumbs-up, bow, fist-and-palm greeting, fist bumps, and
look-at-watch gestures.

.SH "6. Gesture tests"
.PP
List named gestures:
.nf
ROBOT=10.42.10.12 \&./robot_gestures.sh list
.fi
.PP
Preview a gesture; this does not move the robot:
.nf
ROBOT=10.42.10.12 \&./robot_gestures.sh wave
.fi
.PP
Execute a gesture only after the safety checks in section 1. Type PLAY only
when prompted:
.nf
ROBOT=10.42.10.12 \&./robot_gestures.sh wave --execute
ROBOT=10.42.10.12 \&./robot_gestures.sh handshake --execute
ROBOT=10.42.10.12 \&./robot_gestures.sh thumbs_up --execute
ROBOT=10.42.10.12 \&./robot_gestures.sh finger_heart --execute
ROBOT=10.42.10.12 \&./robot_gestures.sh bow --execute
.fi
.PP
The general resource player is also available:
.nf
ROBOT=10.42.10.12 \&./play_motion.sh --execute
.fi
.PP
Use robot_gestures.sh when possible. It maps short English names to verified
installed motion-resource paths.

.SH "7. Audio tests"
.PP
Read speaker status:
.nf
python3 robot_audio.py status
.fi
.PP
Set a moderate volume. The documentation recommends no more than 70:
.nf
python3 robot_audio.py set-volume 40 --apply
.fi
.PP
TTS wrapper:
.nf
python3 audio_test.py "Hello. I am ready to assist you in English."
.fi
.PP
TTS requires network access. In only_voice mode, a TTS request may be accepted
but speaker output can require the ROS 2 full-takeover audio-streaming method.

.bp
.SH "8. Health, map, and resource queries"
.PP
Current alerts (read-only):
.nf
HDU='http://10.42.10.12:50587/rpc'
curl -sS -H 'content-type: application/json' -X POST \
  "$HDU/aimdk.protocol.HDSService/GetAlertList" -d '{}'
.fi
.PP
The health endpoint timed out during later testing. This alone does not prove
the robot is off, because the HDU motion service still returned HTTP responses.
.PP
List installed audio or screen-emoticon resources by replacing RESOURCE_TYPE_MOTION:
.nf
RESOURCE_TYPE_AUDIO
RESOURCE_TYPE_EMOTICON
.fi
.PP
Map queries are documented at 10.42.10.11:50807. Do not change maps, delete
resources, trigger autonomous charging, or switch motion actions without a
specific authorized task and a clear safety plan.

.SH "9. ROS 2 walking - not ready yet"
.PP
Forward, backward, sideways, and turning movement use the ROS 2 topic:
.nf
/motion/control/locomotion_velocity
.fi
.PP
The guarded script is:
.nf
python3 robot_walk.py forward --execute
.fi
.PP
It defaults to scale 0.05 for 0.5 seconds, limits scale to 0.10 and duration
to one second, checks the MOTION state, and publishes zero-velocity stop
commands in cleanup. It has not moved the robot because its prerequisites are
currently incomplete.
.PP
Required before walking:
.IP 1. 3
Restore the external LAN robot address or find its new IP in AimMaster/router
DHCP leases.
.IP 2. 3
Obtain the robot's DDS configuration file:
.nf
/agibot/software/v0/entry/cfg/ros_dds_configuration.xml
.fi
.IP 3. 3
Obtain and install the x86_64 version of ros2_plugin_proto for this WSL PC.
.IP 4. 3
Source the ROS environment and configure discovery:
.nf
source /opt/ros/jazzy/setup.bash
export ROS_DOMAIN_ID=232
export FASTRTPS_DEFAULT_PROFILES_FILE="$HOME/ros_dds_configuration.xml"
ros2 topic list --no-daemon --spin-time 10 -t
.fi
.IP 5. 3
Verify that /motion/control/locomotion_velocity appears before running
robot_walk.py.

.SH "10. Current conclusion"
.PP
HTTP motion-resource playback through 10.42.10.12:56444 and resource discovery
through 10.42.10.10:51049 are confirmed. The external address 192.168.2.196 is
currently unreachable, and ROS 2 discovery shows only local topics because the
DDS configuration and protocol package are missing. Continue with read-only
queries or carefully supervised stored gestures; do not attempt locomotion
until the ROS 2 prerequisites are complete.
