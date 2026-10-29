"""
toy_agent.py  -  a minimal AI agent you can watch think.

PURPOSE: before you secure agents, you should operate one. This is the smallest
thing that is honestly an "agent": it is given a GOAL, and it decides its own
steps by picking TOOLS in a LOOP until the goal is met. You never script the
steps - it chooses them from the current state.

    goal  ->  [ think: what should I do next? ]
                 |
                 v
              [ act: call a tool ]
                 |
                 v
              [ observe: see the result, update state ]
                 |
                 +--> loop back until the goal is satisfied, then STOP

HONEST NOTE ON "THE BRAIN":
In a real agent, an LLM reads the goal + state and decides the next tool. Here
we fake that brain with a few plain rules (the `decide` function), with NO API
key and NO dependencies, so you can run it and watch the part that actually
matters: the LOOP. The loop is identical whether the brain is an LLM or rules -
and the loop is what makes it an agent. Swap `decide` for an LLM call later and
nothing else changes.

This agent's domain is the Lisbon trip from the payment-guard work, on purpose:
its `pay` tool is exactly where, in Slice 2, we will slot the Guard between the
agent and the money - and then try to hijack it.
"""

# ---- the WORLD the agent can act on (all fake, in memory) ------------------
FLIGHTS = [{"payee": "TAP Air Portugal", "price": 420}]
HOTELS  = [{"payee": "Lisbon Marriott", "price": 180}]   # per night

state = {
    "goal": "Book a return flight and 2 nights hotel in Lisbon, then confirm.",
    "flight_found": False,
    "hotel_found": False,
    "flight_booked": False,
    "hotel_booked": False,
    "confirmed": False,
    "spent": 0.0,
    "log": [],          # what the agent has done - its audit trail
}


# ---- the TOOLBOX: the only things the agent is able to DO ------------------
def tool_search_flights(_):
    return f"found flight: {FLIGHTS[0]['payee']} GBP {FLIGHTS[0]['price']}"

def tool_search_hotels(_):
    return f"found hotel: {HOTELS[0]['payee']} GBP {HOTELS[0]['price']}/night"

def tool_pay(args):
    # In Slice 2, a Guard will sit in FRONT of this function and may block it.
    state["spent"] += args["amount"]
    state["log"].append(f"PAID {args['payee']} GBP {args['amount']}")
    return f"paid {args['payee']} GBP {args['amount']} (total GBP {state['spent']})"

def tool_confirm(_):
    state["confirmed"] = True
    return "trip confirmed, itinerary sent to traveller"

TOOLBOX = {
    "search_flights": tool_search_flights,
    "search_hotels":  tool_search_hotels,
    "pay":            tool_pay,
    "confirm":        tool_confirm,
}


# ---- the "BRAIN": decide the next action from the current state ------------
# (A real agent asks an LLM here. We use rules so it runs with no dependencies.)
def decide(state):
    """Return (tool_name, args, reasoning) for the next step, or (None, ...) when done."""
    if not state["flight_booked"]:
        if not state["flight_found"]:
            return "search_flights", {}, "I need a flight first; let me look."
        f = FLIGHTS[0]
        return "pay", {"payee": f["payee"], "amount": f["price"], "category": "airline"}, \
               "I found a flight; pay for it."
    if not state["hotel_booked"]:
        if not state["hotel_found"]:
            return "search_hotels", {}, "Flight done; now I need a hotel."
        h = HOTELS[0]
        return "pay", {"payee": h["payee"], "amount": h["price"] * 2, "category": "hotel"}, \
               "I found a hotel; pay for 2 nights."
    if not state["confirmed"]:
        return "confirm", {}, "Everything booked; confirm the trip."
    return None, {}, "Goal met - nothing left to do."


# ---- the LOOP: think -> act -> observe -> repeat ---------------------------
def run(max_steps=10):
    print("GOAL:", state["goal"], "\n" + "-" * 70)
    for step in range(1, max_steps + 1):
        tool_name, args, reasoning = decide(state)

        if tool_name is None:                       # the agent decides it is done
            print(f"\nStep {step}: THINK  -> {reasoning}")
            print("Agent stops.")
            break

        print(f"\nStep {step}: THINK  -> {reasoning}")
        print(f"         ACT    -> {tool_name}({args if args else ''})")
        result = TOOLBOX[tool_name](args)           # the agent takes the action
        print(f"         OBSERVE-> {result}")

        # update state based on what happened (the agent learns from the result)
        if tool_name == "search_flights":
            state["flight_found"] = True
        elif tool_name == "search_hotels":
            state["hotel_found"] = True
        elif tool_name == "pay" and args.get("category") == "airline":
            state["flight_booked"] = True
        elif tool_name == "pay" and args.get("category") == "hotel":
            state["hotel_booked"] = True

    print("\n" + "=" * 70)
    print("DONE. Audit trail of actions the agent took:")
    for entry in state["log"]:
        print("  -", entry)
    print(f"Total spent: GBP {state['spent']}.  Confirmed: {state['confirmed']}")
    print("=" * 70)
    print("\nThat loop - think, act with a tool, observe, repeat until done - IS")
    print("the agent. Next (Slice 2): put the Guard in front of tool_pay(), feed")
    print("the agent a POISONED web page, and watch it get talked into paying an")
    print("attacker - then watch the Guard stop it.")


if __name__ == "__main__":
    run()
