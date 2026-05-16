from __future__ import annotations
from typing import Any, AsyncGenerator
from datetime import date
import json
from openai import OpenAI
from .config import Config
from .tools.serpapi import search_flights, search_shopping

SYSTEM_PROMPT = """Bạn là Tara Bot — agent thông minh chuyên tìm vé máy bay và săn giá đồ.

NGUYÊN TẮC:
- Trả lời bằng tiếng Việt tự nhiên, thân thiện.
- Khi user hỏi vé máy bay, gọi tool search_flights.
- Khi user hỏi giá sản phẩm, gọi tool search_shopping.
- Sau khi tool trả kết quả, chuyển tiếp NGUYÊN VĂN kết quả đó cho user, chỉ thêm 1-2 câu ngắn.
- KHÔNG reformat lại kết quả từ tool.
- Có thể nói chuyện thông thường — không cần gọi tool.

Mặc định cho câu hỏi mơ hồ về thời gian:
- "cuối tuần" → thứ Sáu tuần gần nhất (không quá khứ)
- "tuần sau" → tuần tiếp theo"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "Tìm chuyến bay. Trả về giá, hãng, giờ bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "departure_id":  {"type": "string", "description": "Mã sân bay đi (IATA). Mặc định SGN"},
                    "arrival_id":    {"type": "string", "description": "Mã sân bay đến (IATA)"},
                    "outbound_date": {"type": "string", "description": "Ngày đi (YYYY-MM-DD)"},
                    "return_date":   {"type": "string", "description": "Ngày về (YYYY-MM-DD)"},
                    "adults":        {"type": "integer", "description": "Số người lớn. Mặc định 1"},
                },
                "required": ["arrival_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_shopping",
            "description": "Tìm sản phẩm, so sánh giá.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Tên sản phẩm cần tìm"},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "search_flights":  search_flights,
    "search_shopping": search_shopping,
}
MAX_TOOL_ITERATIONS = 5


class Agent:
    def __init__(self):
        self.client = OpenAI(
            api_key=Config.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = "llama-3.3-70b-versatile"
        self.history = []

    def _with_date(self, user_message: str) -> str:
        today = date.today().strftime("%A, %d/%m/%Y")
        return f"[Hôm nay: {today}]\n{user_message}"

    def chat(self, user_message: str) -> str:
        injected = self._with_date(user_message)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self.history
        messages.append({"role": "user", "content": injected})

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = response.choices[0].message
            messages.append(msg)

            if msg.tool_calls:
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    fn = TOOL_FUNCTIONS.get(fn_name)
                    result = fn(**fn_args) if fn else f"Unknown tool: {fn_name}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    })
                continue

            reply = msg.content or ""
            self.history.append({"role": "user", "content": injected})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        return "Xin lỗi, em không thể xử lý yêu cầu này!"

    async def stream_chat(self, user_message: str) -> AsyncGenerator[str, None]:
        reply = self.chat(user_message)
        yield reply