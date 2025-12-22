try:
    from .agent import Agent
except ImportError:
    from agent import Agent

def choose_agent(llm_response:str) -> Agent:
    """
    Based on LLM response, chooses the appropriate agent for the job
    Args:
        llm_response (str): LLM' response (example: <LOGIN>, <REAL>, etc)
    Returns:
        Agent: The right agent class for the job
    """
    # TODO: Here we create the agents that do the things
    match llm_response:
        case "<LOGIN>": 
            return Agent()
        
        case "<SHIFT>":
            return Agent()
        
        # User asks for a task that is not allowed / unknown
        case "<DENY>":
            return Agent()
        


    return None

