from __future__ import annotations
import json
from typing import Any, AsyncGenerator
from datetime import date
import google.generativeai as genai
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

FLIGHT_TOOL = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="search_flights",
            description="Tìm chuyến bay. Trả về giá, hãng, giờ bay.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "departure_id": genai.protos.Schema(type=genai.protos.Type.STRING),
                    "arrival_id":   genai.protos.Schema(type=genai.protos.Type.STRING),
                    "outbound_date":genai.protos.Schema(type=genai.protos.Type.STRING),
                    "return_date":  genai.protos.Schema(type=genai.protos.Type.STRING),
                    "adults":       genai.protos.Schema(type=genai.protos.Type.INTEGER),
                },
                required=["arrival_id"],
            ),
        )
    ]
)

SHOPPING_TOOL = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="search_shopping",
            description="Tìm sản phẩm, so sánh giá.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(type=genai.protos.Type.STRING),
                },
                required=["query"],
            ),
        )
    ]
)

TOOL_FUNCTIONS = {
    "search_flights":  search_flights,
    "search_shopping": search_shopping,
}
MAX_TOOL_ITERATIONS = 5


class Agent:
    def __init__(self):
        genai.configure(api_key=Config.gemini_api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=SYSTEM_PROMPT,
            tools=[FLIGHT_TOOL, SHOPPING_TOOL],
        )
        self.history = []

    def _with_date(self, user_message: str) -> str:
        today = date.today().strftime("%A, %d/%m/%Y")
        return f"[Hôm nay: {today}]\n{user_message}"

    def chat(self, user_message: str) -> str:
        chat = self.model.start_chat(history=self.history)
        injected = self._with_date(user_message)

        for _ in range(MAX_TOOL_ITERATIONS):
            response = chat.send_message(injected if _ == 0 else "")
            part = response.candidates[0].content.parts[0]

            if hasattr(part, "function_call") and part.function_call.name:
                fn_name = part.function_call.name