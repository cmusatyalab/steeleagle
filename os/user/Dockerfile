FROM alpine:3.16
RUN apk add --no-cache python3=3.10.14-r1 py3-pip

# Set python3 as the default python
RUN ln -sf python3 /usr/bin/python

# Install any required build dependencies
RUN apk add --no-cache gcc musl-dev linux-headers bash

# Set the dir in the container
WORKDIR /steeleagle_os/steeleagle_user

COPY ./os/user /steeleagle_os/steeleagle_user
COPY ./os/cnc_protocol /steeleagle_os/cnc_protocol
COPY ./os/env.sh /steeleagle_os/env.sh
COPY ./os/util /steeleagle_os/util

# Install any required Python packages
RUN pip install --no-cache-dir -r /steeleagle_os/steeleagle_user/requirements.txt

# source the env.sh file
ENTRYPOINT ["/bin/bash", "-c", "source /steeleagle_os/env.sh && exec \"$@\""]