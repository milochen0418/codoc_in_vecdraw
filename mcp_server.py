import asyncio
import httpx
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("VecDraw Control")

# Configuration
REFLEX_API_URL = "http://localhost:8000/mcp/push_ops"

async def send_ops(ops: list, room_id: str = "default"):
    """Helper to send operations to the Reflex app."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                REFLEX_API_URL,
                json={"room_id": room_id, "ops": ops},
                timeout=5.0
            )
            response.raise_for_status()
            return f"Successfully sent {len(ops)} operations to room '{room_id}'."
        except Exception as e:
            return f"Error sending operations: {str(e)}. Is the Reflex app running?"

@mcp.tool()
async def draw_rectangle(x: int, y: int, width: int, height: int, fill: str = "black", room_id: str = "default") -> str:
    """Draw a rectangle on the canvas."""
    op = {
        "op": "addRect",
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "fill": fill
    }
    return await send_ops([op], room_id)

@mcp.tool()
async def draw_circle(cx: int, cy: int, radius: int, fill: str = "black", room_id: str = "default") -> str:
    """Draw a circle (ellipse) on the canvas."""
    op = {
        "op": "addEllipse",
        "cx": cx,
        "cy": cy,
        "rx": radius,
        "ry": radius,
        "fill": fill
    }
    return await send_ops([op], room_id)

@mcp.tool()
async def draw_text(x: int, y: int, content: str, font_size: int = 20, room_id: str = "default") -> str:
    """Add text to the canvas."""
    op = {
        "op": "addText",
        "x": x,
        "y": y,
        "content": content,
        "font_size": font_size
    }
    return await send_ops([op], room_id)

@mcp.tool()
async def draw_line(x1: int, y1: int, x2: int, y2: int, stroke: str = "black", room_id: str = "default") -> str:
    """Draw a line between two points."""
    op = {
        "op": "addLine",
        "x": x1,
        "y": y1,
        "end_x": x2,
        "end_y": y2,
        "stroke": stroke
    }
    return await send_ops([op], room_id)

@mcp.tool()
async def clear_canvas(room_id: str = "default") -> str:
    """Clear all shapes from the canvas."""
    op = {"op": "clear"}
    return await send_ops([op], room_id)

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
