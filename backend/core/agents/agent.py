"""
Parent class for all agents
"""

class Agent:
    def __init__(self):
        self.SYSTEM_PROMPT = """
"""
        

    def activate(self, context: str) -> str:
        """
        Activates the supplied agent with the context it needs
        Args:
            agent (Agent): the selected agent
            context (str): context the agent needs to execute its job
        Returns:
            str: The information from the agent to be to the LLM again for fromatting to TTS
        """

        # Return None means we encountered an error
        return None