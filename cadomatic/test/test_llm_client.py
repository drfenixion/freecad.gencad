import pytest
from unittest.mock import Mock, patch
from langchain_core.messages import HumanMessage, AIMessage
from src.llm_client import call_model

class TestLLMClient:
    def setup_method(self):
        """Run before each test method"""
        self.default_message = HumanMessage(content="Create a box")
        self.state = {"messages": [self.default_message]}
        print("\nSetup: Initialized default state")

    def teardown_method(self):
        """Run after each test method"""
        print("Teardown: Cleaning up state")
        self.state = None

    def test_call_model_returns_ai_message(self):
        with patch('src.llm_client.retriever') as mock_retriever, \
             patch('src.llm_client.llm') as mock_llm:

            mock_retriever.invoke.return_value = [Mock(page_content="Test doc")]
            mock_llm.invoke.return_value = AIMessage(content="Test response")

            result = call_model(self.state)

            assert isinstance(result, dict)
            assert "messages" in result
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert result["messages"][0].content == "Test response"

    def test_call_model_includes_history(self):
        messages = [
            HumanMessage(content="Create a box"),
            AIMessage(content="Box created"),
            HumanMessage(content="Now add a cylinder")
        ]
        state = {"messages": messages}

        with patch('src.llm_client.retriever') as mock_retriever, \
             patch('src.llm_client.llm') as mock_llm:

            mock_retriever.invoke.return_value = [Mock(page_content="Test doc")]

            def capture_prompt(prompt):
                capture_prompt.prompt_content = prompt
                return AIMessage(content="Test response")

            mock_llm.invoke.side_effect = capture_prompt

            result = call_model(state)
            prompt_content = capture_prompt.prompt_content

            assert "Create a box" in prompt_content
            assert "Box created" in prompt_content
            assert "Now add a cylinder" in prompt_content

    def test_call_model_uses_retriever(self):
        with patch('src.llm_client.retriever') as mock_retriever, \
             patch('src.llm_client.llm') as mock_llm:

            mock_docs = [Mock(page_content="Test documentation")]
            mock_retriever.invoke.side_effect = lambda query: mock_docs
            mock_llm.invoke.return_value = AIMessage(content="Test response")

            result = call_model(self.state)

            # Check that retriever was called with the last message
            assert mock_retriever.invoke.call_args[0][0] == "Create a box"

    def test_call_model_structure(self):
        with patch('src.llm_client.retriever') as mock_retriever, \
             patch('src.llm_client.llm') as mock_llm:

            mock_retriever.invoke.return_value = [Mock(page_content="Test doc")]
            mock_llm.invoke.return_value = AIMessage(content="Generated code")

            result = call_model(self.state)

            assert isinstance(result, dict)
            assert "messages" in result
            assert isinstance(result["messages"], list)
            assert len(result["messages"]) == 1
            assert isinstance(result["messages"][0], AIMessage)
            assert "Generated code" in result["messages"][0].content

    def test_call_model_with_empty_messages(self):
        state = {"messages": []}
        with pytest.raises((IndexError, KeyError)):
            call_model(state)

    def test_prompt_content_analysis(self):
        with patch('src.llm_client.retriever') as mock_retriever, \
             patch('src.llm_client.llm') as mock_llm:

            mock_retriever.invoke.return_value = [Mock(page_content="Test documentation")]

            captured_prompts = []

            def capture_llm_call(prompt):
                captured_prompts.append(str(prompt))
                return AIMessage(content="Test response")

            mock_llm.invoke.side_effect = capture_llm_call

            result = call_model(self.state)

            assert len(captured_prompts) == 1
            prompt = captured_prompts[0]

            print("Captured prompt content:")
            print("=" * 50)
            print(prompt)
            print("=" * 50)

            assert "Create a box" in prompt
            assert "FreeCAD" in prompt
            assert "Python code" in prompt
