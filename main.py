import os
import json
import base64
import asyncio
import argparse
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.rest import Client
import websockets.client
from dotenv import load_dotenv
import uvicorn
import re

load_dotenv()

# Configuration
TWILIO_ACCOUNT_SID = 'ACd1eff7ab490404a25f11cd151c53e87a'
TWILIO_AUTH_TOKEN = 'd13a17ef7084d7f630aab41be97634bd'
PHONE_NUMBER_FROM = '+18482929065'
OPENAI_API_KEY = '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'
raw_domain = 'https://a290-210-212-2-165.ngrok-free.app'
DOMAIN = re.sub(r'(^\w+:|^)\/\/|\/+$', '', raw_domain) # Strip protocols and trailing slashes from DOMAIN

PORT = int("6060")



# Demo data structures for order, location and FAQs
ORDER_DETAILS = {
    "order_id": "ORD123456",
    "customer_name": "John Smith",
    "delivery_address": "123 Main St, Anytown, ST 12345",
    "items": [
        {"name": "Chicken Burger", "quantity": 2, "special_instructions": "No mayo"},
        {"name": "French Fries", "quantity": 1, "special_instructions": "Extra crispy"}
    ],
    "order_status": "In Transit",
    "estimated_delivery": "2:30 PM"
}

RIDER_DETAILS = {
    "name": "Navjyot",
    "current_location": "456 Oak Avenue, Anytown, ST 12345",
    "current_coordinates": {"lat": "40.7128", "lng": "-74.0060"},
    "vehicle": "Honda Activa",
    "rating": "4.8"
}

ROUTE_DETAILS = {
    "pickup_point": "Restaurant XYZ, 789 Pine St, Anytown, ST 12345",
    "pickup_coordinates": {"lat": "40.7120", "lng": "-74.0050"},
    "delivery_point": ORDER_DETAILS["delivery_address"],
    "delivery_coordinates": {"lat": "40.7140", "lng": "-74.0070"},
    "estimated_distance": "2.5 km",
    "estimated_time": "15 minutes",
    "waypoints": [
        "Take right from Pine St",
        "Continue on Oak Avenue",
        "Left turn onto Main St",
        "Destination will be on your right"
    ]
}

FAQS = {"delivery_time": {
                "question": "What are the typical delivery times?",
                "answer": "Typical delivery times are 30-60 minutes depending on distance and traffic. We strive to provide the most accurate estimated delivery time for each order."
            },
            "tracking": {
                "question": "How can I track my order?",
                "answer": "You can track your order in real-time through our mobile app or website. Simply enter your order number to get live updates on your delivery status."
            },
            "contact_support": {
                "question": "How do I contact customer support?",
                "answer": "Our customer support can be reached at 1-800-DELIVERY. We're available 24/7 to assist you with any questions or concerns."
            },
            "cancellation_policy": {
                "question": "What is the cancellation policy?",
                "answer": "Orders can be cancelled within 10 minutes of placement with no fee. After 10 minutes, cancellation may be subject to a small processing fee."
            },
            "delivery_policy": {
                "question": "What is your delivery policy?",
                "answer": "Our delivery policy ensures timely and safe delivery of your items. We prioritize careful handling, punctual delivery, and customer satisfaction."
            },
            "special_instructions": {
                "question": "Can I add special delivery instructions?",
                "answer": "Yes, you can add special instructions during the order placement. These could include specific delivery preferences like 'leave at door', 'ring doorbell', or any other specific requirements."
            },
            "payment_methods": {
                "question": "What payment methods do you accept?",
                "answer": "We accept major credit cards, digital wallets, and cash on delivery. Payment options may vary depending on your location."
            },
            "temperature_handling": {
                "question": "How do you ensure food temperature during delivery?",
                "answer": "We use insulated delivery bags and prioritize quick transportation to maintain optimal food temperature. Hot items are kept hot, and cold items are kept cold."
            },
            "lost_item_policy": {
                "question": "What happens if an item is lost or damaged?",
                "answer": "If an item is lost or damaged during delivery, contact our customer support immediately. We will investigate and provide a replacement or refund."
}}

# Enhanced system message using f-strings
SYSTEM_MESSAGE = f'''You are RiderPal, an AI delivery assistant helping rider {RIDER_DETAILS['name']} with order tracking, 
location details, and customer support for deliveries. Here are the current details:

ORDER INFORMATION:
- Order ID: {ORDER_DETAILS['order_id']}
- Customer: {ORDER_DETAILS['customer_name']}
- Delivery Address: {ORDER_DETAILS['delivery_address']}
- Items:
  {', '.join([f"{item['quantity']}x {item['name']} ({item['special_instructions']})" for item in ORDER_DETAILS['items']])}
- Status: {ORDER_DETAILS['order_status']}
- Estimated Delivery: {ORDER_DETAILS['estimated_delivery']}

RIDER DETAILS:
- Name: {RIDER_DETAILS['name']}
- Current Location: {RIDER_DETAILS['current_location']}
- Vehicle: {RIDER_DETAILS['vehicle']}
- Rating: {RIDER_DETAILS['rating']}

ROUTE INFORMATION:
- Pickup Point: {ROUTE_DETAILS['pickup_point']}
- Delivery Point: {ROUTE_DETAILS['delivery_point']}
- Estimated Distance: {ROUTE_DETAILS['estimated_distance']}
- Estimated Time: {ROUTE_DETAILS['estimated_time']}
- Current Route:
  {' → '.join(ROUTE_DETAILS['waypoints'])}

You can answer common questions about:
{chr(10).join([f"- {question}: {answer}" for question, answer in zip(FAQS.keys(), FAQS.values()) if not question.startswith('answer')])}

Please provide accurate and helpful information based on these details. If asked about real-time updates, 
remind the customer that these details are current as of the last update. For any questions about 
modifying orders or specific issues, direct customers to customer support while remaining helpful 
and empathetic.'''






VOICE = 'alloy'
LOG_EVENT_TYPES = [
    'error', 'response.content.done', 'rate_limits.updated', 'response.done',
    'input_audio_buffer.committed', 'input_audio_buffer.speech_stopped',
    'input_audio_buffer.speech_started', 'session.created'
]

app = FastAPI()

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and PHONE_NUMBER_FROM and OPENAI_API_KEY):
    raise ValueError('Missing Twilio and/or OpenAI environment variables. Please set them in the .env file.')

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


async def send_initial_conversation_item(openai_ws):
    """Send initial conversation so AI talks first."""
    initial_conversation_item = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "Greet the user with 'Hello there! I am an RiderPal, I am assisting Navjyot today.  "
                        "How can I help you?'"
                    
                    )
                }
            ]
        }
    }
    await openai_ws.send(json.dumps(initial_conversation_item))
    await openai_ws.send(json.dumps({"type": "response.create"}))

async def initialize_session(openai_ws):
    """Control initial session with OpenAI."""
    session_update = {
        "type": "session.update",
        "session": {
            "turn_detection": {"type": "server_vad"},
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "voice": VOICE,
            "instructions": SYSTEM_MESSAGE,
            "modalities": ["text", "audio"],
            "temperature": 0.8,
        }
    }
    print('Sending session update:', json.dumps(session_update))
    await openai_ws.send(json.dumps(session_update))

    # Have the AI speak first
    await send_initial_conversation_item(openai_ws)


async def check_number_allowed(to):
    """Check if a number is allowed to be called."""
    try:
        # Uncomment these lines to test numbers. Only add numbers you have permission to call
        # OVERRIDE_NUMBERS = ['+18005551212'] 
        # if to in OVERRIDE_NUMBERS:             
          # return True

        incoming_numbers = client.incoming_phone_numbers.list(phone_number=to)
        if incoming_numbers:
            return True

        outgoing_caller_ids = client.outgoing_caller_ids.list(phone_number=to)
        if outgoing_caller_ids:
            return True

        return False
    except Exception as e:
        print(f"Error checking phone number: {e}")
        return False
    

async def make_call(phone_number_to_call: str):
    """Make an outbound call."""
    if not phone_number_to_call:
        raise ValueError("Please provide a phone number to call.")

    is_allowed = await check_number_allowed(phone_number_to_call)
    if not is_allowed:
        raise ValueError(f"The number {phone_number_to_call} is not recognized as a valid outgoing number or caller ID.")

    # Ensure compliance with applicable laws and regulations
    # All of the rules of TCPA apply even if a call is made by AI.
    # Do your own diligence for compliance.

    outbound_twiml = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect><Stream url="wss://{DOMAIN}/media-stream" /></Connect></Response>'
    )

    call = client.calls.create(
        from_=PHONE_NUMBER_FROM,
        to=phone_number_to_call,
        twiml=outbound_twiml
    )

    await log_call_sid(call.sid)

async def log_call_sid(call_sid):
    """Log the call SID."""
    print(f"Call started with SID: {call_sid}")



@app.get('/', response_class=JSONResponse)
async def index_page():
    return {"message": "Twilio Media Stream Server is running!"}

@app.websocket('/media-stream')
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and OpenAI."""
    print("Client connected")
    await websocket.accept()

    async with websockets.client.connect(
    'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
    extra_headers={
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "OpenAI-Beta": "realtime=v1"
    }
    ) as openai_ws:

        await initialize_session(openai_ws)
        stream_sid = None

        async def receive_from_twilio():
            """Receive audio data from Twilio and send it to the OpenAI Realtime API."""
            nonlocal stream_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data['event'] == 'media' and openai_ws.open:
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                    elif data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        print(f"Incoming stream has started {stream_sid}")
            except WebSocketDisconnect:
                print("Client disconnected.")
                if openai_ws.open:
                    await openai_ws.close()

        async def send_to_twilio():
            """Receive events from the OpenAI Realtime API, send audio back to Twilio."""
            nonlocal stream_sid
            try:
                async for openai_message in openai_ws:
                    response = json.loads(openai_message)
                    if response['type'] in LOG_EVENT_TYPES:
                        print(f"Received event: {response['type']}", response)
                    if response['type'] == 'session.updated':
                        print("Session updated successfully:", response)
                    if response['type'] == 'response.audio.delta' and response.get('delta'):
                        try:
                            audio_payload = base64.b64encode(base64.b64decode(response['delta'])).decode('utf-8')
                            audio_delta = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
                                }
                            }
                            await websocket.send_json(audio_delta)
                        except Exception as e:
                            print(f"Error processing audio data: {e}")
            except Exception as e:
                print(f"Error in send_to_twilio: {e}")
        await asyncio.gather(receive_from_twilio(), send_to_twilio())



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Twilio AI voice assistant server.")
    parser.add_argument('--call', required=True, help="The phone number to call, e.g., '--call=+18005551212'")
    args = parser.parse_args()

    phone_number = args.call
    # print(
    #     'Our recommendation is to always disclose the use of AI for outbound or inbound calls.\n'
    #     'Reminder: All of the rules of TCPA apply even if a call is made by AI.\n'
    #     'Check with your counsel for legal and compliance advice.'
    # )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(make_call(phone_number))
    
    uvicorn.run(app, host="0.0.0.0", port=PORT)