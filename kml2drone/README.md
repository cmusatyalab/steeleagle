# kml2drone

```sh
usage: kml2drone [-h] [-p {anafi,dji}] [-o OUTPUT] [-v] [-t TEMPLATE]
                 [-da DASHBOARD_ADDRESS] [-dp DASHBOARD_PORT]
                 input

Convert kml/kmz file to drone-specific instructions.

positional arguments:
  input                 kml/kmz file to convert

optional arguments:
  -h, --help            show this help message and exit
  -p {anafi,dji}, --platform {anafi,dji}
                        Drone platform to convert to [default: Anafi (Olympe)]
  -o OUTPUT, --output OUTPUT
                        Filename for generated drone instructions [default:
                        flightplan.py]
  -v, --verbose         Write output to console as well [default: False]
  -t TEMPLATE, --template TEMPLATE
                        Specify a jinja2 template [default: anafi.py.jinja2]
  -da DASHBOARD_ADDRESS, --dashboard_address DASHBOARD_ADDRESS
                        Specify address of dashboard to send heartbeat to
                        [default:
                        transponder.pgh.cloudapp.azurelel.cs.cmu.edu]
  -dp DASHBOARD_PORT, --dashboard_port DASHBOARD_PORT
                        Specify dashboard port [default: 8080]

```
