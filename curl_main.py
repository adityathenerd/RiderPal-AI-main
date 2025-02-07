import requests
import subprocess
import time
import asyncio
import uvicorn
from multiprocessing import Process
from main import app, make_call

def start_server():
    """Start the FastAPI server using uvicorn"""
    uvicorn.run(app, host="0.0.0.0", port=6060)

async def initiate_call(phone_number: str):
    """Make the call using the existing make_call function"""
    try:
        await make_call(phone_number)
        print(f"Call initiated to {phone_number}")
    except Exception as e:
        print(f"Error making call: {e}")

def main():
    # Start the server in a separate process
    server_process = Process(target=start_server)
    server_process.start()
    
    # Wait for the server to start up
    print("Waiting for server to start...")
    time.sleep(5)  # Give the server some time to initialize
    
    # Phone number to call
    phone_number = "+918117015660"  # Replace with your target phone number
    
    # Create an event loop and run the call
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(initiate_call(phone_number))
        
        # Keep the script running
        print("Server is running. Press Ctrl+C to stop.")
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Clean up
        server_process.terminate()
        server_process.join()
        loop.close()

if __name__ == "__main__":
    main()