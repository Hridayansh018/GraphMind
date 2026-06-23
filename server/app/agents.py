import base64
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from .tools import get_weather, web_search
import os
from dotenv import load_dotenv
from .tools import web_search

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

llm = ChatOpenAI(
    model="openai/gpt-oss-120b:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)


travel_agent = create_agent(llm, [get_weather])

def make_math_agent(mcp_tools):
    return create_agent(llm, mcp_tools)

def make_resume_agent(mcp_tools):
    return create_agent(llm, mcp_tools)

# def vision_ans(image_b64:str, q:str)->str:
#     msg = HumanMessage(content=[
#         {"type": "text", "text": q},
#         {"type": "image_url",
#          "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
#     ])
#     return vision_llm.invoke([msg]).content

web_agent = create_agent(llm, [web_search])