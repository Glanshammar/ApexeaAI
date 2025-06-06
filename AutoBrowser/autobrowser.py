from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from typing import Dict, List, Optional, Union, Any
from enum import IntEnum
import json
import re
import os
import sys
from time import sleep

current_dir = os.path.dirname(os.path.abspath(__file__))

class BrowserType(IntEnum):
    Chromium = 1
    Firefox = 2
    Webkit = 3

class AutoBrowser:
    def __init__(self, type: BrowserType, headless: bool = False):
        self.playwright = sync_playwright().start()
        
        # Initialize browser based on type
        if type == BrowserType.Chromium:
            self.browser = self.playwright.chromium.launch(headless=headless)
        elif type == BrowserType.Firefox:
            self.browser = self.playwright.firefox.launch(headless=headless)
        elif type == BrowserType.Webkit:
            self.browser = self.playwright.webkit.launch(headless=headless)
        else:
            raise ValueError('Invalid browser type. Please specify a valid browser type.')
        
        # Create a new context and page
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        
        # Load XPaths
        self.xpaths = self.LoadXPaths()
        
        # Set default timeout (20 seconds)
        self.page.set_default_timeout(20000)
        
        # Expose XPath elements as attributes
        for key in self.xpaths:
            setattr(self, key, self.xpaths[key])
    
    def SetTimeout(self, seconds: int) -> None:
        self.page.set_default_timeout(seconds * 1000)  # Convert to milliseconds
    
    def Script(self, js_code: str) -> Any:
        return self.page.evaluate(js_code)
    
    def NewTab(self, url: Optional[str] = None) -> Page:
        new_page = self.context.new_page()
        if url:
            new_page.goto(url)
        self.page = new_page
        return new_page
    
    def SwitchTab(self, index: int = -1) -> None:
        pages = self.context.pages
        if 0 <= index < len(pages):
            self.page = pages[index]
        else:
            raise IndexError(f"Tab index {index} is out of range. Available tabs: {len(pages)}")
    
    def LoadXPaths(self) -> Dict[str, str]:
        xpaths_path = os.path.join(current_dir, 'xpaths.json')
        
        try:
            with open(xpaths_path, 'r') as file:
                xpaths = json.load(file)
                print("XPaths loaded successfully.")
                return xpaths
        except FileNotFoundError:
            print(f"xpaths.json file not found at path: {xpaths_path}")
            return {}
    
    def XPath(self, key: str) -> Optional[str]:
        return self.xpaths.get(key)
    
    def OpenWebsite(self, url: str) -> None:
        if not (url.startswith('http://') or url.startswith('https://')):
            url = f'https://{url}'
        self.page.goto(url)
    
    def FindElementXPATH(self, xpath: str):
        return self.page.wait_for_selector(xpath)
    
    def FindElementByID(self, id_prefix: str, all_elements: bool = False):
        selector = f"[id^='{id_prefix}']"
        if all_elements:
            return self.page.query_selector_all(selector)
        else:
            return self.page.wait_for_selector(selector)
    
    def FindElementsByClass(self, class_name: str):
        return self.page.query_selector_all(f"div[class*='{class_name}']")
    
    def FindElementsByText(self, text: str, partial: bool = False):
        if partial:
            return self.page.query_selector_all(f"//*[contains(text(), '{text}')]")
        else:
            return self.page.query_selector_all(f"//*[text()='{text}']")
    
    def FindHrefs(self) -> List[str]:
        return self.page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a'));
            return links.map(link => link.href).filter(href => href);
        }""")
    
    def ClickElement(self, xpath: str) -> None:
        self.page.click(xpath)
    
    def TextInput(self, xpath: str, text: str) -> None:
        self.page.fill(xpath, text)
    
    def GetElementText(self, xpath: str) -> str:
        element = self.page.wait_for_selector(xpath)
        return element.text_content() if element else ""
    
    def TakeScreenshot(self, path: str) -> None:
        self.page.screenshot(path=path)
    
    def WaitForNavigation(self) -> None:
        self.page.wait_for_load_state("networkidle")
    
    def WaitForSelector(self, selector: str, timeout: Optional[int] = None) -> None:
        if timeout:
            self.page.wait_for_selector(selector, timeout=timeout * 1000)
        else:
            self.page.wait_for_selector(selector)
    
    def GetPageTitle(self) -> str:
        return self.page.title()
    
    def GetPageUrl(self) -> str:
        return self.page.url
    
    def GoBack(self) -> None:
        self.page.go_back()
    
    def GoForward(self) -> None:
        self.page.go_forward()
    
    def Reload(self) -> None:
        self.page.reload()
    
    def CloseBrowser(self) -> None:
        self.browser.close()
        self.playwright.stop()
    
    @staticmethod
    def IsUrlValid(url: str) -> bool:
        pattern = re.compile(r'https?://\S+')
        return bool(pattern.match(url))
    
    @staticmethod
    def FilterLinks(keywords: List[str], links: List[str]) -> List[str]:
        return [url for url in links if any(kw in url for kw in keywords)]