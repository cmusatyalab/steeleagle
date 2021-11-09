FROM ubuntu:20.04
LABEL Satyalab, satya-group@lists.andrew.cmu.edu

ENV DEBIAN_FRONTEND=noninteractive

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clinfo \
    curl \
    debconf-utils \
    git \
    libgl1-mesa-glx \
    lsb-release \
    python3 \
    python3-opencv \
    python3-pip \
    sudo \
    vim \
    wget \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#add Parrot repo
#RUN bash -c 'echo "deb http://plf.parrot.com/sphinx/binary `lsb_release -cs`/" | sudo tee /etc/apt/sources.list.d/sphinx.list > /dev/null'
#RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 508B1AE5

# Install build and runtime dependencies
#RUN echo parrot-sphinx	sphinx/firmwared_users	string	ubuntu | debconf-set-selections && \
#    echo parrot-sphinx	sphinx/license_approval	boolean	true | debconf-set-selections && \
#    apt-get update && apt-get install -y parrot-sphinx \
#    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip3 install --upgrade pip
RUN python3 -m pip install jupyter ipython jinja2 zmq opencv-python

RUN ln -s /usr/bin/python3 /usr/bin/python
#install Olympe
RUN useradd -ms /bin/bash ubuntu
RUN echo "ubuntu ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
USER ubuntu
RUN  python3 -m pip install --user parrot-olympe

WORKDIR /home/ubuntu
COPY --chown=ubuntu:ubuntu . steel-eagle
WORKDIR steel-eagle

EXPOSE 8888 9002 8080
ENTRYPOINT ["./entrypoint.sh"]
