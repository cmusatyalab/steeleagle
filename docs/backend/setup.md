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
Follow the [instructions](../gcs/setup.md) on installing the Streamlit GCS.

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
