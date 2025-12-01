import ollama



# Input a prompt into the llm, default model is the lightest one. Returns the llm response
class OllamaClient:

    def __init__(self, model: str = 'gemma3:270m', system_prompt: str = None):
        self.model_name = model
        self.messages = []

        # System prompt (rules to be applied to every output)
        if system_prompt:
            self.messages.append({
                'role': 'system',
                'content': system_prompt
            })
        else:
            self.messages.append({
                'role': 'system',
                'content': 'Only plain text alphabet (no letter bold, italics, symbols like (-, +, *) should be ' +
                'in the output.'
            })


    def ask_llm(self, prompt:str) -> str:
        """
        Send prompt to LLM, and return its response. Conversation history is remembered.
        Args:
            prompt (str): user prompt

        Returns:
            str: llm's response
        """
        # Add user prompt to conversation history
        self.messages.append({
            'role': 'user',
            'content': prompt
        })

        # Ask LLM
        response = ollama.chat(model=self.model_name, messages=self.messages)
        response_content = response['message']['content']

        # Add LLM repsonse to conversation history
        self.messages.append({
            'role': 'assistant',
            'content': response_content
        })

        return response_content

    
    def clear_history(self, keep_system_prompt: bool = True) -> None:
        """
        Clears the conversation history
        Args:
            keep_system_prompt (bool, optional): If True, will also clear the system prompt. Defaults to True.
        """
        if keep_system_prompt and self.messages and self.messages[0]['role'] == 'system':
            system_msg = self.messages[0]
            self.messages = [system_msg]
        else:
            self.messages = []


    def get_history(self, formatted:bool = False):
        """
        Gets the conversation history
        Args:
            formatted (bool, optional): If true, gets formatted version of conversation history. Defaults to False.
        """
        if formatted:
            conversation = []
            for msg in self.messages:
                if msg['role'] == 'system':
                    conversation.append(f"[SYSTEM]: {msg['content']}")
                elif msg['role'] == 'user':
                    conversation.append(f"User: {msg['content']}")
                elif msg['role'] == 'assistant':
                    conversation.append(f"Assistant: {msg['content']}")
            return '\n\n'.join(conversation)
        else:
            return self.messages.copy()


# NOTE: FOR DEBUGGING
def main():
    print("START MESSAGING THE LLM NOW")
    llm = OllamaClient(model='gemma3:1b')
    user_input:str = ""

    while True:
        user_input = input()
        if user_input == "/bye":
            break
        print(llm.ask_llm(user_input))

    print(llm.get_history(True))


if __name__ == "__main__":
    main()
