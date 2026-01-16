from google.adk.tools import ToolContext
import time
from typing import Dict, Any

def tool_answer_user_query(answer: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Answer the original user query. 
    
    You should use this tool when you have complete all necessary steps to confidently answer 
    the user's original instructions. Once you have used this tool, the interaction will end.

    In order to call this tool you must provide the answer string.

    Args:
        answer (str): The answer to the user's original query.
    """
    print(tool_context.state)
    tool_context.state["final_answer"] = answer
    return {"status": 200, "message": "Final answer recorded."}

def tool_wait(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Wait for a period of time.
    
    You should use this tool when you need to wait for elements to load. You should not call this tool
    multiple times in a row.
    """
    time.sleep(5)
    return {"status": 200, "message": "Waited for 5 seconds."}
    
def tool_click_web_element(web_element_num: int, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Click a Web Element.
    
    You need to use this tool when you want to click on a web element on the page. You will need to provide the
    number of the web element that you want to click.
    
    In order to use this tool you must provide the web element number.

    Args:
        web_element_num (int): The number of the web element that you want to click.
    """
    browser = tool_context.state.get("webdriver")
    if not browser:
        return {"error": "No browser instance found in tool context."}
    
    web_elements = tool_context.state.get("web_elements")
    if not web_elements or web_element_num >= len(web_elements):
        return {"error": f"Web element number {web_element_num} is out of range."}
    
    try:
        web_elements[web_element_num].click()
        time.sleep(2)  # Wait for the page to load after clicking
        return {"status": 200, "message": f"Clicked on web element number {web_element_num}."}
    except Exception as e:
        return {"error": str(e)}
    
# TODO add more tools for typing, scrolling, etc.