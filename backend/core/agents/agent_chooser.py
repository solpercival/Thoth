from agent import Agent

def choose_agent(llm_response:str) -> Agent:
    """
    Based on LLM response, chooses the appropriate agent for the job
    Args:
        llm_response (str): LLM' response (example: <LOGIN>, <REAL>, etc)
    Returns:
        Agent: The right agent class for the job
    """

    match llm_response:
        case "<LOGIN>": 
            return None


    return None

