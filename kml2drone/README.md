# kml2drone

```sh
usage: kml2drone [-h] [-p {anafi,dji}] [-o OUTPUT] [-v] input

Convert kml/kmz file to drone-specific instructions.

positional arguments:
  input                 kml/kmz file to convert

optional arguments:
  -h, --help            show this help message and exit
  -p {anafi,dji}, --platform {anafi,dji}
                        Drone platform to convert to [default: Anafi (Olympe)]
  -o OUTPUT, --output OUTPUT
                        Filename for generated drone instructions [default:
                        drone.txt]
  -v, --verbose         Write output to console as well [default: False]
usage: kml2drone [-h] [-p {anafi,dji}] [-o OUTPUT] [-v] input
```
