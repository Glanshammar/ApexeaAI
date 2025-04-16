import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from AutoBrowser import AutoBrowser, BrowserType
from time import sleep
import random

browser = AutoBrowser(BrowserType.Chrome)
browser.OpenWebsite('https://the-internet.herokuapp.com/')
sleep(5)
browser.CloseBrowser()