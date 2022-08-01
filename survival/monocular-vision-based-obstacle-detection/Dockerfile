FROM python:3.7

COPY . /
#RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt --no-cache-dir

# don't run as root
RUN groupadd -g 1000 appuser && useradd -r -u 1000 -g appuser appuser
USER appuser

WORKDIR /
ENTRYPOINT ["python3", "/Main.py"]

# docker run -v <absolute_path_to_data>:/data -v <absolute_path_to_out_folder>:/out <image name>