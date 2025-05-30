from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from time import sleep
import json
import re
import os
import sys
from enum import IntEnum

current_dir = os.path.dirname(os.path.abspath(__file__))

class BrowserType(IntEnum):
    Chrome = 1
    Firefox = 2


class AutoBrowser():
    def __init__(self, type: BrowserType):
        self.driver = webdriver.Chrome() if type == BrowserType.Chrome else webdriver.Firefox if BrowserType.Firefox else None
        if self.driver == None:
            raise ValueError('Browser type not set. Please specify the browser type.')
        self.xpaths = self.LoadXPaths()
        self.handles = self.driver.window_handles
        self.wait = WebDriverWait(self.driver, 20)

        for key in self.xpaths:
            setattr(self, key, self.xpaths[key])

    def SetWait(self, seconds:int):
        self.wait = WebDriverWait(self.driver, seconds)

    def Script(self, js_code):
        self.driver.execute_script(js_code)

    def NewTab(self, url=None):
        if url == None:
            url = ''
        self.driver.execute_script(f"window.open('{url}');")
        self.handles = self.driver.window_handles
        self.driver.switch_to.window(self.handles[-1])
    
    def SwitchTab(self):
        self.driver.switch_to.window(self.handles[-1])

    def LoadXPaths(self):
        xpaths_path = os.path.join(current_dir, 'xpaths.json')

        try:
            with open(xpaths_path, 'r') as file:
                xpaths = json.load(file)
                print("XPaths loaded successfully.")
                return xpaths
        except FileNotFoundError:
            print(f"xpaths.json file not found at path: {xpaths_path}")
            return {}

    def XPath(self, key):
        return self.xpaths.get(key)

    def OpenWebsite(self, url):
        if not(url.startswith('http://') or url.startswith('https://')):
            url = f'https://{url}'
        self.driver.get(url)

    def FindElementXPATH(self, xpath):
        return self.wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def FindElementByID(self, id:str, all_elements:bool = False):
        if all_elements:
            elements = self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, f"[id^='{id}']")
                )
            )
            return elements
        else:
            element = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, f"[id^='{id}']")
                )
            )
            return element
    
    def FindElementsByClass(self, class_name:str):
        elements = self.driver.find_elements(By.XPATH, f"//div[contains(@class, '{class_name}')]")
        return elements

    
    def FindElementsByText(self, text:str, partial:bool = False):
        if partial == True:
            elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")
            return elements
        else:
            elements = self.driver.find_elements(By.XPATH, f"//*[text()='{text}']")
            return elements
    
    def FindHrefs(self):
        hrefs = []
        links = self.driver.find_elements(By.TAG_NAME, "a")
        hrefs.extend([link.get_attribute("href") for link in links])
        return hrefs

    def ClickElement(self, xpath):
        clickable_element = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        clickable_element.click()

    
    def TextInput(self, xpath, text):
        text_element = self.wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        text_element.send_keys(text)

    def GetElementText(self, xpath):
        element = self.wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return element.text

    def CloseBrowser(self):
        self.driver.quit()

    @staticmethod
    def IsUrlValid(url):
        pattern = re.compile(r'https?://\S+')
        return bool(pattern.match(url))

    @staticmethod
    def FilterLinks(keywords:list, links:list):
        filtered_links = [url for url in links if any(kw in url for kw in keywords)]
        return filtered_links