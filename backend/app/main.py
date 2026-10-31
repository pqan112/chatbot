from typing import Literal, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from .assistant import build_messages, retrieve
from .config import settings

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


async def token_stream(messages: list[Message]):
    history = [m.model_dump() for m in messages]
    query = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    chunks = await retrieve(client, query) if query else []
    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=cast(
            list[ChatCompletionMessageParam], build_messages(history, chunks)
        ),
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        token_stream(req.messages), media_type="text/plain; charset=utf-8"
    )
