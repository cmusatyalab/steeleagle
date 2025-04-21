To begin, download the SteelEagle repository from GitHub:

```
git clone --depth 1 https://github.com/cmusatyalab/steeleagle.git
cd steeleagle
```

The backend code lives in the `backend` directory. The files pertinent for
setting up and running SteelEagle are the `docker-compose.yml` and the
`redis.conf.template` files.

```
backend
└── server
    ├── docker-compose.yml
    └── redis
        └── redis.conf.template

```
The `docker-compose.yml` file is pre-configured to launch the required
backend computation engines and expose the ports needed to allow for
communication between components.

The ground control station code lives in the `gcs/streamlit` directory.

## Database Setup

SteelEagle uses Redis for storing drone telemetry such as location, velocity,
battery level, etc. To set up Redis follow these instructions:
```
# Navigate to the Redis directory
cd backend/server/redis

# Create the redis.conf file from the template
cp redis.conf.template redis.conf
```

Open the `redis.conf` file in your favorite editor and choose and enter a
Redis password on line 874:
```
user steeleagle on allcommands allkeys allchannels >(use secure password here)
```
For example, if you chose `mypass` as the password, this line should now be:
```
user steeleagle on allcommands allkeys allchannels >mypass
```

## Ground Control Station Setup
Navigate to the Streamlit directory:
```
cd gcs/streamlit
```
Next, install the Python dependencies:
```
pip3 install -r requirements.txt
```
Next, navigate to the `.streamlit` directory:
```
cd .streamlit
```
Create the `secrets.toml` config file from the template:
```
cp secrets.toml.template secrets.toml
```
Open the `secrets.toml` file in your favorite editor and fill out the fields
according to the instructions:
```
# The Redis database IP address. This can be 0.0.0.0 if Redis is running on
# the same host
redis = "<server>"
redis_port = 6379
redis_user = "steeleagle"
# The Redis password you specified in redis.conf
redis_pw = "<generate with>"
# Specify as 0.0.0.0:8080 in most cases
webserver = "<server>:8080"
# Specify as 0.0.0.0:1984 in most cases
webrtc = "<server>:1984"
# Specify as 0.0.0.0 in most cases
zmq = "<server>"
zmq_port = 6001
# Choose and enter a password to use for streamlit
password = "<secure password>"
```

## Environment Setup
Navigate to the server directory:
```
cd backend/server
```
And create the environment file from the template:
```
cp template.env .env
```
Within the environment file, add the Redis password you set up in the
`REDIS_AUTH` variable and also add the externally accessible IP of the host
to `WEBSERVER_URL`:
```
REDIS_AUTH=<shared key from redis.conf>
WEBSERVER_URL=http://<externally accessible IP of host>
```
