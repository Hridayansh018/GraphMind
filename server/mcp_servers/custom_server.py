from fastmcp import FastMCP

mcp = FastMCP("MathServer")

@mcp.tool
def add(a:float, b:float)->float:
    """Add two numbers"""
    return a+b

@mcp.tool
def subtract(a:float, b:float)->float:
    """Subtract two numbers"""
    return a-b

@mcp.tool
def multily(a:float, b:float)->float:
    """Multiply two numbers"""
    return a*b

@mcp.tool
def divide(a:float, b:float)->float:
    """Divide two numbers"""
    return a/b


#we will be adding more features in future

if __name__ == "__main__":
    mcp.run()