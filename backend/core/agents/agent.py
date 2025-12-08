"""
Parent class for all agents
"""

class Agent:
    def activate(self, context: str) -> str:
        """
        Activates the supplied agent with the context it needs
        Args:
            agent (Agent): the selected agent
            context (str): context the agent needs to execute its job
        Returns:
            str: The information from the agent to be to the LLM again for fromatting to TTS
        """
        return None