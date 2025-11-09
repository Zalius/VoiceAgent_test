"""
Restaurant Voice Order Assistant
==================================
A LiveKit Voice Agent that acts as a restaurant phone order operator.
It takes orders, confirms availability, calculates totals, and asks for delivery address.
Requires OpenAI and Deepgram API keys.
"""

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import Agent, AgentSession, RunContext
from livekit.agents.llm import function_tool
from livekit.plugins import openai, deepgram, silero
from datetime import datetime
import os

# Load environment variables
load_dotenv(".env")

class RestaurantOrderAssistant(Agent):
    """Friendly restaurant phone operator that handles food orders."""

    def __init__(self):
        super().__init__(
            instructions="""You are a polite and cheerful restaurant phone operator.
            Your role is to take food orders, confirm item availability, suggest options,
            ask for the delivery address, and thank the customer.
            Speak naturally, like a friendly restaurant staff member over the phone."""
        )

        # Define the menu
        self.menu = {
            "burgers": {
                "classic burger": {"price": 8.99, "options": ["cheese", "add bacon", "extra lettuce"]},
                "veggie burger": {"price": 7.99, "options": ["extra tomato", "avocado", "spicy sauce"]},
                "chicken burger": {"price": 9.49, "options": ["extra mayo", "add egg", "add cheese"]},
            },
            "pizza": {
                "margherita": {"price": 12.99, "options": ["extra cheese", "thin crust", "add mushrooms"]},
                "pepperoni": {"price": 13.49, "options": ["extra pepperoni", "stuffed crust", "add olives"]},
                "bbq chicken": {"price": 14.29, "options": ["extra sauce", "jalapenos", "add onions"]},
            },
            "fries": {
                "regular fries": {"price": 3.99, "options": ["ketchup", "mayo", "cheese dip"]},
                "curly fries": {"price": 4.49, "options": ["bbq sauce", "ranch dip"]},
            },
            "drinks": {
                "cola": {"price": 2.49, "options": ["ice", "no ice"]},
                "orange juice": {"price": 3.49, "options": ["no pulp", "extra cold"]},
                "water": {"price": 1.49, "options": ["room temperature", "chilled"]},
            },
            "desserts": {
                "chocolate cake": {"price": 5.49, "options": ["extra fudge", "whipped cream"]},
                "ice cream": {"price": 4.99, "options": ["chocolate syrup", "sprinkles"]},
            },
        }

        # Initialize session state
        self.orders = []
        self.delivery_address = None
        self.customer_name = None

    # --------------------------------------------------------
    # Tools (callable functions for LLM interaction)
    # --------------------------------------------------------

    @function_tool
    async def view_menu(self, context: RunContext) -> str:
        """Show the available food categories and some popular items."""
        response = "Here’s our menu:\n\n"
        for category, items in self.menu.items():
            response += f"🍽 {category.title()}:\n"
            for name, info in items.items():
                response += f"  • {name.title()} - ${info['price']:.2f}\n"
            response += "\n"
        response += "All prices include tax. You can ask for item details or order anything listed!"
        return response

    @function_tool
    async def add_item_to_order(self, context: RunContext, category: str, item_name: str, quantity: int = 1, options: list[str] | None = None) -> str:
        """Add a menu item to the current order."""
        cat_lower = category.lower()
        item_lower = item_name.lower()

        if cat_lower not in self.menu or item_lower not in self.menu[cat_lower]:
            return f"Sorry, we don’t have '{item_name}' under {category}. Would you like to hear available options instead?"

        item = self.menu[cat_lower][item_lower]
        total_item_price = item["price"] * quantity
        chosen_options = options if options else []

        self.orders.append({
            "category": cat_lower,
            "item": item_lower,
            "quantity": quantity,
            "options": chosen_options,
            "total": total_item_price,
        })

        options_text = f" with {' and '.join(chosen_options)}" if chosen_options else ""
        return f"Added {quantity} × {item_name.title()}{options_text} to your order. Subtotal: ${total_item_price:.2f}"

    @function_tool
    async def remove_item(self, context: RunContext, item_name: str) -> str:
        """Remove an item from the order."""
        before_count = len(self.orders)
        self.orders = [o for o in self.orders if o["item"] != item_name.lower()]
        after_count = len(self.orders)

        if before_count == after_count:
            return f"I couldn’t find '{item_name}' in your current order."
        else:
            return f"Removed '{item_name.title()}' from your order."

    @function_tool
    async def view_current_order(self, context: RunContext) -> str:
        """Display the current order summary."""
        if not self.orders:
            return "Your order is currently empty."

        summary = "Here’s what you have ordered so far:\n\n"
        total = 0.0
        for o in self.orders:
            summary += f"• {o['quantity']} × {o['item'].title()} (${o['total']:.2f})"
            if o["options"]:
                summary += f" with {', '.join(o['options'])}"
            summary += "\n"
            total += o["total"]

        summary += f"\nTotal so far: ${total:.2f}"
        return summary

    @function_tool
    async def set_delivery_address(self, context: RunContext, address: str) -> str:
        """Save the customer’s delivery address."""
        self.delivery_address = address
        return f"Got it! The order will be delivered to: {address}"

    @function_tool
    async def confirm_order(self, context: RunContext, customer_name: str) -> str:
        """Finalize the order and generate a simple receipt."""
        if not self.orders:
            return "You don’t have any items yet. Please add something first."

        if not self.delivery_address:
            return "I’ll need your delivery address before confirming. Could you please tell me where to deliver?"

        self.customer_name = customer_name
        total_amount = sum(o["total"] for o in self.orders)
        confirmation_number = f"ORD{1000 + len(self.orders)}"

        result = f"✅ Order confirmed for {customer_name}!\n\n"
        result += f"Confirmation Number: {confirmation_number}\n"
        result += f"Delivery Address: {self.delivery_address}\n\n"
        result += "Items Ordered:\n"
        for o in self.orders:
            result += f"  - {o['quantity']} × {o['item'].title()} (${o['total']:.2f})\n"
        result += f"\nGrand Total: ${total_amount:.2f}\n\n"
        result += "Your food will arrive soon! Thank you for ordering with us ❤️"

        # Reset order for the next customer
        self.orders = []
        self.delivery_address = None
        self.customer_name = None

        return result

    @function_tool
    async def get_current_time(self, context: RunContext) -> str:
        """Return current local time for convenience."""
        now = datetime.now().strftime("%I:%M %p on %B %d, %Y")
        return f"The current local time is {now}."

# --------------------------------------------------------
# Agent entrypoint
# --------------------------------------------------------

async def entrypoint(ctx: agents.JobContext):
    """Entry point for the Restaurant Operator."""

    session = AgentSession(
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model=os.getenv("LLM_CHOICE", "gpt-4.1-mini")),
        tts=openai.TTS(voice="echo"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=RestaurantOrderAssistant())

    await session.generate_reply(
        instructions="Greet the caller warmly as a restaurant operator, offer to show the menu or take their order."
    )

if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
