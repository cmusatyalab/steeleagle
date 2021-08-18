#FROM nvidia/cuda:10.0-cudnn7-devel-ubuntu18.04
FROM ubuntu:18.04
LABEL Satyalab, satya-group@lists.andrew.cmu.edu

ENV DEBIAN_FRONTEND=noninteractive

# Install build and runtime dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clinfo \
    curl \
    debconf-utils \
    git \
    lsb-release \
    python3 \
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
RUN python3 -m pip install jupyter ipython jinja2

#install repo tool
RUN curl https://storage.googleapis.com/git-repo-downloads/repo > /bin/repo
RUN chmod a+x /bin/repo

#symlink python3 -> python
RUN ln -s /usr/bin/python3 /usr/bin/python
#install Olympe
RUN useradd -ms /bin/bash ubuntu
RUN echo "ubuntu ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
USER ubuntu
RUN mkdir -p /home/ubuntu/parrot-groundsdk
WORKDIR /home/ubuntu/parrot-groundsdk
RUN ["/bin/bash", "-c", "/bin/repo init -u https://github.com/Parrot-Developers/groundsdk-manifest.git"]
RUN bash -c '/bin/repo sync'
#set /etc/localtime so tzdata doesn't prompt for timezone info
RUN sudo ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime
RUN DEBIAN_FRONTEND=noninteractive sudo ./products/olympe/linux/env/postinst
RUN mkdir -p /home/ubuntu/.config/dragon_build
#EULA-<hash> is an md5 hash of /home/ubuntu/parrot-groundsdk/.repo/manifests/EULA.md
#and it needs to be present in order to avoid license prompts
#maybe replace with a call to md5sum so this doesn't break when EULA.md changes?
RUN touch /home/ubuntu/.config/dragon_build/EULA-9f6684a0241a5a845bfc8395aaec0886
RUN ./build.sh -p olympe-linux -A all final -j

WORKDIR /home/ubuntu
RUN sudo chown -R ubuntu:ubuntu /home/ubuntu/.local
COPY --chown=ubuntu:ubuntu . steel-eagle
WORKDIR steel-eagle

EXPOSE 8888 9002 8080
ENTRYPOINT ["./entrypoint.sh"]
