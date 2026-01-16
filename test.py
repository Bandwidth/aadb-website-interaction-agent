from utils import get_web_element_rect
import requests
import undetected_chromedriver as uc
from selenium import webdriver
from run import exec_action_click
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium_stealth import stealth
import time
import boto3
import os

from sully_utils import WebsiteInteractionAgent
from google.adk.models.lite_llm import LiteLlm
import asyncio

async def main():
    session = boto3.Session(profile_name = os.getenv("AWS_PROFILE"))
    client = session.client('bedrock-runtime', region_name='us-west-2')
    model_id = "bedrock/global.anthropic.claude-sonnet-4-20250514-v1:0"
    my_model = LiteLlm(
        model = model_id,
        client = client
    )

    chrome_options = Options()
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.140 Safari/537.36"
                # Add typical HTTP headers via Chrome command-line
    chrome_options.add_argument("accept=text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/"
        "apng,*/*;q=0.8")
    chrome_options.add_argument("accept-encoding=gzip, deflate, br")
    chrome_options.add_argument("connection=keep-alive")
    chrome_options.add_argument("accept-language=en-US,en;q=0.9")
    chrome_options.add_argument("--enable-features=ReaderMode")
    chrome_options.add_argument("accept-language=en-US,en;q=0.9")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--crash-dumps-dir=/temp")
    chrome_options.add_argument("cache-control=max-age=0")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1024,768")
    driver = webdriver.Chrome(options=chrome_options)

    driver.get('https://www.whitespruce.com')

    # Now load our LLM processor using the async create method
    global agent
    agent = await WebsiteInteractionAgent.create(
        config={},
        browser=driver,
        llm_model=my_model
    )

    time.sleep(2)

# Run the async main function
asyncio.run(main())

test_for_model = asyncio.run(agent.run("""
                           PLease find the contact form for the wesbite. We were provided instructions for this:
                           CONSUMER-INITIATED CONTACT WITH OUR BUSINESS VIA OUR WEBSITE WWW.WHITESPRUCE.COM https://www.whitespruce.com/contact-email-trailers-dealershipxcontact WITH A WIDGET IN WHICH THE CUSTOMER CLICKS \"TEXT US\".  CUSTOMER SUBMITED THEIR FIRST AND LAST NAME, PHONE NUMBER AND THE MESSAGE THEY INTEND TO SEND.  THEY SEE THE DISCLOSURE BEFORE CLICKING SNED.
                           """))