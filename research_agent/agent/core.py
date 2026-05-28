from research_agent.agent.memory import Memory
from research_agent.agent.planner import build_system_prompt
from research_agent.config.settings import settings
from research_agent.models.factory import get_provider
from research_agent.tools.registry import TOOL_SCHEMAS, dispatch


def run_agent(question: str) -> dict:
    memory = Memory()
    system = build_system_prompt(question)
    provider = get_provider()
    memory.add_user(f"Please research the following question: {question}")

    for iteration in range(settings.max_loop_iterations):
        print(f"\n[Loop {iteration + 1}/{settings.max_loop_iterations}]")

        response = provider.call(
            messages=memory.get(),
            tools=TOOL_SCHEMAS,
            system=system,
        )

        memory.add_assistant([b.to_dict() for b in response.content])

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            print(f"[Agent] Unexpected end_turn: {text[:200]}")
            break

        if response.stop_reason == "tool_use":
            tool_calls = [b for b in response.content if b.type == "tool_use"]

            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_input = tool_call.input or {}
                tool_id = tool_call.id

                print(f"[Tool] {tool_name}({tool_input})")

                if tool_name == "final_answer":
                    print(f"\n[Done] {tool_input['summary']}")
                    print(f"[Report] {tool_input['report_path']}")
                    memory.add_tool_result(tool_id, "Research complete.")
                    return {
                        "summary": tool_input["summary"],
                        "report_path": tool_input["report_path"],
                        "iterations": iteration + 1,
                    }

                try:
                    result = dispatch(tool_name, tool_input)
                except Exception as e:
                    result = f"Error running {tool_name}: {e}"

                print(f"[Result] {str(result)[:150]}...")
                memory.add_tool_result(tool_id, result)

    return {"error": "Max iterations reached without a final answer."}
