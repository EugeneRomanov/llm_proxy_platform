import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/v1/chat/completions")
async def mock_chat():
    async def generate():
        tokens = ["Hello", " this", " is", " a", " mocked", " response", " from", " LLM."]
        for token in tokens:
            chunk = {"choices": [{"delta": {"content": token}}]}
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(0.2) # Имитация задержки
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")