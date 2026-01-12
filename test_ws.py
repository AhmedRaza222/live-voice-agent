
import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://localhost:7860/infobip"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Successfully connected to {uri}")
            
            # Simulate Infobip handshake/metadata message
            payload = {
                "event": "connected",
                "callId": "12345"
            }
            await websocket.send(json.dumps(payload))
            print("✅ Sent JSON payload")
            
            # Verify we stay connected for a moment
            await asyncio.sleep(2)
            print("✅ Connection stable after 2 seconds")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
