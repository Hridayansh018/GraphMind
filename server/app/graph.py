from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from .agents import make_resume_agent
# from langchain.agents import create_agent
from .agents import make_math_agent, web_agent



class BotState(MessagesState): 
    route: str  
    
    
async def build_bot():
    client = MultiServerMCPClient({
        "math": {"transport": "stdio", "command": "python",
                 "args": ["mcp_servers/custom_server.py"]},
        "resume": {"transport": "stdio", "command": "python",
                   "args": ["mcp_servers/resume_mcp.py"]},
    })
    
    math_tools = await client.get_tools()
    tools = await client.get_tools()
    math_agent = make_math_agent(math_tools)
    resume_tools = [t for t in tools if t.name in {"review_resume","ats_score"}]
    resume_agent = make_resume_agent(resume_tools)

    
    def math_node(state:MessagesState)->str:
        return math_agent.invoke(state)
    def web_node(state:MessagesState):
        return web_agent.invoke(state)
    def resume_node(state: BotState):
        return resume_agent.invoke(state)
    
    def supervisor(state:MessagesState)->str:
        text = state["messages"][-1].content.lower()
        if state.get("route") == "resume":     
            return "resume"
        if any(w in text for w in ["add", "plus", "times", "multiply", "calculate","divide","minus","subtract"]): 
            return "math"
        return "web"
    
    saver = InMemorySaver()
    g = StateGraph(MessagesState)
    g.add_node("math",math_node)
    g.add_node("web",web_node)
    g.add_node("resume", resume_node)           
    g.add_conditional_edges(START, supervisor, ["math","web","resume"])
    g.add_edge("web",END)
    g.add_edge("math",END)
    g.add_edge("web",END)
    return g.compile(checkpointer=saver)

# async def build_resume_agent():
#     client = MultiServerMCPClient({
#         "resume": {"transport": "stdio", "command": "python",
#                    "args": ["mcp_servers/resume_mcp.py"]},
#     })
#     resume_tools = await client.get_tools()
#     return make_resume_agent(resume_tools)