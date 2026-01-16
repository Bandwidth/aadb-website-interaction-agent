import base64
import re
import os
import json
import time
import logging
from typing import List
import inspect
import numpy as np
from PIL import Image
from selenium import webdriver
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.planners import PlanReActPlanner
from google.adk.models.lite_llm import LiteLlm
from google.adk.agents import LlmAgent, LoopAgent
from google.adk.runners import InMemoryRunner, Runner
from google.genai import types
from google.adk.agents.callback_context import CallbackContext
import asyncio
import website_interaction_tools


class WebsiteInteractionAgent:
    
    def __init__(self, config: dict, browser: webdriver.Chrome, llm_model: LiteLlm):
        self.config = config
        self.browser = browser
        self.screenshot_filename = config.get('screenshot_filename', 'annotated_screenshot.png')
        self.setup_tools_and_prompt()
        
        self.app_name = config.get('app_name', 'WebsiteInteractionAgent')
        self.user_id = config.get('user_id', 'default_user')
        self.session_id = config.get('session_id', 'default_session')
        self.llm_model = llm_model
        
    @classmethod
    async def create(cls, config: dict, browser: webdriver.Chrome, llm_model: LiteLlm):
        """
        Async factory method to create a WebsiteInteractionAgent instance.
        
        Usage:
            agent = await WebsiteInteractionAgent.create(config, browser, llm_model)
        """
        # Create instance using __init__
        instance = cls(config, browser, llm_model)
        
        # Setup our agent needs (async part)
        session = InMemorySessionService()
        instance.session_service = await session.create_session(
            app_name=instance.app_name,
            user_id=instance.user_id,
            session_id=instance.session_id,
            state={}
        )
        
        # Create our LLMAgent
        instance.processor_agent = LlmAgent(
            model=instance.llm_model,
            name='WebsiteDecisionProcessor',
            instruction=instance.system_prompt,
            tools=instance.allowed_tools,
            #planner=PlanReActPlanner(),
            generate_content_config=types.GenerateContentConfig(
                # Set temperateure to be deterministic
                temperature=0.0,
                # Set max output tokens to something reasonable
                # Since the LLM is only making decisions, it shouldn't need too many tokens
                max_output_tokens=500
            ),
        )
        
        instance.runner = Runner(
            app_name=instance.app_name,
            agent=instance.processor_agent, 
            session_service=session
        )
        
        instance.session_service.state['webdriver'] = browser
        
        return instance
        
    async def run(self, user_query: str) -> str:
        """
        Runs the looping agent to answer a given user query.
        """
        self.session_service.state['user_task'] = user_query        
        # Convert our original query to parts.
        query_part = types.Part(
            text=user_query
        )
        
        # Get our first webpage state
        webtext = self.get_current_webpage_state()
        webtext_part = types.Part(
            text = webtext
        )
        # Get our image text as a part
        parts = [query_part, webtext_part, self.image_part]
        
        # Reset the final answer state
        self.session_service.state['final_answer'] = None
        self.session_service.state['action_taken'] = None
        
        max_iterations = self.config.get('max_iterations', 10)
        for iteration in range(max_iterations):
            # Call our LLM with the original parts
            print(await self.call_llm(parts))
            
            # Check if we have a final answer
            final_answer = self.session_service.state.get('final_answer')
            if final_answer:
                return final_answer
            
            # Ask the LLM what action it needs to take next
            update_request = types.Part(
                text="Here is your current webpage state. Please decide what action to take next."
            )
            
            # Otherwise we need to update our webpage state
            webtext = self.get_current_webpage_state()
            webtext_part = types.Part(
                text = webtext
            )
            
            parts = [update_request, webtext_part, self.image_part]
            
        return "Unable to find a final answer within the maximum number of iterations."
            
        
    async def call_llm(self, parts: List[types.Part]) -> str:
        """
        Calls the LLM with the given parts and returns the response.

        Args:
            parts (List[types.Part]): The parts to send to the LLM.
        """
        content = types.Content(role='user', parts=parts)
        iterations = 100
        iteration = 0
        async for event in self.runner.run_async(user_id = self.user_id, session_id = self.session_id,
                                 new_message=content):
            print(event)
            if event.is_final_response():
                final_response = event.content
                return final_response
            if iteration >= iterations:
                iteration += 1
        
        return None
        
    def get_current_webpage_state(self) -> str:
        """
        Gets the screenshot and web elements of the current webpage and updates the artifact and session state.

        Returns:
            String of element text.
        """
        # Setup our web elements
        rects, element, element_text = self.get_web_element_rect(fix_color=True)
        
        # Get screenshot
        image_bytes = self.save_screenshot(filename=self.screenshot_filename)
        
        # Load image bytes into a the correct types
        self.image_part = types.Part(
            inline_data = types.Blob(
                mime_type = "image/png",
                data = image_bytes
            )
        )
        
        # Update artifact state
        self.session_service.state['web_elements'] = element
        self.session_service.state['formatted_ele_text'] = element_text
        
        # Delete the rectangles after taking the screeenshot
        self.del_web_element_rect()
        
        return "\t".join(element_text)
    
    def setup_tools_and_prompt(self) -> None:
        """
        Sets up the allowed tools and system prompt based on configuration.
        """
        # Load from website_interaction_tools
        available_tools = {
            name: obj for name, obj in inspect.getmembers(website_interaction_tools, inspect.isfunction)
            if name.startswith('tool_')
        }
        
        # Determine if we have a restricted set of tools    
        allowed_tools = self.config.get('allowed_tools', list(available_tools.keys()))
        
        allowed_tools = [available_tools[tool_name] for tool_name in allowed_tools if tool_name in available_tools]
        self.allowed_tools = allowed_tools
        
        # Now we need to setup the sytem prompt
        with open('system_prompt.txt', 'r') as file:
            self.system_prompt = file.read()
        return None
    
    
    def save_screenshot(self, filename='current_screenshot.png') -> str:
        """
        Captures a screenshot of the current browser instance.

        Returns:
            str: The image bytes of a screenshot.
        """
        screenshot_data = self.browser.save_screenshot(filename)
        
        # Open our screenshot
        with open(filename, 'rb') as img_file:
            image_bytes = img_file.read()
        
        return image_bytes
    
    # interact with webpage and add rectangles on elements
    def get_web_element_rect(self, fix_color: bool=True) -> tuple[list, list, str]:
        """
        Gets the rectangles of web elements on a webpage using JavaScript executed in the browser.

        Args:
            browser (webdriver.Chrome): The Selenium WebDriver instance controlling the browser.
            fix_color (bool): Whether to use a fixed color for the rectangles or random colors.
    
        Returns:
            tuple: A tuple containing:
                - list: A list of rectangle elements drawn on the webpage.
                - list: A list of web elements corresponding to the rectangles.
                - str: A formatted string of element texts with their indices.
        """
        if fix_color:
            selected_function = "getFixedColor"
            # color_you_like = '#5210da'
        else:
            selected_function = "getRandomColor"


        # This script draws rectangles around interactive elements and labels them with indices.
        with open('label_script.txt', 'r') as file:
            js_script = file.read().replace("COLOR_FUNCTION", selected_function)
    
        rects, items_raw = self.browser.execute_script(js_script)

        # format_ele_text = [f"[{web_ele_id}]: \"{items_raw[web_ele_id]['text']}\";" for web_ele_id in range(len(items_raw)) if items_raw[web_ele_id]['text'] ]
        format_ele_text = []
    
        # Loop through each web element and annotate based on conditions
        for web_ele_id in range(len(items_raw)):
            label_text = items_raw[web_ele_id]['text']
            ele_tag_name = items_raw[web_ele_id]['element'].tag_name
            ele_type = items_raw[web_ele_id]['element'].get_attribute("type")
            ele_aria_label = items_raw[web_ele_id]['element'].get_attribute("aria-label")
            input_attr_types = ['text', 'search', 'password', 'email', 'tel']
        
            if not label_text:
                if (ele_tag_name.lower() == 'input' and ele_type in input_attr_types) or ele_tag_name.lower() == 'textarea' or (ele_tag_name.lower() == 'button' and ele_type in ['submit', 'button']):
                    if ele_aria_label:
                        format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{ele_aria_label}\";")
                    else:
                        format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";" )

            elif label_text and len(label_text) < 200:
                if not ("<img" in label_text and "src=" in label_text):
                    if ele_tag_name in ["button", "input", "textarea"]:
                        if ele_aria_label and (ele_aria_label != label_text):
                            format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\", \"{ele_aria_label}\";")
                        else:
                            format_ele_text.append(f"[{web_ele_id}]: <{ele_tag_name}> \"{label_text}\";")
                    else:
                        if ele_aria_label and (ele_aria_label != label_text):
                            format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\", \"{ele_aria_label}\";")
                        else:
                            format_ele_text.append(f"[{web_ele_id}]: \"{label_text}\";")


        format_ele_text = '\t'.join(format_ele_text)
        
        # also asign rects so that we can delete them later
        self.rects = rects
        return rects, [web_ele['element'] for web_ele in items_raw], format_ele_text

    
    def del_web_element_rect(self):
        """
        Deletes the rectangles drawn on the webpage.

        Args:
            browser (webdriver.Chrome): The Selenium WebDriver instance controlling the browser.
        """
        if hasattr(self, 'rects'):
            js_del_script = """
            for (let i = 0; i < arguments[0].length; i++) {
                document.body.removeChild(arguments[0][i]);
            }
            """
            self.browser.execute_script(js_del_script, self.rects)
            del self.rects