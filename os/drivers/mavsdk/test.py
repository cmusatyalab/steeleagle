from mavsdk import System

async def get_home():
    drone = System()
    await drone.connect(system_address="udp://:14550")

    print("Connecting to drone...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Drone connected!")
            break

    print("Fetching home position...")
    async for home_position in drone.telemetry.home():
        print(f"Home position: Latitude: {home_position.latitude_deg}, "
              f"Longitude: {home_position.longitude_deg}, "
              f"Absolute Altitude: {home_position.absolute_altitude_m} meters")
        break

if __name__ == "__main__":
    import asyncio
    asyncio.run(get_home())

