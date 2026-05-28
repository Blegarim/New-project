import sys
from research_agent.agent.core import run_agent

def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Research question: ").strip()

    if not question:
        print("Please provide a research question.")
        sys.exit(1)

    print(f"\nResearching: {question}\n{'─' * 60}")
    result = run_agent(question)

    if "error" in result:
        print(f"\nFailed: {result['error']}")
        sys.exit(1)
    else:
        print(f"\nCompleted in {result['iterations']} iterations.")
        print(f"Report: {result['report_path']}")

if __name__ == "__main__":
    main()
