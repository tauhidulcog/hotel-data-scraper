import signal
import ssl
import urllib.request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import pandas as pd
import json
from time import sleep
import undetected_chromedriver as uc


class DriverManager:
    """
    This context manager manage the chrome driver and manage the resources.
    """

    def __init__(self):
        # Fix SSL certificate issues for undetected_chromedriver
        self._setup_ssl_context()
        
        user_agent_file_path = 'user_agents.json'
        with open(user_agent_file_path) as user_agents:
            self.user_agents = json.load(user_agents)

        self.driver = self._chrome_driver()

    def __enter__(self) -> webdriver.Chrome:
        return self.driver

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit_driver()

    def _setup_ssl_context(self):
        """Setup SSL context to handle certificate verification issues"""
        try:
            # Create unverified SSL context for downloads
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Install the SSL context globally
            urllib.request.install_opener(
                urllib.request.build_opener(
                    urllib.request.HTTPSHandler(context=ssl_context)
                )
            )
        except Exception as e:
            print(f"Warning: Could not setup SSL context: {e}")

    def _setup_chrome_driver_options(self) -> webdriver.ChromeOptions:
        # driver_options = webdriver.ChromeOptions()
        driver_options = uc.ChromeOptions()
        driver_options.add_argument('--ignore-certificate-errors')
        driver_options.add_argument('--incognito')
        # driver_options.add_argument('--headless')
        # driver_options.add_argument('--disable-gpu')
        driver_options.add_argument('--no-sandbox')
        # Solving the 403 issue.
        driver_options.add_argument(
            '--disable-blink-features=AutomationControlled'
        )
        driver_options.add_argument("--disable-extensions")
        # driver_options.add_experimental_option('useAutomationExtension', False)
        # driver_options.add_experimental_option(
        #     "excludeSwitches", ["enable-automation"]
        # )
        # Rotate the UserAgent.
        driver_options.add_argument(
            f'user-agent={random.choice(self.user_agents)["user_agent"]}'
        )
        # self.driver_options.add_argument(
        #     'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        #     '(KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        # )
        # driver_options.add_argument('window-size=1920x1080')

        return driver_options

    def _chrome_driver(self) -> webdriver.Chrome:
        # Setup driver options.
        driver_options = self._setup_chrome_driver_options()

        try:
            # Try with specific Chrome version first
            driver = uc.Chrome(options=driver_options, version_main=140)
        except Exception as e:
            print(f"Failed to create driver with version 140: {e}")
            try:
                # Fallback: Let undetected_chromedriver auto-detect version
                driver = uc.Chrome(options=driver_options)
            except Exception as e2:
                print(f"Failed to create driver with auto-detection: {e2}")
                # Final fallback: Use regular selenium ChromeDriver
                print("Falling back to regular selenium ChromeDriver")
                driver = webdriver.Chrome(options=driver_options)

        return driver

    def quit_driver(self):
        driver = self.driver
        # Quit the driver process using SIGTERM signal.
        driver.quit()
        driver.service.stop()
        sleep(5)
        # Check driver process has been closed or not.
        if driver.service.process.poll() is None:
            # The driver process doesn't close yet. Need to force close.
            driver.service.process.send_signal(signal.SIGKILL)
            sleep(5)

